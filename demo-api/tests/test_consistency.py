from app.consistency import check_all, check_invoice


def _invoice(**overrides):
    base = {
        "_id": "INV-TEST",
        "customer": "Test SAS",
        "line_items": [
            {"sku": "SKU-1", "qty": 2, "unit_price": 1000, "subtotal": 2000},
        ],
        "total": 2000,
        "status": "paid",
        "audit_log": [{"ts": "2026-01-01T00:00:00Z", "action": "paid", "actor": "system"}],
    }
    base.update(overrides)
    return base


def test_consistent_invoice_has_no_violations():
    assert check_invoice(_invoice()) == []


def test_total_mismatch_detected():
    violations = check_invoice(_invoice(total=999))
    assert len(violations) == 1
    violation = violations[0]
    assert violation["rule"] == "total_mismatch"
    assert violation["invoice_id"] == "INV-TEST"
    assert violation["expected"] == 2000
    assert violation["found"] == 999


def test_line_item_subtotal_mismatch_detected():
    invoice = _invoice(
        line_items=[{"sku": "SKU-1", "qty": 2, "unit_price": 1000, "subtotal": 5000}],
        total=5000,
    )
    violations = check_invoice(invoice)
    rules = {v["rule"] for v in violations}
    assert "line_item_subtotal_mismatch" in rules


def test_missing_audit_log_on_issued_invoice():
    invoice = _invoice(status="issued", audit_log=[])
    violations = check_invoice(invoice)
    assert any(v["rule"] == "missing_audit_log" for v in violations)


def test_draft_invoice_allows_empty_audit_log():
    invoice = _invoice(status="draft", audit_log=[])
    assert check_invoice(invoice) == []


def test_check_all_aggregates_across_invoices():
    good = _invoice()
    bad = _invoice(_id="INV-BAD", total=1)
    violations = check_all([good, bad])
    assert len(violations) == 1
    assert violations[0]["invoice_id"] == "INV-BAD"


def test_null_line_items_reported_as_violation_not_crash():
    invoice = _invoice(line_items=None)
    violations = check_invoice(invoice)
    assert any(v["rule"] == "malformed_invoice" for v in violations)


def test_null_total_reported_as_violation_not_crash():
    invoice = _invoice(total=None)
    violations = check_invoice(invoice)
    assert any(v["rule"] == "malformed_invoice" for v in violations)


def test_non_numeric_total_reported_as_violation_not_crash():
    invoice = _invoice(total="2000")
    violations = check_invoice(invoice)
    assert any(v["rule"] == "malformed_invoice" for v in violations)


def test_null_audit_log_reported_as_violation_not_crash():
    invoice = _invoice(status="issued", audit_log=None)
    violations = check_invoice(invoice)
    assert any(v["rule"] == "missing_audit_log" for v in violations)


def test_line_item_missing_required_key_reported_as_violation_not_crash():
    invoice = _invoice(line_items=[{"sku": "SKU-1", "qty": 2, "subtotal": 2000}])
    violations = check_invoice(invoice)
    assert any(v["rule"] == "malformed_line_item" for v in violations)


def test_line_item_missing_sku_still_reports_subtotal_mismatch():
    invoice = _invoice(
        line_items=[{"qty": 2, "unit_price": 1000, "subtotal": 5000}],
        total=5000,
    )
    violations = check_invoice(invoice)
    assert any(v["rule"] == "line_item_subtotal_mismatch" for v in violations)


def test_missing_status_reported_as_violation():
    invoice = _invoice(status=None)
    violations = check_invoice(invoice)
    assert any(v["rule"] == "malformed_invoice" for v in violations)


def test_both_total_and_line_items_missing_is_not_silently_consistent():
    invoice = _invoice(line_items=None, total=None)
    violations = check_invoice(invoice)
    assert violations != []


def test_check_all_isolates_one_broken_invoice_from_the_rest():
    class Explodes(dict):
        def get(self, *a, **k):
            raise RuntimeError("boom")

    broken = Explodes(_invoice(_id="INV-BROKEN"))
    good = _invoice()
    violations = check_all([broken, good])
    assert any(v["rule"] == "unreadable_invoice" for v in violations)
