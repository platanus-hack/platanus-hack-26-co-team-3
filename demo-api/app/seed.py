import json
from pathlib import Path
from typing import Any, Dict, List

from app.db import get_invoices_collection

SEED_PATH = Path(__file__).resolve().parent.parent / "seed" / "invoices.seed.json"


def load_seed_data() -> List[Dict[str, Any]]:
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def reset_db() -> int:
    collection = get_invoices_collection()
    invoices = load_seed_data()
    collection.delete_many({})
    if invoices:
        collection.insert_many(invoices)
    return len(invoices)


def seed_if_empty() -> None:
    collection = get_invoices_collection()
    if collection.count_documents({}) == 0:
        reset_db()
