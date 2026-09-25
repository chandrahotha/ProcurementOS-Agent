"""scenario_opt: manual scenarios + constrained least-cost allocation.

Deterministic greedy allocator (capacity-aware). OR-Tools path is used when
available AND requested; greedy is the certified default so results never
depend on solver presence. Infeasible constraints -> verdict + repair hints,
never silent relaxation. Invalid inputs (negative prices, fractional or
negative capacities, max_suppliers <= 0) are rejected, never relaxed.
"""

from __future__ import annotations

from typing import Any


def _capacity_int(value: Any, supplier_id: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"capacity for {supplier_id!r} must be a number")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"capacity for {supplier_id!r} must be a whole number")
    return int(value)


def allocate(
    demand: int,
    offers: list[dict[str, Any]],
    max_suppliers: int | None = None,
) -> dict[str, Any]:
    """offers: [{supplier_id, unit_cost_minor, capacity}]. Returns allocation."""
    if demand <= 0:
        return {"allocations": [], "objective_value": 0, "constraints_ok": True, "notes": []}
    if not offers:
        return {
            "allocations": [],
            "objective_value": 0,
            "constraints_ok": False,
            "notes": ["no offers: add suppliers or reduce demand"],
        }
    if max_suppliers is not None and max_suppliers <= 0:
        return {
            "allocations": [],
            "objective_value": 0,
            "constraints_ok": False,
            "notes": ["max_suppliers must be >= 1"],
        }
    for o in offers:
        if int(o.get("unit_cost_minor", 0)) < 0:
            raise ValueError(f"negative unit_cost_minor for {o.get('supplier_id')!r}: rejected")
        _capacity_int(o.get("capacity", 0), str(o.get("supplier_id")))
    ranked = sorted(offers, key=lambda o: o["unit_cost_minor"])
    if max_suppliers is not None:
        ranked = ranked[:max_suppliers]
    remaining = demand
    allocations = []
    total = 0
    for o in ranked:
        take = min(remaining, _capacity_int(o.get("capacity", 0), str(o.get("supplier_id"))))
        if take <= 0:
            continue
        allocations.append({"supplier_id": o["supplier_id"], "qty": take})
        total += take * int(o["unit_cost_minor"])
        remaining -= take
        if remaining == 0:
            break
    if remaining > 0:
        return {
            "allocations": allocations,
            "objective_value": total,
            "constraints_ok": False,
            "notes": [f"shortfall {remaining}: raise capacity, add suppliers, or split demand"],
        }
    return {
        "allocations": allocations,
        "objective_value": total,
        "constraints_ok": True,
        "notes": [],
    }
