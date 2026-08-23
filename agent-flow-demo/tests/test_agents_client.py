"""Registro del arbol de delegacion contra la API del dashboard."""
import pytest
import requests
import requests_mock

from agent_flow import agents_client, config

URL = f"{config.DASHBOARD_API_URL}/agents"
OBJECT_ID = "6a8a4e1aadfda2e92dbca45e"


def test_devuelve_el_id_que_asigna_la_api():
    with requests_mock.Mocker() as m:
        m.post(URL, status_code=201, json={"_id": OBJECT_ID, "purpose": "p",
                                           "parentId": None, "sessionId": "s"})
        assert agents_client.register(purpose="p", session_id="s") == OBJECT_ID


def test_manda_el_contrato_que_la_api_espera():
    with requests_mock.Mocker() as m:
        m.post(URL, status_code=201, json={"_id": OBJECT_ID, "purpose": "p",
                                           "parentId": OBJECT_ID, "sessionId": "s"})
        agents_client.register(purpose="p", session_id="s", parent_id=OBJECT_ID)
        body = m.last_request.json()
        assert set(body) == {"purpose", "sessionId", "parentId"}
        assert body["parentId"] == OBJECT_ID


def test_la_raiz_va_sin_padre():
    with requests_mock.Mocker() as m:
        m.post(URL, status_code=201, json={"_id": OBJECT_ID, "purpose": "p",
                                           "parentId": None, "sessionId": "s"})
        agents_client.register(purpose="p", session_id="s")
        assert m.last_request.json()["parentId"] is None


@pytest.mark.parametrize("status", [400, 404, 500, 503])
def test_un_error_no_tumba_la_corrida(status):
    """La trazabilidad es observacion: si la API falla se pierde el nodo,
    no la corrida."""
    with requests_mock.Mocker() as m:
        m.post(URL, status_code=status, text="boom")
        assert agents_client.register(purpose="p", session_id="s") is None


def test_la_api_caida_no_tumba_la_corrida():
    with requests_mock.Mocker() as m:
        m.post(URL, exc=requests.exceptions.ConnectionError)
        assert agents_client.register(purpose="p", session_id="s") is None


def test_un_201_con_html_no_rompe():
    """El CDN puede responder su pagina de error; sin _id no hay nodo."""
    with requests_mock.Mocker() as m:
        m.post(URL, status_code=201, text="<html>error</html>")
        assert agents_client.register(purpose="p", session_id="s") is None


def test_cada_sesion_tiene_su_id():
    a, b = agents_client.new_session_id(), agents_client.new_session_id()
    assert a != b and len(a) == 36


def test_fetch_tree_pide_por_sesion():
    with requests_mock.Mocker() as m:
        m.get(URL, status_code=200, json=[{"_id": OBJECT_ID, "purpose": "p",
                                           "parentId": None, "sessionId": "s1"}])
        nodos = agents_client.fetch_tree("s1")
        assert m.last_request.qs["sessionid"] == ["s1"]
        assert nodos[0]["_id"] == OBJECT_ID
