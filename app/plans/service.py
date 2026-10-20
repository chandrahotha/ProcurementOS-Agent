"""Plan generation/validation/versioning/diff (F04, F18). Deterministic DAG skeletons."""

from __future__ import annotations

import hashlib
import json
from typing import Any

#: The canonical call shape for each tool.
#:
#: A plan task is "run this tool with arguments of this shape". Before
#: this existed the task rows carried `{"depends_on": [...]}` as their
#: arguments, so every tool with a required argument was dispatched with
#: the wrong payload and blocked itself — a plan that acknowledged and then
#: could not do anything.
#:
#: These are the *shape*, not fabricated data: the values are neutral
#: (zeroed cost, an empty line list, an empty dimension map), so running a
#: plan task exercises the tool's contract without inventing a number.
#: The certified figures for a mission come from the analysis suite
#: (`POST /missions/{id}/analyze`), not from here.
CANONICAL_ARGS: dict[str, dict[str, Any]] = {
    "extract_candidates": {},
    "normalize_quote_line": {
        "line_id": "plan-template",
        "supplier_id": "S-PLANNED",
        "qty": "1",
        "uom": "pcs",
        "unit_price_minor": 0,
        "currency": "INR",
        "tax_mode": "exempt",
        "base_uom": "pcs",
        "target_ccy": "INR",
    },
    "compute_sourcing_rank": {"lines": []},
    "compute_supplier_kpis": {"transactions": []},
    "compute_tco": {
        "price_minor": 0,
        "freight_minor": 0,
        "insurance_minor": 0,
        "tooling_minor": 0,
        "tax_minor": 0,
        "discount_minor": 0,
    },
    "score_risk": {"dimensions": {}},
    "optimize_scenario": {"demand": 0, "offers": []},
    "draft_message": {
        "candidate_cost_minor": 0,
        "batna_cost_minor": 0,
        "draft_price_minor": 0,
    },
    "render_dry_run": {},
}

# Canonical task skeleton per mission (tools must be allowlist members).
PLAN_SKELETON: list[dict[str, Any]] = [
    {
        "key": "classify-docs",
        "title": "Classify intake documents",
        "tool": "extract_candidates",
        "depends_on": [],
        "estimate_min": 5,
        "autonomy_class": "AUTO",
    },
    {
        "key": "extract-quotes",
        "title": "Extract quote lines + spans",
        "tool": "extract_candidates",
        "depends_on": ["classify-docs"],
        "estimate_min": 15,
        "autonomy_class": "AUTO",
    },
    {
        "key": "normalize-lines",
        "title": "Normalize units/currency/tax",
        "tool": "normalize_quote_line",
        "depends_on": ["extract-quotes"],
        "estimate_min": 10,
        "autonomy_class": "AUTO",
    },
    {
        "key": "rank-sourcing",
        "title": "Rank cheapest-compliant per line",
        "tool": "compute_sourcing_rank",
        "depends_on": ["normalize-lines"],
        "estimate_min": 5,
        "autonomy_class": "AUTO",
    },
    {
        "key": "supplier-kpis",
        "title": "Compute supplier KPIs",
        "tool": "compute_supplier_kpis",
        "depends_on": ["extract-quotes"],
        "estimate_min": 5,
        "autonomy_class": "AUTO",
    },
    {
        "key": "tco-build",
        "title": "Build TCO waterfalls",
        "tool": "compute_tco",
        "depends_on": ["normalize-lines"],
        "estimate_min": 10,
        "autonomy_class": "AUTO",
    },
    {
        "key": "risk-score",
        "title": "Score risk dimensions",
        "tool": "score_risk",
        "depends_on": ["extract-quotes"],
        "estimate_min": 5,
        "autonomy_class": "AUTO",
    },
    {
        "key": "optimize-scenarios",
        "title": "Optimize award scenarios",
        "tool": "optimize_scenario",
        "depends_on": ["rank-sourcing", "tco-build", "risk-score"],
        "estimate_min": 10,
        "autonomy_class": "AUTO",
    },
    {
        "key": "draft-negotiation",
        "title": "Draft negotiation messages",
        "tool": "draft_message",
        "depends_on": ["optimize-scenarios"],
        "estimate_min": 10,
        "autonomy_class": "AUTO",
    },
    {
        "key": "render-brief",
        "title": "Render decision brief",
        "tool": "render_dry_run",
        "depends_on": ["optimize-scenarios"],
        "estimate_min": 5,
        "autonomy_class": "AUTO",
    },
]

MATERIAL_TOOLS = {"send_supplier_message", "issue_po_intent", "reserve_budget_intent"}


def dag_hash(taskspecs: list[dict[str, Any]]) -> str:
    canon = json.dumps(taskspecs, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def validate_dag(taskspecs: list[dict[str, Any]], allowlist: set[str]) -> list[str]:
    """Return error list (empty = valid). Checks acyclic + allowlisted + deps exist."""
    errors: list[str] = []
    keys = {t["key"] for t in taskspecs}
    for t in taskspecs:
        if t.get("tool") not in allowlist:
            errors.append(f"task {t.get('key')}: unknown tool {t.get('tool')}")
        for d in t.get("depends_on", []):
            if d not in keys:
                errors.append(f"task {t.get('key')}: missing dep {d}")
    # cycle check (Kahn)
    indeg = {t["key"]: 0 for t in taskspecs}
    adj: dict[str, list[str]] = {t["key"]: [] for t in taskspecs}
    for t in taskspecs:
        for d in t.get("depends_on", []):
            if d in adj:
                adj[d].append(t["key"])
                indeg[t["key"]] += 1
    queue = [k for k, v in indeg.items() if v == 0]
    seen = 0
    while queue:
        n = queue.pop()
        seen += 1
        for m in adj.get(n, []):
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    if seen != len(taskspecs):
        errors.append("DAG has a cycle")
    return errors


def diff_plans(prev: list[dict[str, Any]], cur: list[dict[str, Any]]) -> dict[str, Any]:
    pk = {t["key"]: t for t in prev}
    ck = {t["key"]: t for t in cur}
    added = [k for k in ck if k not in pk]
    removed = [k for k in pk if k not in ck]
    changed = [k for k in ck if k in pk and ck[k] != pk[k]]
    material = bool(added or removed or changed)
    return {"added": added, "removed": removed, "changed": changed, "material": material}
