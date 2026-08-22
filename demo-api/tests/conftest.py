import os

# Force (not setdefault) the test database name: this suite runs destructive
# operations (delete_many, insert_many, update_one) against it, so it must
# never silently fall through to a real DB_NAME already exported in the
# shell (e.g. after `source .env`, which sets DB_NAME=demo_billing). MONGO_URI
# needs no override here: app.db already defaults it the same way.
os.environ["DB_NAME"] = "demo_billing_test"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import reset_db


@pytest.fixture
def clean_db():
    # No teardown needed: the next test's reset_db() call fully restores the
    # exact seed state regardless of what this test mutated.
    reset_db()
    yield


@pytest.fixture
def client(clean_db):
    with TestClient(app) as c:
        yield c
