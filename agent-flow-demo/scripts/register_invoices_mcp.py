"""Upsert de la entrada `invoices-mcp` en roxy.mcps.

No modifica mongo-data/population/mcps.mock.json (bloque 1, Santiago) para
no pisar ese archivo desde otro bloque: populate.py hace `delete_many({})`
sobre toda la coleccion antes de insertar, asi que una entrada agregada solo
por este script desaparece si alguien vuelve a correr `mongo-data/run.sh`.
Si el equipo decide que `invoices-mcp` es parte fija de la demo, esta misma
entrada deberia migrar a mcps.mock.json.

Las reglas son el espejo textual de los tres invariantes que valida
demo-api (demo-api/app/consistency.py), para que el LLM evaluador de Roxy
tenga contra que comparar el payload que le manda agent_flow.mongo_tools.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent_flow import config  # noqa: E402

DOC = {
    "name": "invoices-mcp",
    "description": "MCP sobre demo_billing.invoices (demo-api, bloque 4) para el flujo agentico de conciliacion",
    "server": {"url": f"{config.MONGO_URI}/{config.BILLING_DB_NAME}", "protocol": "mcp"},
    "authorization": {
        "type": "bearer",
        "credentialsRef": "vault://roxy/mcp/invoices",
        "credentials": "tok_invoices_demo",
    },
    "rules": [
        {"priority": 1, "instruction": "deny update_invoice si proposedTotal no es igual a computedSubtotalSum"},
        {"priority": 2, "instruction": "deny update_invoice si proposedStatus es 'paid' y appendsAuditLog es false"},
        {"priority": 3, "instruction": "allow update_invoice si proposedTotal coincide con computedSubtotalSum y, cuando proposedStatus es 'paid', appendsAuditLog es true"},
    ],
}


def main():
    client = MongoClient(config.MONGO_URI)
    db = client[config.ROXY_DB_NAME]
    now = datetime.now(timezone.utc)
    doc = dict(DOC, updatedAt=now)
    db.mcps.update_one(
        {"name": DOC["name"]},
        {"$set": doc, "$setOnInsert": {"createdAt": now}},
        upsert=True,
    )
    print(f"invoices-mcp registrado en {config.ROXY_DB_NAME}.mcps")


if __name__ == "__main__":
    main()
