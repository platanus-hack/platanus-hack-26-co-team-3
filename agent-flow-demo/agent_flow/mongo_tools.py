from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from pymongo import MongoClient

from roxy import RoxyUnavailable

from agent_flow import config

_client = MongoClient(config.MONGO_URI)
_db = _client[config.BILLING_DB_NAME]
_invoices = _db["invoices"]


def list_issued_invoices() -> List[Dict[str, Any]]:
    return list(_invoices.find({"status": "issued"}, {"_id": 1, "customer": 1, "total": 1}))


class RoxyDenialLimit(Exception):
    """El subagente insistio con operaciones que Roxy denego hasta pasarse
    del tope. Corta la ejecucion de ese subagente: reintentar mas no lo va a
    acercar a una operacion valida."""


def build_tools(accessed_by: str, run_id: str, roxy=None):
    """Tools de un subagente sobre demo_billing.invoices ("MCP de Mongo").

    Roxy V2 (roxy-gateway/README.md) le pega al MCP el mismo cuando aprueba,
    y `invoices-mcp` esta registrado apuntando a demo-api por HTTP: esa
    llamada existe, pero es de lectura. El veredicto queda logueado en
    roxy.security -es lo que ve el dashboard- y el write sobre Mongo lo
    ejecuta este tool.

    TODO: cuando demo-api exponga la escritura, el write deberia salir de la
    respuesta de Roxy y no repetirse aca.
    """
    denials = {"count": 0}

    @tool
    def read_invoice(invoice_id: str) -> Dict[str, Any]:
        """Lee el detalle completo de una factura por _id: line_items, total,
        status, audit_log y cualquier nota adjunta (notes) del cliente o del
        proveedor."""
        doc = _invoices.find_one({"_id": invoice_id})
        if doc is None:
            return {"error": f"invoice {invoice_id} not found"}
        return doc

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
        doc = _invoices.find_one({"_id": invoice_id})
        if doc is None:
            return f"error: invoice {invoice_id} not found"

        computed_subtotal_sum = sum(li["subtotal"] for li in doc.get("line_items", []))
        proposed_total = new_total if new_total is not None else doc["total"]
        proposed_status = new_status if new_status is not None else doc["status"]

        payload = {
            "invoiceId": invoice_id,
            "currentStatus": doc["status"],
            "currentTotal": doc["total"],
            "computedSubtotalSum": computed_subtotal_sum,
            "proposedStatus": proposed_status,
            "proposedTotal": proposed_total,
            "appendsAuditLog": audit_log_entry is not None,
        }

        if config.ROXY_ENABLED and roxy is not None:
            decision = roxy.guard(
                action="update_invoice",
                payload=payload,
                run_id=run_id,
                accessed_by=accessed_by,
                mcp_name=config.ROXY_MCP_NAME,
            )
            if not decision.allowed:
                denials["count"] += 1
                # El texto de la denegacion solo lo ve el agente: sin esto la
                # corrida con Roxy se ve igual que la de sin, salvo por el
                # dano que no ocurrio.
                print(f"  [Roxy] DENEGADO {invoice_id} ({accessed_by}): {decision.reason}")
                if denials["count"] >= config.MAX_ROXY_DENIALS:
                    raise RoxyDenialLimit(
                        f"{denials['count']} operaciones denegadas por Roxy "
                        f"sobre {invoice_id}; ultima: {decision.reason}"
                    )
                return f"DENEGADO por Roxy: {decision.reason}"

        update: Dict[str, Any] = {}
        if new_status is not None:
            update["status"] = new_status
        if new_total is not None:
            update["total"] = new_total

        ops: Dict[str, Any] = {}
        if update:
            ops["$set"] = update
        if audit_log_entry is not None:
            ops["$push"] = {
                "audit_log": {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "action": new_status or "update",
                    "actor": accessed_by,
                    "detail": audit_log_entry,
                }
            }
        if ops:
            _invoices.update_one({"_id": invoice_id}, ops)

        return (f"OK: invoice {invoice_id} actualizada (status={proposed_status}, "
                f"total={proposed_total})")

    return [read_invoice, update_invoice]
