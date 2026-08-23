"""Callback de LangChain que registra el arbol de delegacion en Roxy.

Se engancha una vez, en el `config` de la invocacion, y desde ahi cada
agente que se lance queda registrado solo. Quien integra el SDK no toca
sus agentes: no hay ids que pasar de mano en mano ni llamadas que agregar
en cada nodo.
"""
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from langchain_core.callbacks import BaseCallbackHandler

from roxy.client import Decision, RoxyClient, RoxyUnavailable

# Chains que LangChain dispara por su cuenta (el prompt, el parser, el
# scratchpad del agente). Registrarlas llenaria el arbol de ruido: en una
# corrida de cuatro agentes son ~90 eventos, y solo un punado son agentes.
_NOISE = {"RunnableSequence", "RunnableAssign", "RunnableParallel",
          "RunnableLambda", "ChatPromptTemplate", "PromptTemplate",
          "RunnableBinding", "ToolsAgentOutputParser"}


class Roxy(BaseCallbackHandler):
    """Handler de LangChain con la trazabilidad y el control de acceso.

        roxy = Roxy(api_url="https://roxygt.lat/api")
        executor.invoke(entrada, config={"callbacks": [roxy]})

    Un nodo se registra cuando el `metadata` de la invocacion trae
    `purpose`, o cuando el chain es un AgentExecutor. El resto se ignora.
    """

    def __init__(self, api_url: str, gateway_url: Optional[str] = None,
                 api_key: Optional[str] = None, session_id: Optional[str] = None,
                 mcp_name: Optional[str] = None):
        self.client = RoxyClient(api_url=api_url, gateway_url=gateway_url, api_key=api_key)
        self.session_id = session_id or str(uuid4())
        self.mcp_name = mcp_name
        # run_id de LangChain (UUID) -> id del agente en Roxy (ObjectId).
        # La API valida `parentId` como ObjectId, asi que el id del
        # framework no sirve de padre: hay que traducirlo.
        self._agent_ids: Dict[str, str] = {}
        # Guarda el padre declarado de las invocaciones que LangChain no
        # puede encadenar solo (ver _resolve_parent).
        self._declared: Dict[str, str] = {}
        # purpose visto en cada run, para detectar el heredado (ver
        # _is_inherited).
        self._purposes: Dict[str, str] = {}

    # --- registro del arbol ----------------------------------------------

    def _resolve_parent(self, run_id: str, parent_run_id: Optional[UUID],
                        metadata: Dict[str, Any]) -> Optional[str]:
        """Traduce el padre de LangChain al id que Roxy espera.

        Un sub-agente lanzado con su propio `.invoke()` llega sin
        parent_run_id: para esos, quien lo lanza declara el padre en
        metadata como `roxy_parent` (el id que devolvio Roxy) o
        `parent_run_id` (el run_id del framework, que se traduce aca).
        """
        if parent_run_id:
            traducido = self._agent_ids.get(str(parent_run_id))
            if traducido:
                return traducido

        declarado = metadata.get("roxy_parent")
        if declarado:
            return declarado

        declarado_run = metadata.get("parent_run_id")
        if declarado_run:
            return self._agent_ids.get(str(declarado_run))

        return self._declared.get(run_id)

    def _is_inherited(self, parent_run_id: Optional[UUID], purpose: str) -> bool:
        """LangChain copia el `metadata` de una invocacion a cada chain
        anidado, asi que el prompt, el parser y el scratchpad llegan aca con
        el mismo `purpose` del agente. Si el padre ya traia este purpose, lo
        que estamos viendo es esa herencia y no un agente nuevo."""
        if parent_run_id is None:
            return False
        return self._purposes.get(str(parent_run_id)) == purpose

    def _should_register(self, name: str, metadata: Dict[str, Any]) -> bool:
        if metadata.get("purpose"):
            return True
        return name not in _NOISE and name.endswith("AgentExecutor")

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None,
                       tags=None, metadata=None, **kwargs):
        meta = metadata or {}
        name = (serialized or {}).get("name", "chain")
        run_id_s = str(run_id)
        purpose = meta.get("purpose") or name

        if meta.get("purpose"):
            self._purposes[run_id_s] = meta["purpose"]

        if not self._should_register(name, meta):
            return
        if self._is_inherited(parent_run_id, purpose):
            return

        parent_id = self._resolve_parent(run_id_s, parent_run_id, meta)

        agent_id = self.client.register_agent(
            purpose=purpose, session_id=self.session_id, parent_id=parent_id,
        )
        if agent_id:
            self._agent_ids[run_id_s] = agent_id

    # --- identidad --------------------------------------------------------

    def agent_id_for(self, run_id) -> Optional[str]:
        """El id que Roxy le dio a ese run, para usarlo como padre de los
        sub-agentes que lance o como identidad ante el gateway."""
        return self._agent_ids.get(str(run_id))

    def child_config(self, parent_run_id, purpose: str, **metadata) -> Dict[str, Any]:
        """Config lista para el `.invoke()` de un sub-agente, con este
        handler y el padre ya declarado."""
        return {
            "callbacks": [self],
            "metadata": {
                "purpose": purpose,
                "roxy_parent": self.agent_id_for(parent_run_id),
                **metadata,
            },
        }

    # --- delegacion entre procesos (A2A) ----------------------------------

    def headers_to_send(self, run_id=None) -> Dict[str, str]:
        """Headers para propagar la cadena al delegar a un agente que corre
        en otro proceso. Sin esto, el sub-agente remoto arranca un arbol
        nuevo y la cadena se corta justo donde importa."""
        headers = {"X-Roxy-Session": self.session_id}
        agent_id = self.agent_id_for(run_id) if run_id else None
        if agent_id:
            headers["X-Roxy-Parent"] = agent_id
        try:
            from langsmith.run_helpers import get_current_run_tree
            tree = get_current_run_tree()
            if tree is not None:
                headers.update(tree.to_headers())
        except Exception:
            pass
        return headers

    def receive(self, headers: Dict[str, str], fn, *args, **kwargs):
        """Del lado que recibe la delegacion: engancha lo que corra adentro
        a la cadena del agente que llamo."""
        session = headers.get("X-Roxy-Session")
        if session:
            self.session_id = session
        parent = headers.get("X-Roxy-Parent")
        if parent:
            self._declared[str(kwargs.get("run_id", ""))] = parent

        try:
            from langsmith.run_helpers import tracing_context
            with tracing_context(parent=headers):
                return fn(*args, **kwargs)
        except ImportError:
            return fn(*args, **kwargs)

    # --- lectura ----------------------------------------------------------

    def lineage(self, agent_id: str) -> list:
        """De la raiz hasta ese agente. Responde 'quien pidio esto y por
        orden de quien', que es la pregunta de una auditoria."""
        nodos = {n["_id"]: n for n in self.client.fetch_agents(self.session_id)}
        camino, actual, vistos = [], agent_id, set()
        while actual and actual in nodos and actual not in vistos:
            vistos.add(actual)
            camino.append(actual)
            actual = nodos[actual].get("parentId")
        return list(reversed(camino))

    def tree(self) -> list:
        return self.client.fetch_agents(self.session_id)

    # --- control de acceso ------------------------------------------------

    def guard(self, *, action: str, payload: Dict[str, Any], run_id=None,
              accessed_by: Optional[str] = None,
              mcp_name: Optional[str] = None) -> Decision:
        """Somete una accion al veredicto de Roxy antes de ejecutarla.

        Levanta RoxyUnavailable si Roxy no puede decidir: sin veredicto no
        hay permiso.
        """
        target = mcp_name or self.mcp_name
        if not target:
            raise ValueError("hace falta mcp_name (en el constructor o en la llamada)")
        agent_id = self.agent_id_for(run_id) if run_id else None
        return self.client.evaluate(
            mcp_name=target,
            accessed_by=accessed_by or agent_id or "agente-desconocido",
            action=action,
            payload=payload,
            agent_id=agent_id,
        )


__all__ = ["Roxy", "Decision", "RoxyUnavailable"]
