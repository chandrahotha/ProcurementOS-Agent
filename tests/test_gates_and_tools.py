"""B45: evidence-correction conflicts are real, and they block the gate.

The analysis gate refused to advance while `blocking_conflicts` was
non-zero, but the counter was hardcoded to 0: corrections kept no history,
so a second correction silently overwrote the first, and the
three-way diff in `app/evidence/conflicts.py` was written for exactly that
case and never wired.

These tests pin the wired behaviour:

* the first correction establishes the base value,
* a correction that disagrees with a pending one is a conflict: it is
  refused with 409, the stored value is not overwritten, and the span is
  marked conflicted,
* reverting to the base value resolves the conflict,
* repeating the current value resolves it too,
* a conflict actually blocks the analysis gate, and clearing it unblocks.

They also pin the tool registry (E13): the handlers that used to be
`_echo` passthroughs now call the deterministic engine, the closed
registry still refuses an unknown tool, and a material tool still refuses
to run without a quorum approval.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.evidence.conflicts import three_way_diff
from app.tools import registry
from tests.harness import (
    BUYER,
    MANAGER,
    V1,
    auth,
    mission_at_plan,
    record_spans,
)


def _span_id(c: TestClient, base: str, doc_id: str, field: str = "unit_price") -> str:
    spans = record_spans(c, base, doc_id)
    return next(s["id"] for s in spans if s["field_name"] == field)


# ------------------------------------------------------------ three-way diff
def test_three_way_diff_flags_only_a_genuine_disagreement() -> None:
    base = {"v": "a"}
    result = three_way_diff(base, {"v": "b"}, {"v": "c"})
    assert result["conflicts"] == ["v"]
    assert result["needs_retry"] is True

    # The other side still matches base: not a conflict, it auto-resolves.
    result = three_way_diff(base, {"v": "b"}, {"v": "a"})
    assert result["conflicts"] == []
    assert result["needs_retry"] is False

    # Both sides agree: not a conflict.
    result = three_way_diff(base, {"v": "b"}, {"v": "b"})
    assert result["needs_retry"] is False


# --------------------------------------------------------------- the conflict
def test_a_second_disagreeing_correction_is_refused(client: TestClient, workspace_id: str) -> None:
    _mid, base, doc_id = mission_at_plan(client, workspace_id)
    sid = _span_id(client, base, doc_id)

    # The first correction is accepted and establishes the base.
    r = client.patch(
        f"{base}/evidence/{sid}",
        headers=auth(BUYER),
        json={"field_value": "12.40", "reason": "decimal fix"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["field_value"] == "12.40"

    # A second correction that disagrees is a conflict, not an overwrite.
    r = client.patch(
        f"{base}/evidence/{sid}",
        headers=auth(BUYER),
        json={"field_value": "99.99", "reason": "different value"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "evidence_conflict"

    # The stored value is the first correction's, not the refused one's.
    r = client.get(f"{base}/evidence", headers=auth(BUYER))
    row = next(s for s in r.json()["data"]["spans"] if s["id"] == sid)
    assert row["field_value"] == "12.40"
    assert row["conflict_state"] == "conflict"


def test_reverting_to_the_base_value_resolves_the_conflict(
    client: TestClient, workspace_id: str
) -> None:
    _mid, base, doc_id = mission_at_plan(client, workspace_id)
    sid = _span_id(client, base, doc_id)
    original = "v"

    client.patch(
        f"{base}/evidence/{sid}",
        headers=auth(BUYER),
        json={"field_value": "12.40", "reason": "first"},
    )
    r = client.patch(
        f"{base}/evidence/{sid}",
        headers=auth(BUYER),
        json={"field_value": "99.99", "reason": "conflicting"},
    )
    assert r.status_code == 409

    # Reverting to the base settles it: theirs == base, so no conflict.
    r = client.patch(
        f"{base}/evidence/{sid}",
        headers=auth(BUYER),
        json={"field_value": original, "reason": "reverted"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["conflict_state"] == ""


def test_repeating_the_current_value_resolves_the_conflict(
    client: TestClient, workspace_id: str
) -> None:
    _mid, base, doc_id = mission_at_plan(client, workspace_id)
    sid = _span_id(client, base, doc_id)

    client.patch(
        f"{base}/evidence/{sid}",
        headers=auth(BUYER),
        json={"field_value": "12.40", "reason": "first"},
    )
    client.patch(
        f"{base}/evidence/{sid}",
        headers=auth(BUYER),
        json={"field_value": "99.99", "reason": "conflicting"},
    )
    # Repeating what is already stored: mine == theirs, so no conflict.
    r = client.patch(
        f"{base}/evidence/{sid}",
        headers=auth(BUYER),
        json={"field_value": "12.40", "reason": "agreed"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["conflict_state"] == ""


def test_a_conflict_blocks_the_analysis_gate(client: TestClient, workspace_id: str) -> None:
    """The gate reads the real count, not a hardcoded zero."""
    _mid, base, doc_id = mission_at_plan(client, workspace_id)
    sid = _span_id(client, base, doc_id)

    client.patch(
        f"{base}/evidence/{sid}",
        headers=auth(BUYER),
        json={"field_value": "12.40", "reason": "first"},
    )
    client.patch(
        f"{base}/evidence/{sid}",
        headers=auth(BUYER),
        json={"field_value": "99.99", "reason": "conflicting"},
    )

    # Coverage is complete, but the blocking conflict still refuses.
    r = client.post(f"{base}/advance", headers=auth(MANAGER), json={"to_state": "analysis"})
    assert r.status_code == 422
    assert "blocking conflicts" in r.json()["error"]["message"]

    # Resolving the conflict unblocks it.
    client.patch(
        f"{base}/evidence/{sid}",
        headers=auth(BUYER),
        json={"field_value": "v", "reason": "reverted"},
    )
    r = client.post(f"{base}/advance", headers=auth(MANAGER), json={"to_state": "analysis"})
    assert r.status_code == 200, r.text


def test_a_conflict_is_recorded_in_the_audit_trail(client: TestClient, workspace_id: str) -> None:
    _mid, base, doc_id = mission_at_plan(client, workspace_id)
    sid = _span_id(client, base, doc_id)
    client.patch(
        f"{base}/evidence/{sid}",
        headers=auth(BUYER),
        json={"field_value": "12.40", "reason": "first"},
    )
    client.patch(
        f"{base}/evidence/{sid}",
        headers=auth(BUYER),
        json={"field_value": "99.99", "reason": "conflicting"},
    )
    r = client.get(f"{V1}/audit", headers=auth(BUYER))
    actions = [e["action"] for e in r.json()["data"]["events"]]
    assert "evidence_conflict" in actions
    # And the chain is still intact after the refusal.
    r = client.get(f"{V1}/audit/verify", headers=auth(BUYER))
    assert r.json()["data"]["intact"] is True


# ------------------------------------------------------------- tool registry
def test_the_registry_refuses_an_unknown_tool() -> None:
    with __import__("pytest").raises(registry.UnknownToolError):
        registry.dispatch("rm_minus_rf", {})


def test_a_material_tool_needs_an_approval() -> None:
    with __import__("pytest").raises(registry.ToolDeniedError):
        registry.dispatch("issue_po_intent", {"supplier_id": "S-A"})


def test_a_write_tool_needs_an_idempotency_key() -> None:
    with __import__("pytest").raises(registry.ToolDeniedError):
        registry.dispatch("export_report", {}, approval_id="abc")


def test_the_registry_handlers_call_the_deterministic_engine() -> None:
    """E13: these four used to echo their arguments back."""

    out = registry.dispatch(
        "normalize_quote_line",
        {
            "line_id": "L1",
            "supplier_id": "S-A",
            "qty": "2",
            "uom": "pcs",
            "unit_price_minor": 1000,
            "currency": "INR",
            "tax_mode": "exclusive",
            "base_uom": "pcs",
            "target_ccy": "INR",
        },
    )
    assert "echo" not in out["result"], "normalize_quote_line still echoes"
    assert out["result"]["normalized_total_minor"] == 2000

    out = registry.dispatch(
        "compute_sourcing_rank",
        {
            "lines": [
                {
                    "line_id": "L1",
                    "supplier_id": "S-A",
                    "normalized_total_minor": 1000,
                    "compliant": True,
                },
                {
                    "line_id": "L2",
                    "supplier_id": "S-B",
                    "normalized_total_minor": 900,
                    "compliant": True,
                },
            ]
        },
    )
    assert "echo" not in out["result"], "compute_sourcing_rank still echoes"
    ranks = {ln["line_id"]: ln["rank"] for ln in out["result"]["lines"]}
    assert ranks["L2"] == 1
    assert ranks["L1"] == 2

    out = registry.dispatch(
        "compute_supplier_kpis",
        {"transactions": [{"on_time": True, "accepted": True, "qty": 10, "defects": 0}]},
    )
    assert "echo" not in out["result"], "compute_supplier_kpis still echoes"
    assert out["result"]["otd_pct"] == 100.0
    assert out["result"]["n"] == 1

    out = registry.dispatch(
        "draft_message",
        {"candidate_cost_minor": 9000, "batna_cost_minor": 10000, "draft_price_minor": 9500},
    )
    assert "echo" not in out["result"], "draft_message still echoes"
    assert out["result"]["within_bounds"] is True


def test_the_registry_reports_the_tool_version_and_autonomy_class() -> None:
    out = registry.dispatch("compute_tco", {"price_minor": 100, "freight_minor": 0})
    assert out["tool"] == "compute_tco"
    assert out["tool_version"] == "1.0.0"
    assert out["autonomy_class"] == "AUTO"


def test_a_material_tool_succeeds_with_an_approval_and_a_key() -> None:
    """The gate is satisfiable: the refusal above is not a dead end."""
    out = registry.dispatch(
        "issue_po_intent",
        {"supplier_id": "S-A"},
        approval_id="0123456789abcdef",
        idempotency_key="k-1",
    )
    assert out["tool"] == "issue_po_intent"
    assert out["autonomy_class"] == "APPROVAL-REQUIRED"


def test_decimal_money_never_leaves_the_engine_as_a_float() -> None:
    """Money stays in integer minor units (the ground rule)."""
    from decimal import Decimal

    out = registry.dispatch(
        "compute_tco",
        {
            "price_minor": 1000,
            "freight_minor": 250,
            "insurance_minor": 50,
            "tooling_minor": 0,
            "tax_minor": 190,
            "discount_minor": 100,
        },
    )
    assert isinstance(out["result"]["tco_minor"], int)
    assert out["result"]["tco_minor"] == 1390
    assert Decimal(str(out["result"]["tco_minor"])) == Decimal("1390")
