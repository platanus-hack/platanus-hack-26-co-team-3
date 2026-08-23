"""Reconstruccion del arbol de delegacion: quien invoco a quien y a que
tarea raiz pertenece cada nodo."""
import json
from uuid import uuid4

import pytest

from agent_flow.tracing import RunTraceHandler


@pytest.fixture
def handler(tmp_path):
    return RunTraceHandler(path=tmp_path / "run.jsonl")


def leer(handler):
    with open(handler.path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def test_la_raiz_es_su_propio_root(handler):
    raiz = uuid4()
    handler.on_chain_start({"name": "root"}, {}, run_id=raiz)
    registro = leer(handler)[0]
    assert registro["parent_run_id"] is None
    assert registro["root_run_id"] == str(raiz)


def test_un_hijo_apunta_a_su_padre(handler):
    raiz, hijo = uuid4(), uuid4()
    handler.on_chain_start({"name": "root"}, {}, run_id=raiz)
    handler.on_chain_start({"name": "hijo"}, {}, run_id=hijo, parent_run_id=raiz)
    hijo_reg = leer(handler)[1]
    assert hijo_reg["parent_run_id"] == str(raiz)
    assert hijo_reg["root_run_id"] == str(raiz)


def test_un_nieto_hereda_la_raiz_del_abuelo(handler):
    """El caso de los sub-subagentes: tres niveles comparten root_run_id."""
    raiz, hijo, nieto = uuid4(), uuid4(), uuid4()
    handler.on_chain_start({"name": "root"}, {}, run_id=raiz)
    handler.on_chain_start({"name": "hijo"}, {}, run_id=hijo, parent_run_id=raiz)
    handler.on_chain_start({"name": "nieto"}, {}, run_id=nieto, parent_run_id=hijo)
    nieto_reg = leer(handler)[2]
    assert nieto_reg["parent_run_id"] == str(hijo)
    assert nieto_reg["root_run_id"] == str(raiz)


def test_el_padre_declarado_conecta_invocaciones_separadas(handler):
    """Cada subagente es un .invoke() propio, asi que LangChain no le pasa
    parent_run_id; el padre se declara en metadata para no perder el arbol."""
    raiz, hoja = uuid4(), uuid4()
    handler.on_chain_start({"name": "root"}, {}, run_id=raiz)
    handler.on_chain_start({"name": "hoja"}, {}, run_id=hoja,
                           metadata={"parent_run_id": str(raiz)})
    hoja_reg = leer(handler)[1]
    assert hoja_reg["parent_run_id"] == str(raiz)
    assert hoja_reg["root_run_id"] == str(raiz)


def test_el_padre_real_gana_sobre_el_declarado(handler):
    real, declarado, hijo = uuid4(), uuid4(), uuid4()
    handler.on_chain_start({"name": "real"}, {}, run_id=real)
    handler.on_chain_start({"name": "hijo"}, {}, run_id=hijo, parent_run_id=real,
                           metadata={"parent_run_id": str(declarado)})
    assert leer(handler)[1]["parent_run_id"] == str(real)


def test_registra_purpose_y_context(handler):
    run = uuid4()
    handler.on_chain_start({"name": "n"}, {}, run_id=run,
                           metadata={"purpose": "conciliar", "context": {"id": "INV-1"}})
    registro = leer(handler)[0]
    assert registro["purpose"] == "conciliar"
    assert registro["context"] == {"id": "INV-1"}


def test_distingue_chain_tool_y_llm(handler):
    handler.on_chain_start({"name": "c"}, {}, run_id=uuid4())
    handler.on_tool_start({"name": "t"}, "entrada", run_id=uuid4())
    handler.on_llm_start({"name": "l"}, ["prompt"], run_id=uuid4())
    assert [r["type"] for r in leer(handler)] == ["chain", "tool", "llm"]


def test_un_ciclo_no_cuelga_la_busqueda_de_raiz(handler):
    """Defensa contra datos corruptos: _root_of camina hacia arriba y no
    debe quedarse en un bucle infinito."""
    a, b = str(uuid4()), str(uuid4())
    handler._parent_by_run = {a: b, b: a}
    assert handler._root_of(a) in (a, b)
