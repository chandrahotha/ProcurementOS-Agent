"""Negotiation playbook engine (F26): deterministic ladders + BATNA math.

Derived from scenario deltas: walk-away = BATNA cost, target = candidate
savings share, opening = target + concession room. Concession rungs span the
opening->target range (never overshoot below target); the last rung lands
exactly on target.

Hard wall: a draft may aim anywhere at or below walk-away (a better deal than
BATNA), never above it. The rungs are guidance for the draft; send is gated
(EXTERNAL_COMM approval).
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
    span = opening - target
    rung = span // (steps - 1) if span else 0
    concessions = [opening - i * rung for i in range(steps - 1)] + [target]
    return {
        "opening": opening,
        "target": target,
        "walk_away": walk_away,
        "batna_cost_minor": batna_cost_minor,
        "concessions": concessions,
    }


def draft_within_ladder(draft_price_minor: int, lad: dict[str, Any]) -> dict[str, Any]:
    # Drafts may aim below target (better deal); the hard wall is walk-away.
    ok = 0 <= draft_price_minor <= lad["walk_away"]
    return {"within_bounds": ok, "ladder": lad, "draft_price_minor": draft_price_minor}
