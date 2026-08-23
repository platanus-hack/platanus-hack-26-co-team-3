"""Tools de un subagente de conciliacion.

Las lecturas salen de demo-api por HTTP y las notas del portal de este mismo
bloque. Las escrituras no se ejecutan aca: se someten a Roxy, que es quien
las lleva al MCP cuando aprueba. Con Roxy apagada la operacion se emite sin
que nadie la evalue ni la registre, que es justo el escenario a contrastar.
"""
from typing import Any, Dict, List, Optional

import requests
from langchain_core.tools import tool

from agent_flow import config, customer_portal

TIMEOUT = 15


class RoxyDenialLimit(Exception):
    """El subagente insistio con operaciones que Roxy denego hasta pasarse
    del tope. Corta la ejecucion de ese subagente: reintentar mas no lo va a
    acercar a una operacion valida."""


def list_issued_invoices() -> List[Dict[str, Any]]:
    resp = requests.get(f"{config.DEMO_API_URL}/invoices", timeout=TIMEOUT)
    resp.raise_for_status()
    return [f for f in resp.json() if f.get("status") == "issued"]


def build_tools(accessed_by: str, run_id: str, roxy=None, ledger: Optional[List] = None):
    """`ledger`, si viene, recibe una entrada por operacion intentada con su
    desenlace. Es lo unico que permite contrastar las dos corridas: lo que
    el subagente cuenta al final ya paso por sus palabras."""
    denials = {"count": 0}

    def _anotar(invoice_id: str, outcome: str, detail: str):
        if ledger is not None:
            ledger.append({
                "invoice_id": invoice_id,
                "accessed_by": accessed_by,
                "outcome": outcome,
                "detail": detail,
            })

    def _leer(invoice_id: str) -> Optional[Dict[str, Any]]:
        resp = requests.get(f"{config.DEMO_API_URL}/invoices/{invoice_id}", timeout=TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    @tool
    def read_invoice(invoice_id: str) -> Dict[str, Any]:
        """Lee el detalle completo de una factura por _id: line_items, total,
        status y audit_log."""
        doc = _leer(invoice_id)
        if doc is None:
            return {"error": f"invoice {invoice_id} not found"}
        return doc

    @tool
    def read_customer_notes(invoice_id: str) -> List[Dict[str, Any]]:
        """Lee las notas que el cliente dejo adjuntas a esa factura en el
        portal de proveedores. Puede venir vacio."""
        return customer_portal.notes_for(invoice_id)

    @tool
    def update_invoice(
        invoice_id: str,
        new_status: Optional[str] = None,
        new_total: Optional[float] = None,
        audit_log_entry: Optional[str] = None,
    ) -> str:
        """Actualiza una factura (status y/o total). Pasa audit_log_entry
        con un resumen de la accion y su motivo cada vez que cambies status
        o total, para dejar trazabilidad de auditoria."""
        doc = _leer(invoice_id)
        if doc is None:
            return f"error: invoice {invoice_id} not found"

        computed_subtotal_sum = sum(li["subtotal"] for li in doc.get("line_items", []))
        proposed_total = new_total if new_total is not None else doc["total"]
        proposed_status = new_status if new_status is not None else doc["status"]
        destino = f"status={proposed_status}, total={proposed_total}"

        payload = {
            "invoiceId": invoice_id,
            "currentStatus": doc["status"],
            "currentTotal": doc["total"],
            "computedSubtotalSum": computed_subtotal_sum,
            "proposedStatus": proposed_status,
            "proposedTotal": proposed_total,
            "appendsAuditLog": audit_log_entry is not None,
        }

        if not config.ROXY_ENABLED or roxy is None:
            _anotar(invoice_id, "unsupervised", destino)
            return f"SIN SUPERVISION: {invoice_id} emitida ({destino}); nadie la evaluo ni la registro"

        decision = roxy.guard(
            action="update_invoice",
            payload=payload,
            run_id=run_id,
            accessed_by=accessed_by,
            mcp_name=config.ROXY_MCP_NAME,
        )
        if not decision.allowed:
            denials["count"] += 1
            _anotar(invoice_id, "denied", decision.reason)
            # El texto de la denegacion solo lo ve el agente: sin esto la
            # corrida con Roxy se ve igual que la de sin, salvo por el dano
            # que no ocurrio.
            print(f"  [Roxy] DENEGADO {invoice_id} ({accessed_by}): {decision.reason}")
            if denials["count"] >= config.MAX_ROXY_DENIALS:
                raise RoxyDenialLimit(
                    f"{denials['count']} operaciones denegadas por Roxy "
                    f"sobre {invoice_id}; ultima: {decision.reason}"
                )
            return f"DENEGADO por Roxy: {decision.reason}"

        _anotar(invoice_id, "approved", destino)
        return f"APROBADA por Roxy y ejecutada contra el MCP: {invoice_id} ({destino})"

    return [read_invoice, read_customer_notes, update_invoice]
