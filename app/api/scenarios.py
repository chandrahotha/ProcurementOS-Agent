"""Scenarios, negotiation drafts, decision brief (05 W4–W6, F10–F12, F26)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import aud, err, log_timeline, must_mission, not_found, rows_for
from app.auth.deps import Principal, get_principal
from app.auth.roles import ADMIN, BUYER, MANAGER
from app.core.config import settings
from app.core.envelope import ok
from app.core.request_id import get_request_id
from app.db import get_session
from app.models.mission import CostResult, Mission, ScenarioResult, SourcingResult, TimelineEvent

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
    # Baseline (B9/E8): the cheapest feasible single-supplier cost —
    # capacity-aware and input-order independent. When no single supplier
    # covers demand, the conservative upper bound (costliest option at full
    # demand) keeps savings meaningful and never negative from split wins.
    caps: dict[str, int] = {}
    for o in body.offers:
        try:
            caps[str(o.get("supplier_id"))] = int(o.get("capacity", 0))
        except (TypeError, ValueError):
            caps[str(o.get("supplier_id"))] = 0
    singles = [o for o in body.offers if caps.get(str(o.get("supplier_id")), 0) >= body.demand]
    if singles:
        baseline = min(int(o["unit_cost_minor"]) for o in singles) * body.demand
    else:
        baseline = max(int(o["unit_cost_minor"]) for o in body.offers) * body.demand
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
    costs = await rows_for(session, CostResult, m.id, tenant_id=m.tenant_id, limit=500)
    sourcing = await rows_for(session, SourcingResult, m.id, tenant_id=m.tenant_id, limit=500)
    scenarios = await rows_for(session, ScenarioResult, m.id, tenant_id=m.tenant_id, limit=500)
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
    # Real AI touchpoint (B49): when a provider is configured, the evidence
    # note is AI-drafted through run_with_fallback + the hallucination scan,
    # persisted as AIJob/AIResult with cited refs. Unconfigured -> the
    # deterministic note (AI explains only; certified numbers are never
    # altered by AI text).
    evidence_note = "Every figure traces to result rows with evidence refs or a recorded waiver."
    ai_ran = False
    ai_status = "not_configured"
    ai_draft: dict[str, Any] | None = None
    brief = {
        "winner_supplier_id": winner.supplier_id if winner else None,
        "winner_tco_minor": winner.tco_minor if winner else None,
        "ranking": [{"supplier_id": c.supplier_id, "tco_minor": c.tco_minor} for c in ranked],
        "candidate_scenarios": [s.scenario_id for s in cands],
        "exceptions": {"stale_fx_suppliers": stale, "lines_ranked": len(sourcing)},
        "evidence_note": evidence_note,
        "cited_lines": [wline, cline],
        "ai": {"ran": ai_ran, "status": ai_status, "verdict": "", "cited": False},
    }
    if settings.ai_primary_base_url:
        import asyncio

        from app.ai.output_scan import scan_output
        from app.ai.provider import HttpxProvider, MockProvider, run_with_fallback
        from app.audit.writer import payload_hash as phash
        from app.models.foundation import AIJob, AIResult

        ai_inputs = {
            "mission": m.id,
            "winner": brief["winner_supplier_id"],
            "ranking": brief["ranking"],
            "cited_lines": brief["cited_lines"],
        }
        res, ai_status = await asyncio.to_thread(
            run_with_fallback,
            HttpxProvider(base_url=settings.ai_primary_base_url, timeout_s=settings.ai_timeout_s),
            MockProvider(),
            "brief-v1",
            ai_inputs,
        )
        ai_ran = True
        job = AIJob(
            tenant_id=m.tenant_id,
            mission_id=m.id,
            purpose="brief_note",
            provider="primary",
            model_version=str(res.payload.get("model", "mock-1")),
            prompt_version="brief-v1",
            input_hash=phash(ai_inputs),
            output_hash=phash(res.payload),
            status="ok" if res.ok else "degraded",
            error=res.error or None,
            created_by=principal.user_id,
        )
        session.add(job)
        await session.flush()
        # Hallucination guard (POS-AI-HAL-01): the note is labeled
        # analytical, so an unreferenced claim is *accepted with zero
        # authority* — it may not be laundered into the evidence note.
        # Only an evidence-linked claim replaces the deterministic note; an
        # unreferenced one is surfaced separately, with its citation state
        # visible, so a reader can see it is uncited rather than being
        # handed a claim dressed as a certified fact.
        scan = scan_output(
            {
                "text": str(res.payload.get("text", "")),
                "evidence_refs": list(res.payload.get("evidence_refs", [])),
                "label": "analytical",
            }
        )
        ai_text = str(res.payload.get("text", ""))
        ai_refs = list(res.payload.get("evidence_refs", []))
        cited = scan["verdict"] == "accept"
        if ai_text:
            session.add(
                AIResult(
                    tenant_id=m.tenant_id,
                    job_id=job.id,
                    schema_name="brief_note",
                    payload_json=res.payload,
                    evidence_refs=ai_refs,
                    label="AI draft",
                )
            )
            if cited:
                evidence_note = ai_text
            else:
                ai_draft = {
                    "text": ai_text,
                    "cited": False,
                    "verdict": scan["verdict"],
                    "note": "AI analysis, uncited: it explains but certifies nothing.",
                }
        brief["ai"] = {
            "ran": ai_ran,
            "status": ai_status,
            "verdict": scan["verdict"],
            "cited": cited,
        }
        await session.commit()
        brief["evidence_note"] = evidence_note
        if ai_draft is not None:
            brief["ai_draft"] = ai_draft
    # The brief is computed on demand from certified rows (B9): the
    # brief_generated timeline/audit events persist ONCE per mission — not
    # per read — so the gate signal stays real without unbounded growth on
    # every GET.
    kinds = {
        k
        for k in (
            await session.execute(
                select(TimelineEvent.kind).where(TimelineEvent.mission_id == m.id)
            )
        ).scalars()
    }
    if "brief_generated" not in kinds:
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
