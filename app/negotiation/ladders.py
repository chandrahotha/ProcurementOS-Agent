"""Negotiation playbook engine (F26): deterministic ladders + BATNA math.

Derived from scenario deltas: walk-away = BATNA cost, target = candidate
savings share, opening = target + concession room. AI drafts strictly inside
the ladder; send is gated (EXTERNAL_COMM approval).
"""

from __future__ import annotations

from typing import Any


def ladder(candidate_cost_minor: int, batna_cost_minor: int, steps: int = 3) -> dict[str, Any]:
    if steps < 2:
        raise ValueError("ladder needs >= 2 steps")
    walk_away = batna_cost_minor
    target = min(candidate_cost_minor, batna_cost_minor)
    room = max(0, walk_away - target)
    opening = target + room // 2 if room else target
    rung = room // steps if room else 0
    concessions = [opening - i * rung for i in range(steps)]
    return {
        "opening": opening,
        "target": target,
        "walk_away": walk_away,
        "batna_cost_minor": batna_cost_minor,
        "concessions": concessions,
    }


def draft_within_ladder(draft_price_minor: int, lad: dict[str, Any]) -> dict[str, Any]:
    lo = min(lad["target"], lad["walk_away"])
    hi = max(lad["opening"], lad["walk_away"], lad["target"])
    ok = lo <= draft_price_minor <= hi or draft_price_minor == lad["target"]
    # Drafts may aim below target (better deal); they must never exceed walk-away.
    if draft_price_minor > lad["walk_away"]:
        ok = False
    return {"within_bounds": ok, "ladder": lad, "draft_price_minor": draft_price_minor}
