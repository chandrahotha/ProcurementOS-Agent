"""Prompt-injection isolation (brain 04 §4). Document bytes are DATA, never instructions."""

from __future__ import annotations

import re
from typing import Any

PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions?",
    r"approve\s+.*immediately",
    r"you\s+are\s+now\b",
    r"disregard\s+(the\s+)?polic",
    r"override\s+(the\s+)?approval",
    r"send\s+.*without\s+approval",
    r"act\s+as\s+(if\s+you\s+were\s+)?(admin|manager)",
    r"confidential.*reveal",
]

_RX = [re.compile(p, re.IGNORECASE) for p in PATTERNS]


def scan(text: str) -> dict[str, Any]:
    """Return {flagged, hits}. Pure function; OCR output treated as untrusted data."""
    hits = [rx.pattern for rx in _RX if rx.search(text or "")]
    return {"flagged": bool(hits), "hits": hits}


def planning_inputs_clean(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Exclude instruction_flag spans from planner/task-arg construction."""
    return [s for s in spans if not s.get("instruction_flag")]


def args_overlap_flagged(args: dict[str, Any], flagged_texts: list[str]) -> bool:
    blob = " ".join(str(v) for v in args.values()).lower()
    return any(t.lower() in blob for t in flagged_texts if t)
