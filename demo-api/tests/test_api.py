from app.db import get_invoices_collection


def test_list_invoices_returns_seed(client):
    res = client.get("/invoices")
    assert res.status_code == 200
    assert len(res.json()) == 30


def test_get_invoice_by_id(client):
    res = client.get("/invoices/INV-1001")
    assert res.status_code == 200
    assert res.json()["customer"] == "Distribuidora Andina SAS"


def test_get_invoice_not_found(client):
    res = client.get("/invoices/NOPE")
    assert res.status_code == 404


def test_health_consistency_green_on_clean_seed(client):
    res = client.get("/health/consistency")
    assert res.status_code == 200
    body = res.json()
    assert body["consistent"] is True
    assert body["checked"] == 30
    assert body["violations"] == []


def test_health_consistency_flags_corrupted_total(client):
    get_invoices_collection().update_one({"_id": "INV-1001"}, {"$set": {"total": 1}})

    res = client.get("/health/consistency")
    assert res.status_code == 409
    body = res.json()
    assert body["consistent"] is False
    violation = body["violations"][0]
    assert violation["invoice_id"] == "INV-1001"
    assert violation["rule"] == "total_mismatch"
    assert violation["found"] == 1


def test_admin_reset_restores_consistency(client):
    get_invoices_collection().update_one({"_id": "INV-1001"}, {"$set": {"total": 1}})
    assert client.get("/health/consistency").status_code == 409

    res = client.post("/admin/reset")
    assert res.status_code == 200
    assert res.json() == {"reset": True, "count": 30}

    res = client.get("/health/consistency")
    assert res.status_code == 200
    assert res.json()["consistent"] is True


def test_admin_reset_is_idempotent(client):
    first = client.post("/admin/reset").json()
    second = client.post("/admin/reset").json()
    assert first == second == {"reset": True, "count": 30}
