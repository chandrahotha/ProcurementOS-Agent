"""risk_intel: configurable weighted risk model + bands (LOW/MEDIUM/HIGH/CRITICAL)."""

from __future__ import annotations

from typing import Any

BANDS = [(25, "LOW"), (50, "MEDIUM"), (75, "HIGH"), (101, "CRITICAL")]

DEFAULT_WEIGHTS = {
    "quality": 0.25,
    "delivery": 0.25,
    "financial": 0.2,
    "compliance": 0.2,
    "geo": 0.1,
}


def score(dimensions: dict[str, int], weights: dict[str, float] | None = None) -> dict[str, Any]:
    w = weights or DEFAULT_WEIGHTS
    if abs(sum(w.values()) - 1.0) > 1e-9:
        raise ValueError("risk weights must sum to 1.0")
    composite = round(sum(int(dimensions.get(k, 0)) * w[k] for k in w))
    band = next(b for limit, b in BANDS if composite < limit)
    return {
        "dimensions": dict(dimensions),
        "weights": dict(w),
        "composite": composite,
        "band": band,
    }
