import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

POPULATION_DIR = Path(__file__).resolve().parent

load_dotenv(POPULATION_DIR / ".env")

MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "roxy")

if not MONGO_URI:
    sys.exit("MONGO_URI is not set. Copy .env-example to .env and fill it in.")


def parse_datetime(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_mock(filename):
    with open(POPULATION_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def populate_mcps(db):
    docs = load_mock("mcps.mock.json")
    for doc in docs:
        doc["createdAt"] = parse_datetime(doc["createdAt"])
        doc["updatedAt"] = parse_datetime(doc["updatedAt"])

    db.mcps.delete_many({})
    result = db.mcps.insert_many(docs)

    return {doc["name"]: _id for doc, _id in zip(docs, result.inserted_ids)}


def populate_security(db, mcp_ids_by_name):
    docs = load_mock("security.mock.json")
    for doc in docs:
        doc["time"] = parse_datetime(doc["time"])
        doc["mcpId"] = mcp_ids_by_name[doc["mcpName"]]

    db.security.delete_many({})
    result = db.security.insert_many(docs)

    return len(result.inserted_ids)


def main():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]

    mcp_ids_by_name = populate_mcps(db)
    security_count = populate_security(db, mcp_ids_by_name)

    print(f"Inserted {len(mcp_ids_by_name)} documents into '{db.name}.mcps'")
    print(f"Inserted {security_count} documents into '{db.name}.security'")

    client.close()


if __name__ == "__main__":
    main()
