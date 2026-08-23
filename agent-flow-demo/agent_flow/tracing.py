import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from agent_flow import config

# Bloque 9 (interceptor de Santiago) todavia no existe: este handler escribe
# el mismo shape propuesto para la futura coleccion `traces` en
# demo/INTEGRATION-NOTES.md (run_id/parent_run_id/root_run_id/type/name/
# purpose/context/started_at) a un archivo JSONL local, para que conectarlo
# a Mongo despues sea solo cambiar el sink.
#
# El orquestador y cada subagente corren como invocaciones de LangChain
# independientes (no como un solo Runnable anidado), asi que el
# parent_run_id "real" que entrega el framework es None para cada una. Para
# igual poder agrupar el arbol de delegacion, quien lanza cada subagente le
# pasa su propio run_id como metadata["parent_run_id"] al invocar — este
# handler prioriza ese valor declarado sobre el que entrega el framework.


class RunTraceHandler(BaseCallbackHandler):
    def __init__(self, path=None):
        self.path = path or config.TRACES_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._parent_by_run: Dict[str, Optional[str]] = {}

    def _root_of(self, run_id: str) -> str:
        current = run_id
        seen = set()
        while True:
            parent = self._parent_by_run.get(current)
            if parent is None or parent in seen:
                return current
            seen.add(current)
            current = parent

    def _write(self, *, run_id: UUID, parent_run_id: Optional[UUID], type_: str,
               name: str, metadata: Optional[Dict[str, Any]]):
        run_id_s = str(run_id)
        meta = metadata or {}
        # El parent_run_id real del framework manda siempre que exista (es
        # el anidamiento correcto dentro de una misma invocacion). Solo se
        # usa el declarado en metadata para la unica costura que LangChain
        # no puede resolver solo: la raiz de cada subagente, invocado como
        # un .invoke() independiente del orquestador.
        parent_run_id_s = (str(parent_run_id) if parent_run_id else None) or meta.get("parent_run_id")
        self._parent_by_run[run_id_s] = parent_run_id_s

        record = {
            "run_id": run_id_s,
            "parent_run_id": parent_run_id_s,
            "root_run_id": self._root_of(run_id_s),
            "type": type_,
            "name": name,
            "purpose": meta.get("purpose"),
            "context": meta.get("context"),
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        label = record["purpose"] or name
        indent = "  " if parent_run_id_s else ""
        print(f"{indent}[{type_}] {run_id_s[:8]} (parent={parent_run_id_s[:8] if parent_run_id_s else '-'}) {label}")

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None,
                        tags=None, metadata=None, **kwargs):
        name = (serialized or {}).get("name", "chain")
        self._write(run_id=run_id, parent_run_id=parent_run_id, type_="chain",
                    name=name, metadata=metadata)

    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None,
                       tags=None, metadata=None, inputs=None, **kwargs):
        name = (serialized or {}).get("name", "tool")
        meta = dict(metadata or {})
        meta.setdefault("context", input_str)
        self._write(run_id=run_id, parent_run_id=parent_run_id, type_="tool",
                    name=name, metadata=meta)

    def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None,
                      tags=None, metadata=None, **kwargs):
        name = (serialized or {}).get("name", "llm")
        self._write(run_id=run_id, parent_run_id=parent_run_id, type_="llm",
                    name=name, metadata=metadata)
