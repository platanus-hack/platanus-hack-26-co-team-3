from typing import Any, Dict, List

EPSILON = 1e-6


def check_invoice(invoice: Dict[str, Any]) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    invoice_id = invoice["_id"]

    computed_total = 0
    for item in invoice.get("line_items", []):
        expected_subtotal = item["qty"] * item["unit_price"]
        found_subtotal = item["subtotal"]
        if abs(expected_subtotal - found_subtotal) > EPSILON:
            violations.append(
                {
                    "invoice_id": invoice_id,
                    "rule": "line_item_subtotal_mismatch",
                    "expected": expected_subtotal,
                    "found": found_subtotal,
                    "detail": f"sku {item['sku']}: expected subtotal "
                    f"{expected_subtotal} (qty {item['qty']} x unit_price "
                    f"{item['unit_price']}), found {found_subtotal}",
                }
            )
        computed_total += found_subtotal

    total = invoice.get("total", 0)
    if abs(computed_total - total) > EPSILON:
        violations.append(
            {
                "invoice_id": invoice_id,
                "rule": "total_mismatch",
                "expected": computed_total,
                "found": total,
                "detail": f"sum of line_items[].subtotal is {computed_total}, "
                f"but total is {total}",
            }
        )

    status = invoice.get("status")
    audit_log = invoice.get("audit_log", [])
    if status in ("issued", "paid") and len(audit_log) == 0:
        violations.append(
            {
                "invoice_id": invoice_id,
                "rule": "missing_audit_log",
                "expected": "non-empty audit_log",
                "found": "empty audit_log",
                "detail": f"invoice status is '{status}' but audit_log is empty",
            }
        )

    return violations


def check_all(invoices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    for invoice in invoices:
        violations.extend(check_invoice(invoice))
    return violations
