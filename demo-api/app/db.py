import os

from pymongo import MongoClient
from pymongo.collection import Collection

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "demo_billing")

_client = MongoClient(MONGO_URI)
_db = _client[DB_NAME]


def get_invoices_collection() -> Collection:
    return _db["invoices"]
