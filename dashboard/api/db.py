import os

from pymongo import MongoClient
from pymongo.collection import Collection

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "roxy")

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client


def get_security_collection() -> Collection:
    return get_client()[MONGO_DB]["security"]


def get_agents_collection() -> Collection:
    return get_client()[MONGO_DB]["agents"]
