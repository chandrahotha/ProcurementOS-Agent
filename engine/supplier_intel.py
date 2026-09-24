"""supplier_intel: OTD/acceptance/PPM from own transactions (never inflated)."""

from __future__ import annotations

from typing import Any


def compute_kpis(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """transactions: [{on_time: bool, accepted: bool, qty: int, defects: int}]."""
    n = len(transactions)
    if n == 0:
        return {"n": 0, "otd_pct": 0.0, "accept_pct": 0.0, "ppm": 0, "thin": True}
    on_time = sum(1 for t in transactions if t.get("on_time"))
    accepted = sum(1 for t in transactions if t.get("accepted"))
    qty = sum(int(t.get("qty", 0)) for t in transactions)
    defects = sum(int(t.get("defects", 0)) for t in transactions)
    ppm = round(1_000_000 * defects / qty) if qty else 0
    return {
        "n": n,
        "otd_pct": round(100 * on_time / n, 1),
        "accept_pct": round(100 * accepted / n, 1),
        "ppm": ppm,
        "thin": n < 3,  # thin-data label, never inflated
    }
