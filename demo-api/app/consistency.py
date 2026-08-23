from typing import Any, Dict, List

EPSILON = 1e-6


def _violation(
    invoice_id: Any, rule: str, expected: Any, found: Any, detail: str
) -> Dict[str, Any]:
    return {
        "invoice_id": invoice_id,
        "rule": rule,
        "expected": expected,
        "found": found,
        "detail": detail,
    }


def _missing_field_violation(invoice_id: Any, field: str) -> Dict[str, Any]:
    return _violation(
        invoice_id,
        "malformed_invoice",
        f"{field} present",
        f"{field} missing or null",
        f"invoice has no usable {field} (missing or null)",
    )


def _invoice_id(invoice: Any) -> Any:
    try:
        return invoice.get("_id", "<unknown>") if isinstance(invoice, dict) else "<unknown>"
    except Exception:
        return "<unknown>"


def check_invoice(invoice: Dict[str, Any]) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    invoice_id = _invoice_id(invoice)

    line_items = invoice.get("line_items")
    if line_items is None:
        violations.append(_missing_field_violation(invoice_id, "line_items"))
        line_items = []

    computed_total = 0
    for item in line_items:
        if not isinstance(item, dict) or any(
            item.get(key) is None for key in ("qty", "unit_price", "subtotal")
        ):
            violations.append(
                _violation(
                    invoice_id,
                    "malformed_line_item",
                    "qty, unit_price and subtotal present",
                    repr(item),
                    "line item is missing (or has null) qty/unit_price/subtotal",
                )
            )
            continue

        expected_subtotal = item["qty"] * item["unit_price"]
        found_subtotal = item["subtotal"]
        if abs(expected_subtotal - found_subtotal) > EPSILON:
            sku = item.get("sku", "<unknown>")
            violations.append(
                _violation(
                    invoice_id,
                    "line_item_subtotal_mismatch",
                    expected_subtotal,
                    found_subtotal,
                    f"sku {sku}: expected subtotal "
                    f"{expected_subtotal} (qty {item['qty']} x unit_price "
                    f"{item['unit_price']}), found {found_subtotal}",
                )
            )
        computed_total += found_subtotal

    total = invoice.get("total")
    if total is None:
        violations.append(_missing_field_violation(invoice_id, "total"))
    elif not isinstance(total, (int, float)):
        violations.append(
            _violation(
                invoice_id,
                "malformed_invoice",
                "total is numeric",
                repr(total),
                f"invoice total has non-numeric type {type(total).__name__}",
            )
        )
    elif abs(computed_total - total) > EPSILON:
        violations.append(
            _violation(
                invoice_id,
                "total_mismatch",
                computed_total,
                total,
                f"sum of line_items[].subtotal is {computed_total}, "
                f"but total is {total}",
            )
        )

    status = invoice.get("status")
    if status is None:
        violations.append(_missing_field_violation(invoice_id, "status"))

    audit_log = invoice.get("audit_log") or []
    if status in ("issued", "paid") and len(audit_log) == 0:
        violations.append(
            _violation(
                invoice_id,
                "missing_audit_log",
                "non-empty audit_log",
                "empty audit_log",
                f"invoice status is '{status}' but audit_log is empty",
            )
        )

    return violations


def check_all(invoices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    for invoice in invoices:
        try:
            violations.extend(check_invoice(invoice))
        except Exception as exc:
            # Defense in depth: a single unanticipated corruption shape must
            # never take down consistency reporting for the whole collection.
            violations.append(
                _violation(
                    _invoice_id(invoice),
                    "unreadable_invoice",
                    "invoice can be evaluated",
                    str(exc),
                    f"invoice could not be evaluated for consistency: {exc}",
                )
            )
    return violations
