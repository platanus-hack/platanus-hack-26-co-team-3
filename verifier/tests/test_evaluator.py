"""El evaluador responde una sola pregunta por regla: este contexto de
peticion, ¿cae bajo lo que la regla prohibe? El contrato lo fija el gateway
(roxy-gateway/internal/policy/remote.go)."""
import pytest
from fastapi.testclient import TestClient

from evaluator import app

client = TestClient(app)

MCP = {
    "id": "aaa",
    "name": "invoices-mcp",
    "description": "facturas",
    "rules": [
        {"priority": 1, "instruction": "deny update_invoice si proposedTotal no es igual a computedSubtotalSum"},
        {"priority": 2, "instruction": "deny update_invoice si proposedStatus es 'paid' y appendsAuditLog es false"},
    ],
}


def evaluar(payload, action="update_invoice", accessed_by="agent-1"):
    res = client.post("/evaluate", json={
        "mcp": MCP,
        "request": {"accessedBy": accessed_by, "action": action, "payload": payload},
        "time": "2026-08-23T00:00:00Z",
    })
    assert res.status_code == 200
    return res.json()


def test_deniega_cuando_el_total_no_cuadra_con_las_lineas():
    veredicto = evaluar({
        "proposedTotal": 0, "computedSubtotalSum": 600000,
        "proposedStatus": "paid", "appendsAuditLog": True,
    })
    assert veredicto["allowed"] is False
    assert veredicto["violatedPriority"] == 1
    assert "600000" in veredicto["reason"]


def test_deniega_cerrar_como_pagada_sin_auditoria():
    veredicto = evaluar({
        "proposedTotal": 600000, "computedSubtotalSum": 600000,
        "proposedStatus": "paid", "appendsAuditLog": False,
    })
    assert veredicto["allowed"] is False
    assert veredicto["violatedPriority"] == 2


def test_la_regla_de_menor_prioridad_manda_cuando_se_violan_las_dos():
    """El gateway reporta una sola regla violada: tiene que ser la primera."""
    veredicto = evaluar({
        "proposedTotal": 0, "computedSubtotalSum": 600000,
        "proposedStatus": "paid", "appendsAuditLog": False,
    })
    assert veredicto["violatedPriority"] == 1


def test_permite_la_operacion_debida():
    veredicto = evaluar({
        "proposedTotal": 1560000, "computedSubtotalSum": 1560000,
        "proposedStatus": "paid", "appendsAuditLog": True,
    })
    assert veredicto["allowed"] is True
    assert veredicto["violatedPriority"] is None


def test_permite_cuando_el_payload_no_toca_ninguna_regla():
    assert evaluar({"proposedStatus": "issued"}, action="read")["allowed"] is True


def test_un_payload_vacio_no_rompe():
    assert evaluar(None)["allowed"] is True


def test_health():
    assert client.get("/health").status_code == 200
