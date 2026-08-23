"""Comportamiento del tool que toca las facturas: que respete el veredicto
de Roxy y que corte al subagente que insiste con operaciones denegadas."""
import pytest

from agent_flow import config, mongo_tools, roxy_client

FACTURA = {
    "_id": "INV-1005",
    "status": "issued",
    "total": 600000,
    "line_items": [{"sku": "S1", "qty": 2, "unit_price": 300000, "subtotal": 600000}],
}


@pytest.fixture
def escrituras(monkeypatch):
    """Corta el acceso real a Mongo y registra los writes que se intentaron."""
    hechas = []

    class ColeccionFalsa:
        def find_one(self, *a, **k):
            return dict(FACTURA)

        def update_one(self, filtro, ops):
            hechas.append((filtro, ops))

    monkeypatch.setattr(mongo_tools, "_invoices", ColeccionFalsa())
    return hechas


def responder(monkeypatch, *decisiones):
    """Encola las respuestas que dara Roxy, una por llamada."""
    restantes = list(decisiones)

    def falso_evaluate(**kwargs):
        resultado = restantes.pop(0)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado

    monkeypatch.setattr(roxy_client, "evaluate", falso_evaluate)


def permitido():
    return roxy_client.RoxyDecision(allowed=True, reason="ok", mcp_response={})


def denegado():
    return roxy_client.RoxyDecision(allowed=False, reason="viola la regla 1", mcp_response=None)


def actualizar(tools, **kwargs):
    update_invoice = tools[1]
    return update_invoice.invoke({"invoice_id": "INV-1005", **kwargs})


def test_sin_roxy_escribe_directo(monkeypatch, escrituras):
    monkeypatch.setattr(config, "ROXY_ENABLED", False)
    tools = mongo_tools.build_tools("agent-1", "run-1")
    resultado = actualizar(tools, new_total=0)
    assert "OK" in resultado
    assert len(escrituras) == 1


def test_denegado_no_escribe(monkeypatch, escrituras):
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    monkeypatch.setattr(config, "MAX_ROXY_DENIALS", 3)
    responder(monkeypatch, denegado())
    tools = mongo_tools.build_tools("agent-1", "run-1")
    resultado = actualizar(tools, new_total=0)
    assert "DENEGADO" in resultado
    assert escrituras == []


def test_aprobado_escribe(monkeypatch, escrituras):
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    responder(monkeypatch, permitido())
    tools = mongo_tools.build_tools("agent-1", "run-1")
    resultado = actualizar(tools, new_status="paid", audit_log_entry="pago confirmado")
    assert "OK" in resultado
    assert len(escrituras) == 1


def test_corta_al_llegar_al_tope_de_denegaciones(monkeypatch, escrituras):
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    monkeypatch.setattr(config, "MAX_ROXY_DENIALS", 2)
    responder(monkeypatch, denegado(), denegado())
    tools = mongo_tools.build_tools("agent-1", "run-1")

    assert "DENEGADO" in actualizar(tools, new_total=0)
    with pytest.raises(mongo_tools.RoxyDenialLimit):
        actualizar(tools, new_total=0)
    assert escrituras == []


def test_el_tope_es_por_subagente(monkeypatch, escrituras):
    """Una hoja que agota su tope no debe afectar a las demas."""
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    monkeypatch.setattr(config, "MAX_ROXY_DENIALS", 2)
    responder(monkeypatch, denegado(), denegado())

    tools_a = mongo_tools.build_tools("agent-a", "run-a")
    tools_b = mongo_tools.build_tools("agent-b", "run-b")

    assert "DENEGADO" in actualizar(tools_a, new_total=0)
    assert "DENEGADO" in actualizar(tools_b, new_total=0)
    assert escrituras == []


def test_roxy_caido_no_escribe(monkeypatch, escrituras):
    """Si Roxy no puede decidir, no hay permiso: fail-closed."""
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    responder(monkeypatch, roxy_client.RoxyUnavailable("gateway 504"))
    tools = mongo_tools.build_tools("agent-1", "run-1")
    with pytest.raises(roxy_client.RoxyUnavailable):
        actualizar(tools, new_total=0)
    assert escrituras == []


def test_el_payload_lleva_lo_que_roxy_necesita(monkeypatch, escrituras):
    monkeypatch.setattr(config, "ROXY_ENABLED", True)
    capturado = {}

    def falso_evaluate(**kwargs):
        capturado.update(kwargs)
        return permitido()

    monkeypatch.setattr(roxy_client, "evaluate", falso_evaluate)
    tools = mongo_tools.build_tools("agent-1", "run-1")
    actualizar(tools, new_status="paid", new_total=0)

    payload = capturado["payload"]
    assert payload["computedSubtotalSum"] == 600000
    assert payload["proposedTotal"] == 0
    assert payload["proposedStatus"] == "paid"
    assert payload["appendsAuditLog"] is False
    assert capturado["accessed_by"] == "agent-1"
    assert capturado["run_id"] == "run-1"
