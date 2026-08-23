"""Como se traduce la respuesta de Roxy en permiso o negacion.

Es la logica mas sensible del bloque: cualquier camino que devuelva
allowed=True sin que Roxy lo haya aprobado es un fail-open.
"""
import pytest
import requests_mock

from agent_flow import config, roxy_client

URL = f"{config.ROXY_URL}/v1/evaluate"


def evaluate():
    return roxy_client.evaluate(
        accessed_by="agent-subtask-INV-1005",
        run_id="run-1",
        action="update_invoice",
        payload={"invoiceId": "INV-1005"},
    )


def test_403_es_denegacion():
    with requests_mock.Mocker() as m:
        m.post(URL, status_code=403, text="")
        assert evaluate().allowed is False


def test_200_con_json_es_aprobacion():
    with requests_mock.Mocker() as m:
        m.post(URL, status_code=200, json={"updated": 1})
        decision = evaluate()
        assert decision.allowed is True
        assert decision.mcp_response == {"updated": 1}


@pytest.mark.parametrize("status", [404, 500, 502, 503, 504])
def test_errores_no_son_permiso(status):
    with requests_mock.Mocker() as m:
        m.post(URL, status_code=status, text="boom")
        with pytest.raises(roxy_client.RoxyUnavailable):
            evaluate()


def test_200_con_html_no_es_permiso():
    """CloudFront responde su pagina de error con status 2xx cuando el
    gateway esta caido; leer eso como aprobacion es el peor fail-open."""
    with requests_mock.Mocker() as m:
        m.post(URL, status_code=200, text="<!doctype html><html>error</html>",
               headers={"Content-Type": "text/html"})
        with pytest.raises(roxy_client.RoxyUnavailable):
            evaluate()


def test_manda_el_run_id_en_el_header():
    with requests_mock.Mocker() as m:
        m.post(URL, status_code=403, text="")
        evaluate()
        assert m.last_request.headers["X-Roxy-Agent-Run"] == "run-1"


def test_manda_el_contrato_que_roxy_espera():
    with requests_mock.Mocker() as m:
        m.post(URL, status_code=403, text="")
        evaluate()
        body = m.last_request.json()
        assert set(body) == {"mcpName", "accessedBy", "action", "payload"}
        assert body["mcpName"] == config.ROXY_MCP_NAME
        assert body["action"] == "update_invoice"
