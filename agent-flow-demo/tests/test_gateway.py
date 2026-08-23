"""Cliente del gateway. Dos cosas que el SDK no contempla y que aca son la
realidad del despliegue: CloudFront convierte el 403 de una denegacion en un
200 con el HTML del dashboard, y el MCP de Mongo responde por SSE, no JSON."""
import pytest
import requests

from agent_flow import config, gateway

URL = "http://roxy.test"
HTML = "<!doctype html>\n<html lang=\"en\"><head><title>Roxy Dashboard</title></head></html>"


@pytest.fixture(autouse=True)
def gateway_url(monkeypatch):
    monkeypatch.setattr(config, "ROXY_URL", URL)


def evaluar():
    return gateway.evaluate(action="update_invoice", payload={"intent": "x"},
                            accessed_by="agent-1", mcp_name="mongo-catalog-mcp")


def test_un_403_es_una_denegacion(requests_mock):
    requests_mock.post(f"{URL}/v1/evaluate", status_code=403)
    assert evaluar().allowed is False


def test_el_403_enmascarado_por_cloudfront_tambien_es_denegacion(requests_mock):
    """CloudFront remapea 403 y 404 a 200 con /index.html para toda la
    distribucion, asi que la denegacion llega como el HTML del dashboard."""
    requests_mock.post(f"{URL}/v1/evaluate", status_code=200, text=HTML,
                       headers={"Content-Type": "text/html"})
    veredicto = evaluar()
    assert veredicto.allowed is False
    assert "CloudFront" in veredicto.reason


def test_una_respuesta_sse_del_mcp_es_una_aprobacion(requests_mock):
    """El MCP de Mongo contesta por event-stream: no es JSON y no por eso
    deja de ser una operacion aprobada y ejecutada."""
    requests_mock.post(f"{URL}/v1/evaluate", status_code=200,
                       text='event: message\ndata: {"result":{"content":[]}}',
                       headers={"Content-Type": "text/event-stream"})
    assert evaluar().allowed is True


def test_una_respuesta_json_tambien_es_aprobacion(requests_mock):
    requests_mock.post(f"{URL}/v1/evaluate", status_code=200, json={"_id": "INV-1"},
                       headers={"Content-Type": "application/json"})
    assert evaluar().allowed is True


def test_un_5xx_no_es_permiso(requests_mock):
    requests_mock.post(f"{URL}/v1/evaluate", status_code=502, json={"error": "mcp unavailable"})
    with pytest.raises(gateway.GatewayUnavailable):
        evaluar()


def test_un_gateway_inalcanzable_no_es_permiso(requests_mock):
    requests_mock.post(f"{URL}/v1/evaluate", exc=requests.ConnectionError)
    with pytest.raises(gateway.GatewayUnavailable):
        evaluar()


def test_manda_el_cuerpo_que_el_gateway_espera(requests_mock):
    m = requests_mock.post(f"{URL}/v1/evaluate", status_code=403)
    evaluar()
    cuerpo = m.last_request.json()
    assert cuerpo == {
        "mcpName": "mongo-catalog-mcp",
        "accessedBy": "agent-1",
        "action": "update_invoice",
        "payload": {"intent": "x"},
    }


def test_mcp_alcanzable_distingue_el_mcp_que_no_existe(requests_mock):
    """Un 404 tambien llega como HTML, asi que sin esta comprobacion no hay
    forma de distinguir 'lo denegaron' de 'ese MCP no esta registrado'."""
    requests_mock.post(f"{URL}/v1/evaluate", status_code=200, text=HTML,
                       headers={"Content-Type": "text/html"})
    assert gateway.mcp_reachable("mongo-catalog-mcp") is False


def test_mcp_alcanzable_cuando_el_mcp_contesta(requests_mock):
    requests_mock.post(f"{URL}/v1/evaluate", status_code=200,
                       text='event: message\ndata: {}',
                       headers={"Content-Type": "text/event-stream"})
    assert gateway.mcp_reachable("mongo-catalog-mcp") is True
