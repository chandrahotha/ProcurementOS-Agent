"""Phase 9 suites: POS-MISS-01, POS-CONC-01, POS-AI-HAL-01, POS-SEC-01,
POS-APPR-01, state-machine transitions, coverage gate, plan DAG validation.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.actions import service as actions
from app.ai.output_scan import scan_output
from app.approvals import service as approvals
from app.evidence import service as ev
from app.evidence.conflicts import three_way_diff
from app.missions.machine import GateContext, check_transition
from app.models.base import Base
from app.models.mission import CostResult, Mission
from app.plans.service import diff_plans, validate_dag


async def _mk():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


def test_pos_miss_01_advance_refused_without_coverage():
    ctx = GateContext(coverage_pct=40, blocking_conflicts=2, hostile_quarantined=True)
    ok, reason = check_transition("evidence", "analysis", ctx)
    assert ok is False and "coverage" in reason
    # T20: coverage and conflicts are independent gates — a waiver admits
    # low coverage but blocking conflicts still refuse the advance.
    waived = GateContext(
        coverage_pct=40, blocking_conflicts=2, hostile_quarantined=True, coverage_waived=True
    )
    ok2, reason2 = check_transition("evidence", "analysis", waived)
    assert ok2 is False and "conflicts" in reason2
    waived_clean = GateContext(
        coverage_pct=40, blocking_conflicts=0, hostile_quarantined=True, coverage_waived=True
    )
    ok3, _ = check_transition("evidence", "analysis", waived_clean)
    assert ok3 is True
    cov = ev.coverage([{"field_name": "unit_price"}], ["unit_price", "currency", "uom"])
    assert cov["pct"] == 33 and cov["missing"] == ["currency", "uom"]


def test_pos_conc_01_three_way_diff():
    d = three_way_diff({"v": "12.40"}, {"v": "12.50"}, {"v": "12.60"})
    assert d["needs_retry"] is True and d["conflicts"] == ["v"]
    assert d["mine"]["v"] == "12.50" and d["theirs"]["v"] == "12.60" and d["base"]["v"] == "12.40"


def test_pos_ai_hal_01_hallucination_quarantined():
    assert scan_output({"text": "Winner is X", "evidence_refs": ["s1"]})["verdict"] == "accept"
    q = scan_output({"text": "Winner is X", "evidence_refs": []})
    assert q["verdict"] == "quarantine"
    lab = scan_output({"text": "What if weights shift?", "label": "AI analytical"})
    assert lab["verdict"] == "accept-labeled"


async def test_pos_sec_01_cross_tenant_denied() -> None:
    mk = await _mk()
    async with mk() as s:
        s.add(Mission(id="m1", tenant_id="t1", workspace_id="w", title="T1", currency="INR"))
        s.add(Mission(id="m2", tenant_id="t2", workspace_id="w", title="T2", currency="INR"))
        await s.commit()
        mine = (await s.execute(select(Mission).where(Mission.tenant_id == "t1"))).scalars().all()
        assert [m.id for m in mine] == ["m1"]
        # T7: the APP's authz layer is under test — must_mission with a t2
        # principal must refuse t1's mission (404, no existence leak), not
        # just verify a hand-written WHERE clause.
        from fastapi import HTTPException

        from app.api.common import must_mission
        from app.auth.deps import Principal

        t2_principal = Principal(user_id="u-t2", tenant_id="t2", email="o@x.io", roles=["Buyer"])
        with pytest.raises(HTTPException) as ei:
            await must_mission(s, t2_principal, "m1")
        assert ei.value.status_code == 404


async def test_pos_appr_01_single_lane_insufficient_over_threshold() -> None:
    mk = await _mk()
    async with mk() as s:
        s.add(
            Mission(
                id="m9",
                tenant_id="t1",
                workspace_id="w",
                title="M",
                currency="INR",
                state="approval",
            )
        )
        await s.commit()
        # Server-computed value (04 s2): certify a TCO of INR 6,00,000 for
        # S1, above the INR 5,00,000 dual-control threshold, so the AWARD
        # escalates to dual lanes even though the payload declares 1.
        s.add(
            CostResult(
                tenant_id="t1",
                mission_id="m9",
                run_id="",
                supplier_id="S1",
                scenario_id="",
                tco_minor=60_000_000,
                build_up={"price": 60_000_000},
            )
        )
        await s.commit()
        payload = {"supplier_id": "S1", "value_minor": 1, "threshold_minor": 1}
        rows = await approvals.request_approval(
            s,
            tenant_id="t1",
            mission_id="m9",
            action_class="AWARD",
            payload=payload,
            requested_by="u-b",
        )
        # Forged low value cannot downgrade: certified 60k > 50k threshold.
        assert {r.lane for r in rows} == {"managerial", "finance"}
        # Approve ONLY the managerial lane -> quorum still false -> execute DENY.
        mgr = next(r for r in rows if r.lane == "managerial")
        await approvals.decide(
            s,
            approval_id=mgr.id,
            tenant_id="t1",
            principal_roles=["ProcurementManager"],
            principal_id="u-m",
            decision="approved",
            reason="ok",
        )
        assert (
            await approvals.quorum_met(
                s, tenant_id="t1", mission_id="m9", action_class="AWARD", payload=payload
            )
            is False
        )
        import pytest

        with pytest.raises(actions.ActionBlockedError):
            await actions.execute(
                s,
                tenant_id="t1",
                mission_id="m9",
                action_class="AWARD",
                payload=payload,
                tool_name="issue_po_intent",
                actor_id="u-b",
                request_id="r1",
                idempotency_key="k9",
            )


def test_machine_forward_backward_illegal():
    full = GateContext(
        title=True,
        workspace=True,
        currency=True,
        deadline=True,
        autonomy=True,
        intake_doc_or_waiver=True,
        plan_acknowledged=True,
        dag_ok=True,
        coverage_pct=95,
        hostile_quarantined=True,
        suppliers_with_results=3,
        rule_pinned=True,
        candidate_scenario=True,
        savings_reproducible=True,
        brief_generated=True,
        ladders_in_policy=True,
        quorum_met=True,
        payload_hash_match=True,
        actions_settled=True,
        idempotency_ok=True,
        report_exported=True,
        audit_complete=True,
        roles=["ProcurementManager", "Buyer"],
    )
    assert check_transition("intake", "plan", full)[0] is True
    assert check_transition("analysis", "evidence", full) == (True, "backward-as-new-plan-version")
    ok, reason = check_transition("intake", "approval", full)
    assert ok is False and "illegal" in reason


def test_plan_dag_validation_and_diff():
    allow = {"extract_candidates", "compute_tco"}
    good = [
        {"key": "a", "tool": "extract_candidates", "depends_on": []},
        {"key": "b", "tool": "compute_tco", "depends_on": ["a"]},
    ]
    assert validate_dag(good, allow) == []
    bad_tool = [{"key": "a", "tool": "raw_sql", "depends_on": []}]
    assert any("unknown tool" in e for e in validate_dag(bad_tool, allow))
    cyclic = [
        {"key": "a", "tool": "extract_candidates", "depends_on": ["b"]},
        {"key": "b", "tool": "compute_tco", "depends_on": ["a"]},
    ]
    assert any("cycle" in e for e in validate_dag(cyclic, allow))
    d = diff_plans(good, good + [{"key": "c", "tool": "compute_tco", "depends_on": ["b"]}])
    assert d["added"] == ["c"] and d["material"] is True
