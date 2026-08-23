"""El callback traduce el arbol de LangChain al que Roxy entiende."""
from uuid import uuid4

import pytest
import requests
import requests_mock

from roxy import Roxy, RoxyUnavailable

API = "http://roxy.test/api"
GATEWAY = "http://roxy.test/gateway"


class _Registro:
    """Responde /agents con un id distinto por llamada y guarda los cuerpos."""

    def __init__(self):
        self.cuerpos = []
        self._n = 0

    def __call__(self, request, context):
        self.cuerpos.append(request.json())
        self._n += 1
        context.status_code = 201
        return {"_id": f"6a8a5ab12deff1419ec2c3{self._n:02x}",
                "purpose": "p", "parentId": None, "sessionId": "s"}


@pytest.fixture
def registro():
    return _Registro()


@pytest.fixture
def roxy(registro):
    with requests_mock.Mocker() as m:
        m.post(f"{API}/agents", json=registro)
        yield Roxy(api_url=API, gateway_url=GATEWAY, mcp_name="invoices-mcp")


def chain_start(roxy, run_id, parent_run_id=None, purpose="tarea", metadata=None):
    meta = {"purpose": purpose}
    if metadata:
        meta.update(metadata)
    roxy.on_chain_start({"name": "X"}, {}, run_id=run_id,
                        parent_run_id=parent_run_id, metadata=meta)


def test_registra_un_nodo_con_purpose(roxy, registro):
    chain_start(roxy, uuid4(), purpose="conciliar facturas")
    assert len(registro.cuerpos) == 1
    assert registro.cuerpos[0]["purpose"] == "conciliar facturas"
    assert registro.cuerpos[0]["parentId"] is None


def test_ignora_los_chains_internos_de_langchain(roxy, registro):
    """Una corrida dispara ~90 eventos; registrarlos todos llenaria el
    arbol de ruido."""
    for nombre in ("RunnableSequence", "ChatPromptTemplate", "RunnableParallel"):
        roxy.on_chain_start({"name": nombre}, {}, run_id=uuid4(), metadata={})
    assert registro.cuerpos == []


def test_registra_un_agentexecutor_sin_purpose(roxy, registro):
    roxy.on_chain_start({"name": "AgentExecutor"}, {}, run_id=uuid4(), metadata={})
    assert len(registro.cuerpos) == 1


def test_traduce_el_padre_al_id_de_roxy(roxy, registro):
    """LangChain da UUIDs; la API exige el ObjectId que ella misma asigno."""
    padre = uuid4()
    chain_start(roxy, padre, purpose="padre")
    id_padre = roxy.agent_id_for(padre)

    chain_start(roxy, uuid4(), parent_run_id=padre, purpose="hijo")
    assert registro.cuerpos[1]["parentId"] == id_padre
    assert "-" not in registro.cuerpos[1]["parentId"]  # ObjectId, no UUID


def test_encadena_tres_niveles(roxy, registro):
    abuelo, padre, nieto = uuid4(), uuid4(), uuid4()
    chain_start(roxy, abuelo, purpose="abuelo")
    chain_start(roxy, padre, parent_run_id=abuelo, purpose="padre")
    chain_start(roxy, nieto, parent_run_id=padre, purpose="nieto")

    assert registro.cuerpos[0]["parentId"] is None
    assert registro.cuerpos[1]["parentId"] == roxy.agent_id_for(abuelo)
    assert registro.cuerpos[2]["parentId"] == roxy.agent_id_for(padre)


def test_padre_declarado_para_invocaciones_separadas(roxy, registro):
    """Un sub-agente lanzado con su propio .invoke() llega sin
    parent_run_id: el padre se declara en metadata."""
    padre = uuid4()
    chain_start(roxy, padre, purpose="padre")
    id_padre = roxy.agent_id_for(padre)

    chain_start(roxy, uuid4(), purpose="hijo suelto",
                metadata={"roxy_parent": id_padre})
    assert registro.cuerpos[1]["parentId"] == id_padre


def test_child_config_arma_la_config_del_subagente(roxy):
    padre = uuid4()
    chain_start(roxy, padre, purpose="padre")
    cfg = roxy.child_config(padre, purpose="hijo")
    assert cfg["callbacks"] == [roxy]
    assert cfg["metadata"]["roxy_parent"] == roxy.agent_id_for(padre)


def test_todos_los_nodos_comparten_la_sesion(roxy, registro):
    chain_start(roxy, uuid4(), purpose="a")
    chain_start(roxy, uuid4(), purpose="b")
    sesiones = {c["sessionId"] for c in registro.cuerpos}
    assert sesiones == {roxy.session_id}


def test_si_la_api_falla_el_agente_sigue():
    """La traza es observacion: perderla no puede tumbar al agente."""
    with requests_mock.Mocker() as m:
        m.post(f"{API}/agents", status_code=500)
        roxy = Roxy(api_url=API)
        chain_start(roxy, uuid4(), purpose="tarea")
        assert roxy.agent_id_for(uuid4()) is None


def test_si_la_api_esta_caida_el_agente_sigue():
    with requests_mock.Mocker() as m:
        m.post(f"{API}/agents", exc=requests.exceptions.ConnectionError)
        roxy = Roxy(api_url=API)
        chain_start(roxy, uuid4(), purpose="tarea")


# --- control de acceso ---------------------------------------------------

def test_guard_denegado(roxy):
    with requests_mock.Mocker() as m:
        m.post(f"{GATEWAY}/v1/evaluate", status_code=403, text="")
        assert roxy.guard(action="update", payload={}).allowed is False


