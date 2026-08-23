import json
from pathlib import Path
from typing import Any, Dict, List

from pymongo import ReplaceOne

from app.db import get_invoices_collection

SEED_PATH = Path(__file__).resolve().parent.parent / "seed" / "invoices.seed.json"


def load_seed_data() -> List[Dict[str, Any]]:
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def reset_db() -> int:
    collection = get_invoices_collection()
    invoices = load_seed_data()
    if invoices:
        # Upsert each seed invoice in place (instead of delete_many + insert_many)
        # so there is never a window where the collection is fully empty, and so
        # two concurrent resets both converge on the same clean state instead of
        # racing to insert_many the same _ids and raising a duplicate-key error.
        ops = []
        seed_ids = []
        for invoice in invoices:
            ops.append(ReplaceOne({"_id": invoice["_id"]}, invoice, upsert=True))
            seed_ids.append(invoice["_id"])
        collection.bulk_write(ops, ordered=False)
        collection.delete_many({"_id": {"$nin": seed_ids}})
    else:
        collection.delete_many({})
    return len(invoices)


def seed_if_empty() -> None:
    collection = get_invoices_collection()
    if collection.count_documents({}) == 0:
        reset_db()
