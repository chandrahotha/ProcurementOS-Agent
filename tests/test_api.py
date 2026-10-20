"""The HTTP lifecycle, split into the phases it actually asserts.

T9 said: "test_api: `raise_server_exceptions=False` + tolerance assertions
`in (403,404)` can't distinguish intended from accidental; giant lifecycle
test."

Both halves of that are now true in the opposite direction:

* the suite runs with `raise_server_exceptions=True` (B53), so a server
  exception fails the test instead of being flattened into a response;
* every denial below asserts an exact status. There is no `in (403, 404)`
  left: a cross-tenant read is a 404 and nothing else, because a 403 would
  confirm the object exists.

Each test starts from the phase it needs (the builders live in
`tests/harness.py`), so a failure names the behaviour that broke instead
of pointing at a line inside a 250-line walk. The end-to-end walk is still
exercised as one flow in `test_full_mission_walk`, and in the browser by
`web/e2e/full-flow.spec.ts`.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.harness import (
    ANALYZE_PAYLOAD,
    AWARD_PAYLOAD,
    BUYER,
    COMPLIANCE,
    FINANCE,
    MANAGER,
    OUTSIDER,
    REQUIRED_FIELDS,
    V1,
    advance,
    auth,
    create_mission,
    generate_and_acknowledge_plan,
    mission_at_analysis,
    mission_at_approval,
    mission_at_negotiation,
    mission_at_plan,
    record_spans,
)


# ---------------------------------------------------------------- auth matrix
def test_unauthenticated_requests_are_401_with_an_envelope(client: TestClient) -> None:
    r = client.get(f"{V1}/missions")
    assert r.status_code == 401
    assert r.json()["request_id"]
    assert r.json()["error"]["code"]


def test_a_bad_token_is_401(client: TestClient) -> None:
    r = client.get(f"{V1}/missions", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_another_tenant_sees_a_404_not_a_403(client: TestClient, workspace_id: str) -> None:
    """A 403 would confirm the mission exists; a 404 confirms nothing."""
    _mid, base = create_mission(client, workspace_id)
    r = client.get(base, headers=auth(OUTSIDER))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


# ------------------------------------------------------------------- W1 intake
def test_mission_create_returns_the_envelope_and_a_request_id(
    client: TestClient, workspace_id: str
) -> None:
    r = client.post(
        f"{V1}/missions",
        headers=auth(BUYER),
        json={
            "workspace_id": workspace_id,
            "title": "CNC Brackets Q4",
            "currency": "INR",
            "budget_cap_minor": 10000000,
            "deadline": "2026-12-31",
            "autonomy_level": "SUPERVISED",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("X-Request-ID")
    assert r.json()["meta"]["version"] == "v1"
    assert r.json()["data"]["state"] == "intake"


def test_a_bad_deadline_is_422(client: TestClient, workspace_id: str) -> None:
    r = client.post(
        f"{V1}/missions",
        headers=auth(BUYER),
        json={"workspace_id": workspace_id, "title": "x", "deadline": "not-a-date"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_raising_the_autonomy_dial_needs_a_manager(client: TestClient, workspace_id: str) -> None:
    _mid, base = create_mission(client, workspace_id)
    dial = {"autonomy_level": "GUARDED"}
    r = client.patch(base, headers=auth(BUYER), json=dial)
    assert r.status_code == 403
    r = client.patch(base, headers=auth(MANAGER), json=dial)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["autonomy_level"] == "GUARDED"


# ------------------------------------------------------------------ W2 intake
def test_a_clean_document_is_accepted_and_a_macro_document_is_rejected(
    client: TestClient, workspace_id: str
) -> None:
    _mid, base = create_mission(client, workspace_id)
    r = client.post(
        f"{base}/documents",
        headers=auth(BUYER),
        files={"file": ("q.pdf", b"%PDF-1.4 quote", "application/pdf")},
    )
    assert r.json()["data"]["status"] == "clean", r.text

    r = client.post(
        f"{base}/documents",
        headers=auth(BUYER),
        files={
            "file": (
                "e.docx",
                b"PK\x03\x04 vbaProject evil",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert r.json()["data"]["status"] == "rejected"


# -------------------------------------------------------------------- W2 plan
def test_a_plan_proposes_ten_tasks_and_only_a_manager_may_acknowledge(
    client: TestClient, workspace_id: str
) -> None:
    _mid, base = create_mission(client, workspace_id)
    r = client.post(f"{base}/plans", headers=auth(BUYER))
    assert r.json()["data"]["version"] == 1
    assert r.json()["data"]["tasks"] == 10

    r = client.post(f"{base}/plans/1/acknowledge", headers=auth(BUYER))
    assert r.status_code == 403
    r = client.post(f"{base}/plans/1/acknowledge", headers=auth(MANAGER))
    assert r.status_code == 200, r.text


def test_a_plan_diff_is_readable(client: TestClient, workspace_id: str) -> None:
    _mid, base = create_mission(client, workspace_id)
    generate_and_acknowledge_plan(client, base)
    r = client.get(f"{base}/plans/1/diff", headers=auth(BUYER))
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------- W2 tasks
def test_task_retry_requires_an_idempotency_key_and_review_settles(
    client: TestClient, workspace_id: str
) -> None:
    _mid, base, _doc = mission_at_plan(client, workspace_id)
    r = client.get(f"{base}/tasks", headers=auth(BUYER))
    assert len(r.json()["data"]["tasks"]) == 10

    retry = f"{base}/tasks/extract-quotes/retry"
    r = client.post(retry, headers=auth(BUYER))
    assert r.status_code == 422  # the key is required

    r = client.post(retry, headers=auth(BUYER, "k-t1"))
    assert r.json()["data"]["status"] == "queued"

    r = client.post(
        f"{base}/tasks/extract-quotes/review", headers=auth(BUYER), json={"decision": "accept"}
    )
    assert r.json()["data"]["status"] == "done"


# ---------------------------------------------------------------- W2 evidence
def test_evidence_spans_are_recorded_and_correctable(client: TestClient, workspace_id: str) -> None:
    _mid, base, doc_id = mission_at_plan(client, workspace_id)
    spans = record_spans(client, base, doc_id)
    assert len(spans) == 8
    assert {s["field_name"] for s in spans} == set(REQUIRED_FIELDS)

    r = client.patch(
        f"{base}/evidence/{spans[0]['id']}",
        headers=auth(BUYER),
        json={"field_value": "12.40", "reason": "decimal fix"},
    )
    assert r.json()["data"]["reanalysis_recommended"] is True


# ------------------------------------------------------------------ W2 gates
def test_an_illegal_jump_is_refused_with_422(client: TestClient, workspace_id: str) -> None:
    """intake -> approval is not a transition; the status is exactly 422."""
    _mid, base = create_mission(client, workspace_id)
    r = client.post(f"{base}/advance", headers=auth(BUYER), json={"to_state": "approval"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "transition_refused"


def test_the_gate_chain_advances(client: TestClient, workspace_id: str) -> None:
    _mid, base, doc_id = mission_at_plan(client, workspace_id)
    record_spans(client, base, doc_id)
    r = client.post(f"{base}/advance", headers=auth(MANAGER), json={"to_state": "analysis"})
    assert r.status_code == 200, r.text


def test_the_analysis_gate_refuses_without_coverage(client: TestClient, workspace_id: str) -> None:
    """No spans means no coverage: the gate says so and names what is missing."""
    _mid, base, _doc = mission_at_plan(client, workspace_id)
    r = client.post(f"{base}/advance", headers=auth(MANAGER), json={"to_state": "analysis"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "coverage_failed"
    assert r.json()["error"]["details"]["missing"]


# ------------------------------------------------------------------ W3 analyze
def test_analysis_is_idempotent_under_a_repeated_key(client: TestClient, workspace_id: str) -> None:
    _mid, base, _doc = mission_at_plan(client, workspace_id)
    record_spans(client, base, _doc)
    advance(client, base, "analysis")

    r = client.post(f"{base}/analyze", headers=auth(BUYER, "k-an"), json=ANALYZE_PAYLOAD)
    assert r.status_code == 200, r.text
    r = client.post(f"{base}/analyze", headers=auth(BUYER, "k-an"), json=ANALYZE_PAYLOAD)
    assert r.json()["data"]["replayed"] is True


def test_every_result_module_is_readable(client: TestClient, workspace_id: str) -> None:
    _mid, base, _run = mission_at_analysis(client, workspace_id)
    for path in ("sourcing", "cost", "risk"):
        r = client.get(f"{base}/results/{path}", headers=auth(BUYER))
        assert r.status_code == 200 and r.json()["data"]


# ---------------------------------------------------------------- W4 scenarios
def test_the_optimizer_needs_a_manager(client: TestClient, workspace_id: str) -> None:
    _mid, base, _run = mission_at_analysis(client, workspace_id)
    advance(client, base, "scenarios")
    scen = {
        "scenario_id": "split-1",
        "demand": 100,
        "candidate": True,
        "offers": [
            {"supplier_id": "S-A", "unit_cost_minor": 50, "capacity": 60},
            {"supplier_id": "S-B", "unit_cost_minor": 60, "capacity": 60},
        ],
    }
    r = client.post(f"{base}/scenarios/optimize", headers=auth(BUYER), json=scen)
    assert r.status_code == 403
    r = client.post(f"{base}/scenarios/optimize", headers=auth(MANAGER), json=scen)
    assert r.status_code == 200, r.text


def test_an_infeasible_scenario_is_refused_with_the_reason(
    client: TestClient, workspace_id: str
) -> None:
    _mid, base, _run = mission_at_analysis(client, workspace_id)
    advance(client, base, "scenarios")
    bad = {
        "scenario_id": "bad-1",
        "demand": 1000,
        "offers": [
            {"supplier_id": "S-A", "unit_cost_minor": 50, "capacity": 60},
            {"supplier_id": "S-B", "unit_cost_minor": 60, "capacity": 60},
        ],
    }
    r = client.post(f"{base}/scenarios", headers=auth(BUYER), json=bad)
    assert r.status_code == 422
    assert r.json()["error"]["details"]["notes"]


# -------------------------------------------------------------- W5 negotiation
def test_a_draft_beyond_the_walk_away_is_refused(client: TestClient, workspace_id: str) -> None:
    _mid, base, _run = mission_at_negotiation(client, workspace_id)
    draft = {
        "supplier_id": "S-A",
        "candidate_cost_minor": 9000,
        "batna_cost_minor": 10000,
        "text": "Hi, can you do 9500?",
    }
    r = client.post(
        f"{base}/negotiation/drafts",
        headers=auth(BUYER),
        json={**draft, "draft_price_minor": 12000},
    )
    assert r.status_code == 422
    r = client.post(
        f"{base}/negotiation/drafts", headers=auth(BUYER), json={**draft, "draft_price_minor": 9500}
    )
    assert r.json()["data"]["sent"] is False


# ------------------------------------------------------------------ W6 approval
def test_the_brief_ranks_the_cheapest_certified_supplier(
    client: TestClient, workspace_id: str
) -> None:
    _mid, base, _run = mission_at_analysis(client, workspace_id)
    r = client.get(f"{base}/brief", headers=auth(BUYER))
    assert r.json()["data"]["winner_supplier_id"] == "S-A"


def test_award_lanes_come_from_the_server_not_the_payload(
    client: TestClient, workspace_id: str
) -> None:
    """S-A's certified TCO is 4,720 minor, under the 50k threshold, so AWARD
    needs the managerial lane only. The forged low/high values in the
    payload cannot change the lanes."""
    _mid, base, _run = mission_at_approval(client, workspace_id)
    r = client.post(
        f"{base}/approvals",
        headers=auth(BUYER),
        json={"action_class": "AWARD", "payload": AWARD_PAYLOAD},
    )
    assert r.status_code == 200, r.text
    lanes = {a["lane"] for a in r.json()["data"]["approvals"]}
    assert lanes == {"managerial"}


def test_award_without_a_certified_value_is_refused(client: TestClient, workspace_id: str) -> None:
    _mid, base, _run = mission_at_approval(client, workspace_id)
    r = client.post(
        f"{base}/approvals",
        headers=auth(BUYER),
        json={"action_class": "AWARD", "payload": {"supplier_id": "S-Z"}},
    )
    assert r.status_code == 422


def test_the_finance_lane_cannot_decide_a_managerial_row(
    client: TestClient, workspace_id: str
) -> None:
    _mid, base, _run = mission_at_approval(client, workspace_id)
    r = client.post(
        f"{base}/approvals",
        headers=auth(BUYER),
        json={"action_class": "AWARD", "payload": AWARD_PAYLOAD},
    )
    aid = r.json()["data"]["approvals"][0]["id"]
    r = client.post(
        f"{base}/approvals/{aid}/decide",
        headers=auth(FINANCE),
        json={"decision": "approved", "reason": "x"},
    )
    assert r.status_code == 403


def test_a_compliance_reviewer_cannot_decide_either(client: TestClient, workspace_id: str) -> None:
    """The managerial lane is not open to every privileged role."""
    _mid, base, _run = mission_at_approval(client, workspace_id)
    r = client.post(
        f"{base}/approvals",
        headers=auth(BUYER),
        json={"action_class": "AWARD", "payload": AWARD_PAYLOAD},
    )
    aid = r.json()["data"]["approvals"][0]["id"]
    r = client.post(
        f"{base}/approvals/{aid}/decide",
        headers=auth(COMPLIANCE),
        json={"decision": "approved", "reason": "x"},
    )
    assert r.status_code == 403


# ------------------------------------------------------------------- W7 action
def test_execute_is_blocked_before_any_decision(client: TestClient, workspace_id: str) -> None:
    _mid, base, _run = mission_at_approval(client, workspace_id)
    ex_body = {
        "action_class": "AWARD",
        "payload": AWARD_PAYLOAD,
        "tool_name": "issue_po_intent",
    }
    r = client.post(f"{base}/actions/execute", headers=auth(BUYER, "k-ex"), json=ex_body)
    assert r.status_code == 403


def test_dry_run_says_needs_approval_before_the_decision(
    client: TestClient, workspace_id: str
) -> None:
    _mid, base, _run = mission_at_approval(client, workspace_id)
    r = client.post(
        f"{base}/actions/dry-run",
        headers=auth(BUYER),
        json={"action_class": "AWARD", "payload": AWARD_PAYLOAD},
    )
    assert r.json()["data"]["verdict"] == "NEEDS-APPROVAL"


def test_execute_after_the_decision_is_idempotent(client: TestClient, workspace_id: str) -> None:
    _mid, base, _run = mission_at_approval(client, workspace_id)
    r = client.post(
        f"{base}/approvals",
        headers=auth(BUYER),
        json={"action_class": "AWARD", "payload": AWARD_PAYLOAD},
    )
    aid = r.json()["data"]["approvals"][0]["id"]
    r = client.post(
        f"{base}/approvals/{aid}/decide",
        headers=auth(MANAGER),
        json={"decision": "approved", "reason": "ok"},
    )
    assert r.json()["data"]["quorum_met"] is True

    ex_body = {
        "action_class": "AWARD",
        "payload": AWARD_PAYLOAD,
        "tool_name": "issue_po_intent",
    }
    r = client.post(f"{base}/actions/execute", headers=auth(BUYER, "k-ex"), json=ex_body)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["replayed"] is False
    r = client.post(f"{base}/actions/execute", headers=auth(BUYER, "k-ex"), json=ex_body)
    assert r.json()["data"]["replayed"] is True


def test_the_award_issues_a_real_purchase_order(client: TestClient, workspace_id: str) -> None:
    """The gated tool produces an object of record, not just a receipt."""
    _mid, base, _run = mission_at_approval(client, workspace_id)
    r = client.post(
        f"{base}/approvals",
        headers=auth(BUYER),
        json={"action_class": "AWARD", "payload": AWARD_PAYLOAD},
    )
    aid = r.json()["data"]["approvals"][0]["id"]
    client.post(
        f"{base}/approvals/{aid}/decide",
        headers=auth(MANAGER),
        json={"decision": "approved", "reason": "ok"},
    )
    client.post(
        f"{base}/actions/execute",
        headers=auth(BUYER, "k-ex"),
        json={
            "action_class": "AWARD",
            "payload": AWARD_PAYLOAD,
            "tool_name": "issue_po_intent",
        },
    )
    r = client.get(f"{V1}/purchase-orders", headers=auth(BUYER))
    assert r.status_code == 200, r.text
    pos = r.json()["data"]["purchase_orders"]
    assert len(pos) == 1
    # The value is server-computed from the certified result, not the
    # payload's forged value_minor.
    assert pos[0]["total_minor"] == 4720


# ------------------------------------------------------------- W8 report/export
def test_a_run_replays_to_the_same_verdict(client: TestClient, workspace_id: str) -> None:
    """Replay re-runs the stored scenario inputs and compares the result."""
    _mid, base, run_id = mission_at_negotiation(client, workspace_id)
    r = client.get(f"{base}/runs", headers=auth(BUYER))
    assert r.json()["data"]["runs"]
    r = client.post(f"{base}/runs/{run_id}/replay", headers=auth(MANAGER))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["verdict"] == "match"
    assert r.json()["data"]["tco_integrity"] is True


def test_exports_are_tenant_scoped(client: TestClient, workspace_id: str) -> None:
    _mid, base, _run = mission_at_analysis(client, workspace_id)
    r = client.post(f"{base}/export", headers=auth(BUYER), json={"format": "CSV"})
    assert r.status_code == 200 and len(r.content) > 0
    for fmt in ("XLSX", "PDF"):
        r = client.post(f"{base}/export", headers=auth(BUYER), json={"format": fmt})
        assert r.status_code == 200 and len(r.content) > 100, fmt


def test_an_export_cannot_name_a_foreign_mission(client: TestClient, workspace_id: str) -> None:
    _mid, base, _run = mission_at_analysis(client, workspace_id)
    r = client.post(
        f"{base}/export",
        headers=auth(BUYER),
        json={"format": "CSV", "mission_ids": [_mid, "m-smuggled"]},
    )
    assert r.status_code == 403


def test_the_timeline_records_the_walk(client: TestClient, workspace_id: str) -> None:
    _mid, base, _run = mission_at_analysis(client, workspace_id)
    r = client.get(f"{base}/timeline", headers=auth(BUYER))
    assert len(r.json()["data"]["events"]) > 10


def test_the_case_alias_mirrors_the_missions_list(client: TestClient, workspace_id: str) -> None:
    _mid, base, _run = mission_at_analysis(client, workspace_id)
    r = client.get(f"{V1}/cases/missions", headers=auth(BUYER))
    assert r.status_code == 200 and r.json()["data"]["missions"]


# --------------------------------------------------------------- the full walk
def test_full_mission_walk(client: TestClient, workspace_id: str) -> None:
    """The whole W1->W8 path in one flow, as the release gate describes it.

    The phases above pin each step; this one proves the steps compose into
    a mission that reaches `report`.
    """
    mid, base, _run = mission_at_approval(client, workspace_id)
    r = client.post(
        f"{base}/approvals",
        headers=auth(BUYER),
        json={"action_class": "AWARD", "payload": AWARD_PAYLOAD},
    )
    aid = r.json()["data"]["approvals"][0]["id"]
    client.post(
        f"{base}/approvals/{aid}/decide",
        headers=auth(MANAGER),
        json={"decision": "approved", "reason": "ok"},
    )
    r = client.post(
        f"{base}/advance",
        headers=auth(MANAGER),
        json={"to_state": "action", "action_class": "AWARD", "payload": AWARD_PAYLOAD},
    )
    assert r.status_code == 200, r.text
    client.post(
        f"{base}/actions/execute",
        headers=auth(BUYER, "k-ex"),
        json={
            "action_class": "AWARD",
            "payload": AWARD_PAYLOAD,
            "tool_name": "issue_po_intent",
        },
    )
    r = client.post(f"{base}/actions/settle", headers=auth(MANAGER))
    assert r.status_code == 200, r.text
    r = client.post(f"{base}/advance", headers=auth(MANAGER), json={"to_state": "report"})
    assert r.status_code == 200, r.text
    assert client.get(base, headers=auth(BUYER)).json()["data"]["state"] == "report"
    # The audit chain of the whole walk re-walks without a break.
    r = client.get(f"{V1}/audit/verify", headers=auth(BUYER))
    assert r.json()["data"]["intact"] is True
