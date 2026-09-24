"""Normative mission-state machine (brain 04 §1). Pure logic — no DB, fully tested."""

from __future__ import annotations

from dataclasses import dataclass, field

STATES = [
    "intake",
    "plan",
    "evidence",
    "analysis",
    "scenarios",
    "negotiation",
    "approval",
    "action",
    "report",
]

NEXT: dict[str, str] = {
    "intake": "plan",
    "plan": "evidence",
    "evidence": "analysis",
    "analysis": "scenarios",
    "scenarios": "negotiation",
    "negotiation": "approval",
    "approval": "action",
    "action": "report",
}

# Backward moves allowed only as new plan version (never silent rewrite).
BACKWARD_OK = {("analysis", "evidence"), ("approval", "negotiation")}


@dataclass
class GateContext:
    title: bool = False
    workspace: bool = False
    currency: bool = False
    deadline: bool = False
    autonomy: bool = False
    intake_doc_or_waiver: bool = False
    plan_acknowledged: bool = False
    dag_ok: bool = False
    coverage_pct: int = 0
    blocking_conflicts: int = 0
    coverage_waived: bool = False
    hostile_quarantined: bool = True
    suppliers_with_results: int = 0
    sole_source_justified: bool = False
    rule_pinned: bool = False
    candidate_scenario: bool = False
    savings_reproducible: bool = False
    brief_generated: bool = False
    ladders_in_policy: bool = False
    quorum_met: bool = False
    payload_hash_match: bool = False
    actions_settled: bool = False
    idempotency_ok: bool = False
    report_exported: bool = False
    audit_complete: bool = False
    roles: list[str] = field(default_factory=list)


def _has(roles: list[str], *need: str) -> bool:
    return bool(set(roles) & set(need))


def check_transition(frm: str, to: str, ctx: GateContext) -> tuple[bool, str]:
    """Return (allowed, reason). Forward = NEXT[frm]; backward only BACKWARD_OK."""
    if to == frm:
        return False, "no-op"
    if NEXT.get(frm) == to:
        return _entry(to, ctx)
    if (frm, to) in BACKWARD_OK:
        return True, "backward-as-new-plan-version"
    return False, f"illegal {frm}->{to}"


def _entry(to: str, c: GateContext) -> tuple[bool, str]:
    if to == "plan":
        ok = all([c.title, c.workspace, c.currency, c.deadline, c.autonomy, c.intake_doc_or_waiver])
        return ok, "intake checklist" if not ok else "ok"
    if to == "evidence":
        if not _has(c.roles, "ProcurementManager", "Buyer", "Admin"):
            return False, "plan ack requires Manager (or Buyer w/ pre-approved template)"
        if not (c.plan_acknowledged and c.dag_ok):
            return False, "plan v1 must be acknowledged; DAG acyclic + allowlisted tools"
        return True, "ok"
    if to == "analysis":
        gate = (c.coverage_pct >= 80 and c.blocking_conflicts == 0) or c.coverage_waived
        if not gate:
            return False, "coverage >= 80% with 0 blocking conflicts, or Compliance waiver"
        if not c.hostile_quarantined:
            return False, "hostile-span quarantine unverified"
        return True, "ok"
    if to == "scenarios":
        if not ((c.suppliers_with_results >= 2 or c.sole_source_justified) and c.rule_pinned):
            return False, "need sourcing+cost+risk for >=2 suppliers (or sole-source), rule pinned"
        return True, "ok"
    if to == "negotiation":
        if not _has(c.roles, "ProcurementManager"):
            return False, "scenario candidate requires Manager"
        if not (c.candidate_scenario and c.savings_reproducible):
            return False, "need candidate scenario + reproducible savings"
        return True, "ok"
    if to == "approval":
        if not _has(c.roles, "ProcurementManager"):
            return False, "brief handoff requires Manager"
        if not (c.brief_generated and c.ladders_in_policy):
            return False, "need Decision Brief + ladders in policy"
        return True, "ok"
    if to == "action":
        if not (c.quorum_met and c.payload_hash_match):
            return False, "quorum approvals + payload hash match required"
        return True, "ok"
    if to == "report":
        if not (c.actions_settled and c.idempotency_ok):
            return False, "all approved actions executed/skipped with reason; receipts stored"
        return True, "ok"
    return False, f"unknown state {to}"
