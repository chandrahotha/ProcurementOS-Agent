"""Evidence coverage gate (F25): required-field coverage = backed/required."""

from __future__ import annotations

from typing import Any

REQUIRED_FIELDS = [
    "supplier",
    "unit_price",
    "currency",
    "uom",
    "quantity",
    "incoterm",
    "validity",
    "tax_mode",
]


def coverage(spans: list[dict[str, Any]], required: list[str] | None = None) -> dict[str, Any]:
    req = required or REQUIRED_FIELDS
    backed = {s.get("field_name") for s in spans if not s.get("instruction_flag")}
    have = [f for f in req if f in backed]
    missing = [f for f in req if f not in backed]
    pct = round(100 * len(have) / len(req)) if req else 100
    return {"pct": pct, "backed": have, "missing": missing}
