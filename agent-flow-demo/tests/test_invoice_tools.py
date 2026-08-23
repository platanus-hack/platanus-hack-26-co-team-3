"""Comportamiento de los tools de un subagente: leen demo-api por HTTP y
someten cada escritura al veredicto de Roxy, que es quien la ejecuta contra
el MCP. Este bloque no escribe nada por su cuenta."""
import pytest

from roxy import Decision, RoxyUnavailable

from agent_flow import config, invoice_tools

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


class _RoxyFalso:
    """Sustituye al SDK: encola veredictos y registra como se le pidieron."""

    def __init__(self, *decisiones):
        self.restantes = list(decisiones)
        self.llamadas = []

    def guard(self, **kwargs):
        self.llamadas.append(kwargs)
        resultado = self.restantes.pop(0)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado


def permitido():
    return Decision(allowed=True, reason="ok", response={"status": "paid"})


def denegado():
    return Decision(allowed=False, reason="viola la regla 1")


def actualizar(tools, **kwargs):
    update_invoice = tools[2]
    return update_invoice.invoke({"invoice_id": "INV-1005", **kwargs})


def test_read_invoice_lee_de_demo_api(api):
    tools = invoice_tools.build_tools("agent-1", "run-1", roxy=None)
    assert tools[0].invoke({"invoice_id": "INV-1005"})["total"] == 600000


def test_read_invoice_devuelve_error_si_no_existe(monkeypatch, requests_mock):
    monkeypatch.setattr(config, "DEMO_API_URL", API)
    requests_mock.get(f"{API}/invoices/NOPE", status_code=404, json={"detail": "not found"})

    tools = invoice_tools.build_tools("agent-1", "run-1", roxy=None)
    assert "error" in tools[0].invoke({"invoice_id": "NOPE"})


def test_read_customer_notes_sale_del_portal_no_de_demo_api(api):
    """Las notas son del bloque: pedirlas no puede pegarle a demo-api."""
    tools = invoice_tools.build_tools("agent-1", "run-1", roxy=None)
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
    falso = _RoxyFalso()
    tools = invoice_tools.build_tools("agent-1", "run-1", roxy=falso)

    resultado = actualizar(tools, new_total=0)

    assert "SIN SUPERVISION" in resultado
    assert falso.llamadas == []


def test_denegado_no_se_ejecuta(monkeypatch, api):
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    monkeypatch.setattr(config, "MAX_ROXY_DENIALS", 3)
    tools = invoice_tools.build_tools("agent-1", "run-1", roxy=_RoxyFalso(denegado()))

    assert "DENEGADO" in actualizar(tools, new_total=0)


def test_aprobado_lo_ejecuta_roxy(monkeypatch, api):
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    tools = invoice_tools.build_tools("agent-1", "run-1", roxy=_RoxyFalso(permitido()))

    assert "APROBADA" in actualizar(tools, new_status="paid", audit_log_entry="pago confirmado")


def test_corta_al_llegar_al_tope_de_denegaciones(monkeypatch, api):
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    monkeypatch.setattr(config, "MAX_ROXY_DENIALS", 2)
    falso = _RoxyFalso(denegado(), denegado())
    tools = invoice_tools.build_tools("agent-1", "run-1", roxy=falso)

    assert "DENEGADO" in actualizar(tools, new_total=0)
    with pytest.raises(invoice_tools.RoxyDenialLimit):
        actualizar(tools, new_total=0)


def test_el_tope_es_por_subagente(monkeypatch, api):
    """Una hoja que agota su tope no debe afectar a las demas."""
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    monkeypatch.setattr(config, "MAX_ROXY_DENIALS", 2)
    falso = _RoxyFalso(denegado(), denegado())

    tools_a = invoice_tools.build_tools("agent-a", "run-a", roxy=falso)
    tools_b = invoice_tools.build_tools("agent-b", "run-b", roxy=falso)

    assert "DENEGADO" in actualizar(tools_a, new_total=0)
    assert "DENEGADO" in actualizar(tools_b, new_total=0)


def test_roxy_caido_no_deja_pasar(monkeypatch, api):
    """Si Roxy no puede decidir, no hay permiso: fail-closed."""
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    falso = _RoxyFalso(RoxyUnavailable("gateway 504"))
    tools = invoice_tools.build_tools("agent-1", "run-1", roxy=falso)

    with pytest.raises(RoxyUnavailable):
        actualizar(tools, new_total=0)


def test_el_payload_lleva_lo_que_roxy_necesita(monkeypatch, api):
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    falso = _RoxyFalso(permitido())
    tools = invoice_tools.build_tools("agent-1", "run-1", roxy=falso)
    actualizar(tools, new_status="paid", new_total=0)

    capturado = falso.llamadas[0]
    payload = capturado["payload"]
    assert payload["computedSubtotalSum"] == 600000
    assert payload["proposedTotal"] == 0
    assert payload["proposedStatus"] == "paid"
    assert payload["appendsAuditLog"] is False
    assert capturado["accessed_by"] == "agent-1"
    assert capturado["run_id"] == "run-1"


def test_el_registro_anota_cada_operacion_y_su_desenlace(monkeypatch, api):
    """Sin esto no hay contraste: el desenlace de cada operacion solo lo ve
    el agente, que ademas lo reescribe con sus palabras."""
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    monkeypatch.setattr(config, "MAX_ROXY_DENIALS", 3)
    registro = []
    falso = _RoxyFalso(denegado(), permitido())
    tools = invoice_tools.build_tools("agent-1", "run-1", roxy=falso, ledger=registro)

    actualizar(tools, new_total=0)
    actualizar(tools, new_status="paid", audit_log_entry="ok")

    assert [r["outcome"] for r in registro] == ["denied", "approved"]
    assert registro[0]["invoice_id"] == "INV-1005"
    assert registro[0]["accessed_by"] == "agent-1"


def test_el_registro_marca_lo_que_nadie_supervisó(monkeypatch, api):
    monkeypatch.setattr(config, "ROXY_ENABLED", False)
    registro = []
    tools = invoice_tools.build_tools("agent-1", "run-1", roxy=None, ledger=registro)

    actualizar(tools, new_total=0)

    assert [r["outcome"] for r in registro] == ["unsupervised"]
