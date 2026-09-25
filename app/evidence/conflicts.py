"""Concurrent-correction conflicts: three-way diff, no silent overwrite (POS-CONC-01).

Standard three-way semantics: a key is a conflict only when mine and theirs
both differ from base AND from each other. A one-sided change (the other side
still matches base) auto-resolves instead of flagging needs_retry.
"""

from __future__ import annotations

from typing import Any


def three_way_diff(
    base: dict[str, Any], mine: dict[str, Any], theirs: dict[str, Any]
) -> dict[str, Any]:
    keys = set(base) | set(mine) | set(theirs)
    conflicts = sorted(
        k
        for k in keys
        if mine.get(k) != theirs.get(k)
        and mine.get(k) != base.get(k)
        and theirs.get(k) != base.get(k)
    )
    resolved = [k for k in keys if k not in conflicts and mine.get(k) == theirs.get(k)]
    return {
        "base": base,
        "mine": mine,
        "theirs": theirs,
        "conflicts": conflicts,
        "clean": resolved,
        "needs_retry": bool(conflicts),
    }
