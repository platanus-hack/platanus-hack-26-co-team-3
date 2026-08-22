from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from pymongo import MongoClient

from agent_flow import config, roxy_client

_client = MongoClient(config.MONGO_URI)
_db = _client[config.BILLING_DB_NAME]
_invoices = _db["invoices"]


def list_issued_invoices() -> List[Dict[str, Any]]:
    return list(_invoices.find({"status": "issued"}, {"_id": 1, "customer": 1, "total": 1}))


def _invoices_via_connection(connection: Dict[str, Any]):
    """Conecta usando la `connection` que Roxy entrega solo si aprobo (el
    exchange de token de idea.md): url + credenciales del MCP, no las
    credenciales fijas del proceso. Con Mongo local esto sigue siendo el
    mismo cluster, pero es la conexion que hay que abrir si `invoices-mcp`
    apuntara a un servidor real con su propio secreto."""
    client = MongoClient(connection["url"])
    db = client.get_default_database(default=config.BILLING_DB_NAME)
    return db["invoices"]


def build_tools(accessed_by: str, run_id: str):
    """Tools de un subagente sobre demo_billing.invoices ("MCP de Mongo").
    Roxy no reenvia la llamada al MCP real (ver roxy-gateway/README.md):
    solo evalua y, si aprueba, devuelve `connection` (url + credenciales del
    MCP). Este tool es el que abre esa conexion y ejecuta el write.
    """

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

        invoices_handle = _invoices
        connection_note = ""
        if config.ROXY_ENABLED:
            decision = roxy_client.evaluate(
                accessed_by=accessed_by,
                run_id=run_id,
                action="update_invoice",
                payload=payload,
            )
            if not decision.allowed:
                return f"DENEGADO por Roxy: {decision.reason}"
            auth = decision.connection["authorization"]
            invoices_handle = _invoices_via_connection(decision.connection)
            connection_note = f" via {auth['type']} token {auth.get('credentials', '?')}"

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
            invoices_handle.update_one({"_id": invoice_id}, ops)

        return (f"OK: invoice {invoice_id} actualizada (status={proposed_status}, "
                f"total={proposed_total}){connection_note}")

    return [read_invoice, update_invoice]
