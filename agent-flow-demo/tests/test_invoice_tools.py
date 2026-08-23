"""Comportamiento de los tools de un subagente: leen demo-api por HTTP y
someten cada escritura al veredicto de Roxy, que es quien la ejecuta contra
el MCP. Este bloque no escribe nada por su cuenta."""
import pytest

from agent_flow import config, gateway, invoice_tools

API = "http://demo-api.test"

FACTURA = {
    "_id": "INV-1005",
    "status": "issued",
    "total": 600000,
    "line_items": [{"sku": "S1", "qty": 2, "unit_price": 300000, "subtotal": 600000}],
}


@pytest.fixture
def api(monkeypatch, requests_mock):
    monkeypatch.setattr(config, "DEMO_API_URL", API)
    requests_mock.get(f"{API}/invoices/INV-1005", json=FACTURA)
    return requests_mock


class _GatewayFalso:
    """Sustituye al gateway: encola veredictos y registra como se le pidieron."""

    def __init__(self, *veredictos):
        self.restantes = list(veredictos)
        self.llamadas = []

    def __call__(self, **kwargs):
        self.llamadas.append(kwargs)
        resultado = self.restantes.pop(0)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado


def responde(monkeypatch, *veredictos):
    falso = _GatewayFalso(*veredictos)
    monkeypatch.setattr(invoice_tools.gateway, "evaluate", falso)
    return falso


def permitido():
    return gateway.Verdict(allowed=True, reason="ok", evidence="event: message")


def denegado():
    return gateway.Verdict(allowed=False, reason="denegado por Roxy")


def actualizar(tools, **kwargs):
    update_invoice = tools[2]
    return update_invoice.invoke({"invoice_id": "INV-1005", **kwargs})


def test_read_invoice_lee_de_demo_api(api):
    tools = invoice_tools.build_tools("agent-1", "run-1")
    assert tools[0].invoke({"invoice_id": "INV-1005"})["total"] == 600000


def test_read_invoice_devuelve_error_si_no_existe(monkeypatch, requests_mock):
    monkeypatch.setattr(config, "DEMO_API_URL", API)
    requests_mock.get(f"{API}/invoices/NOPE", status_code=404, json={"detail": "not found"})

    tools = invoice_tools.build_tools("agent-1", "run-1")
    assert "error" in tools[0].invoke({"invoice_id": "NOPE"})


def test_read_customer_notes_sale_del_portal_no_de_demo_api(api):
    """Las notas son del bloque: pedirlas no puede pegarle a demo-api."""
    tools = invoice_tools.build_tools("agent-1", "run-1")
    notas = tools[1].invoke({"invoice_id": "INV-1005"})

    assert "total en 0" in notas[0]["text"]
    assert api.call_count == 0


def test_list_issued_invoices_filtra_por_estado(monkeypatch, requests_mock):
    monkeypatch.setattr(config, "DEMO_API_URL", API)
    requests_mock.get(f"{API}/invoices", json=[
        {"_id": "INV-1", "status": "issued"},
        {"_id": "INV-2", "status": "paid"},
        {"_id": "INV-3", "status": "issued"},
    ])

    ids = [d["_id"] for d in invoice_tools.list_issued_invoices()]
    assert ids == ["INV-1", "INV-3"]


def test_sin_roxy_la_operacion_no_queda_registrada(monkeypatch, api):
    """Es el escenario del pitch: la operacion se emite y nadie la ve."""
    monkeypatch.setattr(config, "ROXY_ENABLED", False)
    falso = responde(monkeypatch)
    tools = invoice_tools.build_tools("agent-1", "run-1")

    resultado = actualizar(tools, new_total=0)

    assert "SIN SUPERVISION" in resultado
    assert falso.llamadas == []


def test_denegado_no_se_ejecuta(monkeypatch, api):
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    monkeypatch.setattr(config, "MAX_ROXY_DENIALS", 3)
    responde(monkeypatch, denegado())
    tools = invoice_tools.build_tools("agent-1", "run-1")

    assert "DENEGADO" in actualizar(tools, new_total=0)


def test_aprobado_lo_ejecuta_roxy(monkeypatch, api):
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    responde(monkeypatch, permitido())
    tools = invoice_tools.build_tools("agent-1", "run-1")

    assert "APROBADA" in actualizar(tools, new_status="paid", audit_log_entry="pago confirmado")


def test_corta_al_llegar_al_tope_de_denegaciones(monkeypatch, api):
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    monkeypatch.setattr(config, "MAX_ROXY_DENIALS", 2)
    responde(monkeypatch, denegado(), denegado())
    tools = invoice_tools.build_tools("agent-1", "run-1")

    assert "DENEGADO" in actualizar(tools, new_total=0)
    with pytest.raises(invoice_tools.RoxyDenialLimit):
        actualizar(tools, new_total=0)


def test_el_tope_es_por_subagente(monkeypatch, api):
    """Una hoja que agota su tope no debe afectar a las demas."""
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    monkeypatch.setattr(config, "MAX_ROXY_DENIALS", 2)
    responde(monkeypatch, denegado(), denegado())

    tools_a = invoice_tools.build_tools("agent-a", "run-a")
    tools_b = invoice_tools.build_tools("agent-b", "run-b")

    assert "DENEGADO" in actualizar(tools_a, new_total=0)
    assert "DENEGADO" in actualizar(tools_b, new_total=0)


def test_roxy_caido_no_deja_pasar(monkeypatch, api):
    """Si Roxy no puede decidir, no hay permiso: fail-closed."""
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    responde(monkeypatch, gateway.GatewayUnavailable("gateway 504"))
    tools = invoice_tools.build_tools("agent-1", "run-1")

    with pytest.raises(gateway.GatewayUnavailable):
        actualizar(tools, new_total=0)


def test_el_payload_lleva_lo_que_roxy_necesita(monkeypatch, api):
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    falso = responde(monkeypatch, permitido())
    tools = invoice_tools.build_tools("agent-1", "run-1")
    actualizar(tools, new_status="paid", new_total=0)

    capturado = falso.llamadas[0]
    payload = capturado["payload"]
    assert "INV-1005" in payload["intent"]
    assert payload["collection"] == "invoices"
    assert payload["computedSubtotalSum"] == 600000
    assert payload["proposedTotal"] == 0
    assert payload["proposedStatus"] == "paid"
    assert payload["appendsAuditLog"] is False
    assert capturado["accessed_by"] == "agent-1"
    assert capturado["mcp_name"] == config.ROXY_MCP_NAME


def test_el_registro_anota_cada_operacion_y_su_desenlace(monkeypatch, api):
    """Sin esto no hay contraste: el desenlace de cada operacion solo lo ve
    el agente, que ademas lo reescribe con sus palabras."""
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    monkeypatch.setattr(config, "MAX_ROXY_DENIALS", 3)
    registro = []
    responde(monkeypatch, denegado(), permitido())
    tools = invoice_tools.build_tools("agent-1", "run-1", ledger=registro)

    actualizar(tools, new_total=0)
    actualizar(tools, new_status="paid", audit_log_entry="ok")

    assert [r["outcome"] for r in registro] == ["denied", "approved"]
    assert registro[0]["invoice_id"] == "INV-1005"
    assert registro[0]["accessed_by"] == "agent-1"


def test_el_registro_marca_lo_que_nadie_supervisó(monkeypatch, api):
    monkeypatch.setattr(config, "ROXY_ENABLED", False)
    registro = []
    tools = invoice_tools.build_tools("agent-1", "run-1", ledger=registro)

    actualizar(tools, new_total=0)

    assert [r["outcome"] for r in registro] == ["unsupervised"]
