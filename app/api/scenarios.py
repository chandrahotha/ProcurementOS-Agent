"""Scenarios, negotiation drafts, decision brief (05 W4–W6, F10–F12, F26)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import aud, err, log_timeline, must_mission, not_found, rows_for
from app.auth.deps import Principal, get_principal
from app.auth.roles import ADMIN, BUYER, MANAGER
from app.core.envelope import ok
from app.core.request_id import get_request_id
from app.db import get_session
from app.models.mission import CostResult, Mission, ScenarioResult, SourcingResult

router = APIRouter()
WRITE_ROLES = {BUYER, MANAGER, ADMIN}


class ScenarioBody(BaseModel):
    scenario_id: str
    demand: int
    offers: list[dict[str, Any]]
    max_suppliers: int | None = None
    candidate: bool = False


async def _store_scenario(
    session: AsyncSession,
    request: Request,
    principal: Principal,
    m: Mission,
    body: ScenarioBody,
    optimizer: bool,
) -> Any:
    from engine.scenario_opt import allocate

    rid = get_request_id(request)
    if body.demand <= 0 or not body.offers:
        return err(422, "validation_error", "Demand and offers are required.", rid)
    r = allocate(body.demand, body.offers, body.max_suppliers)
    if not r["constraints_ok"]:
        return err(
            422,
            "scenario_infeasible",
            "Constraints infeasible; nothing relaxed.",
            rid,
            {"notes": r["notes"]},
        )
    baseline = sum(o["unit_cost_minor"] * body.demand for o in body.offers[:1])
    row = ScenarioResult(
        tenant_id=m.tenant_id,
        mission_id=m.id,
        run_id="",
        scenario_id=body.scenario_id,
        allocations=r["allocations"],
        objective_value=r["objective_value"],
        constraints_ok=True,
        savings_vs_baseline=baseline - r["objective_value"],
        candidate=body.candidate,
    )
    session.add(row)
    await session.flush()
    inputs = {"demand": body.demand, "offers": body.offers, "max_suppliers": body.max_suppliers}
    await log_timeline(
        session,
        tenant_id=m.tenant_id,
        mission_id=m.id,
        kind="scenario.created",
        payload={
            "scenario_id": body.scenario_id,
            "objective": r["objective_value"],
            "optimizer": optimizer,
            "inputs": inputs,
        },
        actor_id=principal.user_id,
    )
    action = "scenario_optimized" if optimizer else "scenario_created"
    await aud(
        session,
        request,
        principal,
        action,
        m,
        "scenario",
        row.id,
        after={"scenario_id": body.scenario_id},
    )
    await session.commit()
    return ok(
        {
            "scenario_id": body.scenario_id,
            "allocations": r["allocations"],
            "objective_value": r["objective_value"],
            "savings_vs_baseline": row.savings_vs_baseline,
            "candidate": row.candidate,
        },
        rid,
    )


@router.post("/missions/{mission_id}/scenarios")
async def create_scenario(
    mission_id: str,
    body: ScenarioBody,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    if not set(principal.roles) & WRITE_ROLES:
        return err(403, "forbidden", "Forbidden for role.", get_request_id(request))
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    return await _store_scenario(session, request, principal, m, body, optimizer=False)


@router.post("/missions/{mission_id}/scenarios/optimize")
async def optimize_scenario(
    mission_id: str,
    body: ScenarioBody,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    if MANAGER not in principal.roles and ADMIN not in principal.roles:
        return err(403, "forbidden", "Optimizer runs need a manager.", get_request_id(request))
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    return await _store_scenario(session, request, principal, m, body, optimizer=True)


class DraftBody(BaseModel):
    supplier_id: str
    candidate_cost_minor: int
    batna_cost_minor: int
    draft_price_minor: int
    text: str = ""


@router.post("/missions/{mission_id}/negotiation/drafts")
async def create_draft(
    mission_id: str,
    body: DraftBody,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    if not set(principal.roles) & WRITE_ROLES:
        return err(403, "forbidden", "Forbidden for role.", get_request_id(request))
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    rid = get_request_id(request)
    from app.ingest.instructions import scan
    from app.negotiation.ladders import draft_within_ladder, ladder

    if scan(body.text).get("flagged"):
        return err(422, "draft_refused", "Draft text tripped the instruction scan.", rid)
    lad = ladder(body.candidate_cost_minor, body.batna_cost_minor)
    check = draft_within_ladder(body.draft_price_minor, lad)
    if not check["within_bounds"]:
        return err(
            422, "draft_refused", "Draft exceeds the walk-away; refused.", rid, {"ladder": lad}
        )
    await log_timeline(
        session,
        tenant_id=m.tenant_id,
        mission_id=m.id,
        kind="draft.created",
        payload={
            "supplier_id": body.supplier_id,
            "ladder": lad,
            "draft_price_minor": body.draft_price_minor,
        },
        actor_id=principal.user_id,
    )
    await aud(
        session,
        request,
        principal,
        "draft_created",
        m,
        "draft",
        None,
        after={"supplier_id": body.supplier_id},
    )
    await session.commit()
    # Nothing is sent here by design; sending needs EXTERNAL_COMM quorum in actions.
    return ok({"supplier_id": body.supplier_id, "ladder": lad, "sent": False}, rid)


@router.get("/missions/{mission_id}/brief")
async def decision_brief(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    rid = get_request_id(request)
    costs = await rows_for(session, CostResult, m.id)
    sourcing = await rows_for(session, SourcingResult, m.id)
    scenarios = await rows_for(session, ScenarioResult, m.id)
    if not costs and not sourcing:
        return err(422, "brief_empty", "No certified results to brief on yet.", rid)
    ranked = sorted(costs, key=lambda r: r.tco_minor)
    winner = ranked[0] if ranked else None
    cands = [s for s in scenarios if s.candidate]
    stale = [c.supplier_id for c in costs if c.stale_flag]
    if winner:
        wline = (
            f"Lowest certified TCO is {winner.supplier_id} "
            f"at {winner.tco_minor} minor units [cost:{winner.supplier_id}]."
        )
    else:
        wline = "No TCO rows yet; ranking unavailable [cost:none]."
    if cands:
        cline = f"{len(cands)} scenario(s) marked candidate [scenario:candidate]."
    else:
        cline = "No candidate scenario marked yet [scenario:none]."
    brief = {
        "winner_supplier_id": winner.supplier_id if winner else None,
        "winner_tco_minor": winner.tco_minor if winner else None,
        "ranking": [{"supplier_id": c.supplier_id, "tco_minor": c.tco_minor} for c in ranked],
        "candidate_scenarios": [s.scenario_id for s in cands],
        "exceptions": {"stale_fx_suppliers": stale, "lines_ranked": len(sourcing)},
        "evidence_note": "Every figure traces to result rows with "
        "evidence refs or a recorded waiver.",
        "cited_lines": [wline, cline],
    }
    await log_timeline(
        session,
        tenant_id=m.tenant_id,
        mission_id=m.id,
        kind="brief_generated",
        payload={"winner": brief["winner_supplier_id"]},
        actor_id=principal.user_id,
    )
    await aud(
        session,
        request,
        principal,
        "brief_generated",
        m,
        "brief",
        None,
        after={"winner": brief["winner_supplier_id"]},
    )
    await session.commit()
    return ok(brief, rid)
