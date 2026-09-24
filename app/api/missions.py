"""Missions + documents + state advance (05 W1/W2, 04 section 1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import (
    aud,
    err,
    is_member,
    log_timeline,
    must_member,
    must_mission,
    not_found,
    rows_for,
)
from app.auth.deps import Principal, get_principal
from app.auth.roles import ADMIN, BUYER, MANAGER
from app.core.envelope import ok
from app.core.request_id import get_request_id
from app.db import get_session
from app.evidence.service import coverage as coverage_of
from app.ingest.pipeline import validate_upload, version_record
from app.missions.machine import GateContext, check_transition
from app.models.foundation import Document, DocumentVersion, EvidenceSpan
from app.models.mission import (
    Mission,
    MissionPlan,
    MissionTask,
    ScenarioResult,
    SourcingResult,
    TimelineEvent,
)

router = APIRouter()

WRITERS = {BUYER, MANAGER, ADMIN}


class MissionCreate(BaseModel):
    workspace_id: str
    title: str = Field(min_length=3, max_length=300)
    category: str = "general"
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    budget_cap_minor: int = 0
    deadline: str | None = None
    autonomy_level: str = "SUPERVISED"
    template_id: str | None = None
    lines: list[dict[str, Any]] = []


class MissionPatch(BaseModel):
    title: str | None = None
    category: str | None = None
    currency: str | None = None
    budget_cap_minor: int | None = None
    deadline: str | None = None
    autonomy_level: str | None = None


class AdvanceBody(BaseModel):
    to_state: str
    reason: str = ""
    waiver: bool = False
    action_class: str | None = None
    payload: dict[str, Any] | None = None


def _dto(m: Mission) -> dict[str, Any]:
    return {
        "id": m.id,
        "workspace_id": m.workspace_id,
        "title": m.title,
        "category": m.category,
        "currency": m.currency,
        "budget_cap_minor": m.budget_cap_minor,
        "deadline": m.deadline,
        "autonomy_level": m.autonomy_level,
        "state": m.state,
        "coverage_pct": m.coverage_pct,
        "rule_version": m.rule_version,
        "state_history": m.state_history,
        "lines": m.lines,
    }


async def _tl(
    session: AsyncSession,
    m: Mission,
    uid: str | None,
    kind: str,
    payload: dict[str, Any],
) -> None:
    await log_timeline(
        session,
        tenant_id=m.tenant_id,
        mission_id=m.id,
        kind=kind,
        payload=payload,
        actor_id=uid,
    )


@router.post("/missions")
async def create_mission(
    body: MissionCreate,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    rid = get_request_id(request)
    if not set(principal.roles) & WRITERS:
        return err(403, "forbidden", "Forbidden for role.", rid)
    if body.autonomy_level not in ("ASSISTED", "SUPERVISED", "GUARDED"):
        return err(422, "validation_error", "Unknown autonomy level.", rid)
    await must_member(session, principal, body.workspace_id)
    m = Mission(
        tenant_id=principal.tenant_id,
        workspace_id=body.workspace_id,
        title=body.title,
        category=body.category,
        currency=body.currency.upper(),
        budget_cap_minor=body.budget_cap_minor,
        deadline=body.deadline,
        autonomy_level=body.autonomy_level,
        template_id=body.template_id,
        state="intake",
        created_by=principal.user_id,
        state_history=["intake"],
        lines=body.lines,
    )
    session.add(m)
    await session.flush()
    await _tl(session, m, principal.user_id, "mission.state_changed", {"to": "intake"})
    await aud(
        session, request, principal, "mission_created", m, "mission", m.id, after={"title": m.title}
    )
    await session.commit()
    return ok(_dto(m), rid)


@router.get("/missions")
async def list_missions(
    request: Request,
    state: str | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    q = select(Mission).where(Mission.tenant_id == principal.tenant_id)
    q = q.order_by(Mission.created_at.desc())
    if state:
        q = q.where(Mission.state == state)
    rows = (await session.execute(q)).scalars().all()
    # Membership lives in workspace JSON; filter here.
    out = []
    for m in rows:
        if await is_member(session, principal, m.workspace_id):
            out.append(_dto(m))
    return ok({"missions": out}, get_request_id(request))


@router.get("/missions/{mission_id}")
async def get_mission(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    return ok(_dto(m), get_request_id(request))


@router.patch("/missions/{mission_id}")
async def patch_mission(
    mission_id: str,
    body: MissionPatch,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    rid = get_request_id(request)
    if not set(principal.roles) & WRITERS:
        return err(403, "forbidden", "Forbidden for role.", rid)
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    if body.autonomy_level and body.autonomy_level != m.autonomy_level:
        order = ["ASSISTED", "SUPERVISED", "GUARDED"]
        if body.autonomy_level not in order:
            return err(422, "validation_error", "Unknown autonomy level.", rid)
        higher = order.index(body.autonomy_level) > order.index(m.autonomy_level)
        if higher and MANAGER not in principal.roles:
            return err(403, "dial_increase_denied", "Dial increase needs a manager.", rid)
        m.autonomy_level = body.autonomy_level
        await aud(
            session,
            request,
            principal,
            "dial_changed",
            m,
            "mission",
            m.id,
            after={"autonomy_level": m.autonomy_level},
        )
    for f in ("title", "category", "currency", "budget_cap_minor", "deadline"):
        v = getattr(body, f)
        if v is not None:
            setattr(m, f, v)
    await aud(session, request, principal, "mission_updated", m, "mission", m.id)
    await session.commit()
    return ok(_dto(m), rid)


async def _gate_context(
    session: AsyncSession, principal: Principal, m: Mission, body: AdvanceBody
) -> GateContext:
    from app.approvals.service import quorum_met
    from app.ingest.instructions import args_overlap_flagged
    from app.plans.service import validate_dag
    from app.tools.registry import ALLOWLIST

    docs = await rows_for(session, Document, m.id)
    plans = await rows_for(session, MissionPlan, m.id)
    latest = max(plans, key=lambda p: p.version) if plans else None
    spans = await rows_for(session, EvidenceSpan, m.id)
    cov = coverage_of(
        [{"field_name": s.field_name, "instruction_flag": s.instruction_flag} for s in spans]
    )
    m.coverage_pct = cov["pct"]
    dag_ok = bool(latest) and validate_dag(latest.taskspecs, set(ALLOWLIST)) == []
    acked = bool(latest) and latest.status == "acknowledged"
    suppliers = {r.supplier_id for r in await rows_for(session, SourcingResult, m.id)}
    cands = (
        (
            await session.execute(
                select(ScenarioResult).where(
                    ScenarioResult.mission_id == m.id, ScenarioResult.candidate.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    kinds = {e.kind for e in await rows_for(session, TimelineEvent, m.id)}
    quorum = False
    if body.action_class and body.payload is not None:
        quorum = await quorum_met(
            session,
            tenant_id=m.tenant_id,
            mission_id=m.id,
            action_class=body.action_class,
            payload=body.payload,
        )
    quarantine_ok = True
    flagged = [s for s in spans if s.instruction_flag]
    if flagged:
        texts = [s.quoted_text for s in flagged if s.quoted_text]
        tasks = await rows_for(session, MissionTask, m.id)
        for t in tasks:
            if args_overlap_flagged(t.args_json or {}, texts):
                t.status = "blocked"
                quarantine_ok = False
    return GateContext(
        title=bool(m.title),
        workspace=bool(m.workspace_id),
        currency=bool(m.currency),
        deadline=bool(m.deadline),
        autonomy=bool(m.autonomy_level),
        intake_doc_or_waiver=bool(docs) or body.waiver,
        plan_acknowledged=acked,
        dag_ok=dag_ok,
        coverage_pct=cov["pct"],
        blocking_conflicts=0,
        coverage_waived=("coverage_waiver" in kinds),
        hostile_quarantined=quarantine_ok,
        suppliers_with_results=len(suppliers),
        sole_source_justified=("sole_source_justified" in kinds),
        rule_pinned=bool(m.rule_version),
        candidate_scenario=bool(cands),
        savings_reproducible=bool(cands),
        brief_generated=("brief_generated" in kinds),
        ladders_in_policy=("brief_generated" in kinds),
        quorum_met=quorum,
        payload_hash_match=quorum,
        actions_settled=("actions_settled" in kinds),
        idempotency_ok=True,
        report_exported=("report_exported" in kinds),
        audit_complete=True,
        roles=principal.roles,
    )


@router.post("/missions/{mission_id}/advance")
async def advance_mission(
    mission_id: str,
    body: AdvanceBody,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    rid = get_request_id(request)
    if not set(principal.roles) & WRITERS:
        return err(403, "forbidden", "Forbidden for role.", rid)
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    ctx = await _gate_context(session, principal, m, body)
    allowed, reason = check_transition(m.state, body.to_state, ctx)
    if not allowed:
        if body.to_state == "analysis":
            spans = await rows_for(session, EvidenceSpan, m.id)
            cov = coverage_of(
                [
                    {"field_name": s.field_name, "instruction_flag": s.instruction_flag}
                    for s in spans
                ]
            )
            return err(
                422,
                "coverage_failed",
                f"Advance refused: {reason}.",
                rid,
                {"missing": cov["missing"], "coverage_pct": cov["pct"]},
            )
        code = 403 if ("requires" in reason or "Manager" in reason) else 422
        return err(code, "transition_refused", f"Advance refused: {reason}.", rid)
    frm = m.state
    m.state = body.to_state
    m.state_history = list(m.state_history or []) + [body.to_state]
    if (frm, body.to_state) in {("analysis", "evidence"), ("approval", "negotiation")}:
        plans = await rows_for(session, MissionPlan, m.id)
        v = max([p.version for p in plans], default=0) + 1
        prev_specs = max(plans, key=lambda p: p.version).taskspecs if plans else []
        session.add(
            MissionPlan(
                tenant_id=m.tenant_id,
                mission_id=m.id,
                version=v,
                taskspecs=prev_specs,
                status="draft",
                diff_from_prev={"reason": f"backward {frm}->{body.to_state}"},
            )
        )
    await _tl(
        session, m, principal.user_id, "mission.state_changed", {"from": frm, "to": body.to_state}
    )
    await aud(
        session,
        request,
        principal,
        "mission.state_changed",
        m,
        "mission",
        m.id,
        after={"from": frm, "to": body.to_state},
        reason=body.reason or None,
    )
    await session.commit()
    return ok(_dto(m), rid)


@router.post("/missions/{mission_id}/documents")
async def upload_document(
    mission_id: str,
    request: Request,
    file: UploadFile = File(...),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    rid = get_request_id(request)
    if not set(principal.roles) & WRITERS:
        return err(403, "forbidden", "Forbidden for role.", rid)
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    content = await file.read()
    verdict = validate_upload(file.filename or "upload.bin", file.content_type or "", content)
    doc = Document(
        tenant_id=m.tenant_id,
        mission_id=m.id,
        kind="quote",
        filename=file.filename or "upload.bin",
        mime=file.content_type or "",
        size=len(content),
        sha256="",
        source="upload",
        status="quarantined" if verdict["verdict"] == "clean" else "rejected",
    )
    session.add(doc)
    await session.flush()
    if verdict["verdict"] == "clean":
        v = version_record(doc.filename, content, m.tenant_id)
        doc.sha256 = v["sha256"]
        session.add(
            DocumentVersion(
                tenant_id=m.tenant_id,
                document_id=doc.id,
                version=1,
                s3_key=v["s3_key"],
                sha256=v["sha256"],
                scan_verdict="clean",
            )
        )
        doc.status = "clean"
        await aud(
            session,
            request,
            principal,
            "document_uploaded",
            m,
            "document",
            doc.id,
            after={"filename": doc.filename, "sha256": doc.sha256},
        )
    else:
        await aud(
            session,
            request,
            principal,
            "document_rejected",
            m,
            "document",
            doc.id,
            reason=verdict["reason"],
        )
    await session.commit()
    return ok(
        {
            "id": doc.id,
            "filename": doc.filename,
            "status": doc.status,
            "reason": verdict.get("reason", ""),
        },
        rid,
    )


@router.get("/missions/{mission_id}/documents")
async def list_documents(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    docs = await rows_for(session, Document, m.id)
    return ok(
        {
            "documents": [
                {
                    "id": d.id,
                    "filename": d.filename,
                    "kind": d.kind,
                    "status": d.status,
                    "sha256": d.sha256,
                }
                for d in docs
            ]
        },
        get_request_id(request),
    )