def test_guard_aprobado(roxy):
    with requests_mock.Mocker() as m:
        m.post(f"{GATEWAY}/v1/evaluate", status_code=200, json={"ok": 1})
        assert roxy.guard(action="update", payload={}).allowed is True


def test_guard_no_aprueba_si_el_gateway_esta_caido(roxy):
    with requests_mock.Mocker() as m:
        m.post(f"{GATEWAY}/v1/evaluate", status_code=504, text="<html>error</html>")
        with pytest.raises(RoxyUnavailable):
            roxy.guard(action="update", payload={})


def test_guard_no_aprueba_con_html_y_status_2xx(roxy):
    """Un CDN puede responder su pagina de error con 200; leerla como
    aprobacion seria conceder permiso porque la seguridad se cayo."""
    with requests_mock.Mocker() as m:
        m.post(f"{GATEWAY}/v1/evaluate", status_code=200,
               text="<!doctype html>", headers={"Content-Type": "text/html"})
        with pytest.raises(RoxyUnavailable):
            roxy.guard(action="update", payload={})


def test_guard_manda_la_identidad_del_agente(roxy, registro):
    run = uuid4()
    chain_start(roxy, run, purpose="agente")
    with requests_mock.Mocker() as m:
        m.post(f"{GATEWAY}/v1/evaluate", status_code=403, text="")
        roxy.guard(action="update", payload={}, run_id=run)
        assert m.last_request.headers["X-Roxy-Agent-Run"] == roxy.agent_id_for(run)


# --- lectura --------------------------------------------------------------

def test_lineage_va_de_la_raiz_al_nodo():
    with requests_mock.Mocker() as m:
        m.get(f"{API}/agents", json=[
            {"_id": "a", "parentId": None, "purpose": "raiz", "sessionId": "s"},
            {"_id": "b", "parentId": "a", "purpose": "medio", "sessionId": "s"},
            {"_id": "c", "parentId": "b", "purpose": "hoja", "sessionId": "s"},
        ])
        assert Roxy(api_url=API).lineage("c") == ["a", "b", "c"]


def test_lineage_no_se_cuelga_con_un_ciclo():
    with requests_mock.Mocker() as m:
        m.get(f"{API}/agents", json=[
            {"_id": "a", "parentId": "b", "purpose": "", "sessionId": "s"},
            {"_id": "b", "parentId": "a", "purpose": "", "sessionId": "s"},
        ])
        assert len(Roxy(api_url=API).lineage("a")) == 2


# --- delegacion entre procesos -------------------------------------------

def test_headers_llevan_sesion_y_padre(roxy):
    run = uuid4()
    chain_start(roxy, run, purpose="agente")
    headers = roxy.headers_to_send(run)
    assert headers["X-Roxy-Session"] == roxy.session_id
    assert headers["X-Roxy-Parent"] == roxy.agent_id_for(run)


def test_receive_adopta_la_sesion_del_que_delega(roxy):
    roxy.receive({"X-Roxy-Session": "sesion-remota"}, lambda: None)
    assert roxy.session_id == "sesion-remota"


def test_no_registra_el_purpose_heredado(roxy, registro):
    """LangChain copia el metadata a cada chain anidado: el prompt, el
    parser y el scratchpad llegan con el mismo purpose del agente. Sin este
    filtro un solo agente aparecia como decenas de nodos."""
    agente = uuid4()
    chain_start(roxy, agente, purpose="Conciliar INV-1005")

    # lo que LangChain dispara adentro, con el metadata heredado
    for _ in range(5):
        interno = uuid4()
        chain_start(roxy, interno, parent_run_id=agente, purpose="Conciliar INV-1005")

    assert len(registro.cuerpos) == 1


def test_un_purpose_distinto_si_es_un_agente_nuevo(roxy, registro):
    padre = uuid4()
    chain_start(roxy, padre, purpose="Delegar grupo A")
    chain_start(roxy, uuid4(), parent_run_id=padre, purpose="Conciliar INV-1005")
    assert len(registro.cuerpos) == 2


def test_avisa_cuando_no_puede_registrar(caplog):
    """Fail-open no puede ser mudo: sin aviso, el usuario se entera recien
    al mirar un arbol vacio y no sabe por que."""
    with requests_mock.Mocker() as m:
        m.post(f"{API}/agents", status_code=404, text="not found")
        roxy = Roxy(api_url=API)
        with caplog.at_level("WARNING", logger="roxy"):
            chain_start(roxy, uuid4(), purpose="tarea")
    assert "no se pudo registrar la traza" in caplog.text
    assert API in caplog.text


def test_el_aviso_no_se_repite(caplog):
    """Una corrida con decenas de nodos no debe escupir decenas de avisos."""
    with requests_mock.Mocker() as m:
        m.post(f"{API}/agents", status_code=404, text="not found")
        roxy = Roxy(api_url=API)
        with caplog.at_level("WARNING", logger="roxy"):
            for _ in range(5):
                chain_start(roxy, uuid4(), purpose="tarea")
    assert caplog.text.count("no se pudo registrar la traza") == 1


def test_avisa_tambien_si_la_api_esta_caida(caplog):
    with requests_mock.Mocker() as m:
        m.post(f"{API}/agents", exc=requests.exceptions.ConnectionError)
        roxy = Roxy(api_url=API)
        with caplog.at_level("WARNING", logger="roxy"):
            chain_start(roxy, uuid4(), purpose="tarea")
    assert "no se pudo registrar la traza" in caplog.text
