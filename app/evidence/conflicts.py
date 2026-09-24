"""Concurrent-correction conflicts: three-way diff, no silent overwrite (POS-CONC-01)."""

from __future__ import annotations

from typing import Any


def three_way_diff(
    base: dict[str, Any], mine: dict[str, Any], theirs: dict[str, Any]
) -> dict[str, Any]:
    keys = set(base) | set(mine) | set(theirs)
    conflicts = sorted(k for k in keys if mine.get(k) != theirs.get(k))
    clean = [k for k in keys if mine.get(k) == theirs.get(k)]
    return {
        "base": base,
        "mine": mine,
        "theirs": theirs,
        "conflicts": conflicts,
        "clean": clean,
        "needs_retry": bool(conflicts),
    }
