"""Plans, tasks, runs, timeline (05 W1/W2, F04/F05/F15)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import aud, err, log_timeline, must_mission, not_found, rows_for
from app.auth.deps import Principal, get_principal
from app.auth.roles import ADMIN, BUYER, MANAGER
from app.core.envelope import ok
from app.core.request_id import get_request_id
from app.db import get_session
from app.models.foundation import AuditEvent
from app.models.mission import Mission, MissionPlan, MissionRun, MissionTask, TimelineEvent
from app.plans.service import PLAN_SKELETON, dag_hash, diff_plans, validate_dag
from app.tools.registry import ALLOWLIST

router = APIRouter()

REVIEW_ROLES = {BUYER, MANAGER, ADMIN}
FORBIDDEN = (403, "forbidden", "Forbidden for role.")


def _role_err(rid: str) -> Any:
    return err(*FORBIDDEN, rid)


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


@router.post("/missions/{mission_id}/plans")
async def generate_plan(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    rid = get_request_id(request)
    if not set(principal.roles) & REVIEW_ROLES:
        return _role_err(rid)
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    plans = await rows_for(session, MissionPlan, m.id)
    v = max([p.version for p in plans], default=0) + 1
    specs = [dict(t) for t in PLAN_SKELETON]
    errors = validate_dag(specs, set(ALLOWLIST))
    if errors:
        return err(
            422, "plan_invalid", "Generated plan failed validation.", rid, {"errors": errors}
        )
    prev = max(plans, key=lambda p: p.version).taskspecs if plans else []
    plan = MissionPlan(
        tenant_id=m.tenant_id,
        mission_id=m.id,
        version=v,
        taskspecs=specs,
        dag_hash=dag_hash(specs),
        diff_from_prev=diff_plans(prev, specs),
        status="draft",
    )
    session.add(plan)
    await session.flush()
    for t in specs:
        role = "Buyer" if t["autonomy_class"] == "AUTO" else "ProcurementManager"
        session.add(
            MissionTask(
                tenant_id=m.tenant_id,
                mission_id=m.id,
                plan_version=v,
                key=t["key"],
                title=t["title"],
                tool_name=t["tool"],
                args_json={"depends_on": t.get("depends_on", [])},
                idempotency_key=f"{m.id}:v{v}:{t['key']}",
                assigned_role=role,
            )
        )
    await _tl(session, m, principal.user_id, "plan.proposed", {"version": v})
    await aud(
        session, request, principal, "plan_proposed", m, "plan", plan.id, after={"version": v}
    )
    await session.commit()
    return ok({"version": v, "dag_hash": plan.dag_hash, "tasks": len(specs)}, rid)


@router.get("/missions/{mission_id}/plans/current")
async def current_plan(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    plans = await rows_for(session, MissionPlan, m.id)
    if not plans:
        return err(404, "not_found", "No plan yet.", get_request_id(request))
    p = max(plans, key=lambda x: x.version)
    return ok(
        {
            "version": p.version,
            "status": p.status,
            "dag_hash": p.dag_hash,
            "taskspecs": p.taskspecs,
            "acknowledged_by": p.acknowledged_by,
        },
        get_request_id(request),
    )


@router.get("/missions/{mission_id}/plans/{version}/diff")
async def plan_diff(
    mission_id: str,
    version: int,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    by_version = {p.version: p for p in await rows_for(session, MissionPlan, m.id)}
    if version not in by_version:
        return err(404, "not_found", "No such plan version.", get_request_id(request))
    p = by_version[version]
    return ok({"version": version, "diff": p.diff_from_prev}, get_request_id(request))


@router.post("/missions/{mission_id}/plans/{version}/acknowledge")
async def acknowledge_plan(
    mission_id: str,
    version: int,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    rid = get_request_id(request)
    if MANAGER not in principal.roles and ADMIN not in principal.roles:
        return err(403, "forbidden", "Plan acknowledgement needs a manager.", rid)
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    q = await session.execute(
        select(MissionPlan).where(MissionPlan.mission_id == m.id, MissionPlan.version == version)
    )
    p = q.scalar_one_or_none()
    if p is None:
        return err(404, "not_found", "No such plan version.", rid)
    p.status = "acknowledged"
    p.acknowledged_by = principal.user_id
    others = (
        (
            await session.execute(
                select(MissionPlan).where(
                    MissionPlan.mission_id == m.id, MissionPlan.version != version
                )
            )
        )
        .scalars()
        .all()
    )
    for old in others:
        if old.status == "acknowledged":
            old.status = "superseded"
    await _tl(session, m, principal.user_id, "plan.acknowledged", {"version": version})
    await aud(
        session,
        request,
        principal,
        "plan_acknowledged",
        m,
        "plan",
        p.id,
        after={"version": version},
    )
    await session.commit()
    return ok({"version": version, "status": p.status}, rid)


@router.get("/missions/{mission_id}/tasks")
async def task_board(
    mission_id: str,
    request: Request,
    status: str | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    q = select(MissionTask).where(MissionTask.mission_id == m.id)
    if status:
        q = q.where(MissionTask.status == status)
    tasks = (await session.execute(q)).scalars().all()
    return ok(
        {
            "tasks": [
                {
                    "key": t.key,
                    "title": t.title,
                    "tool": t.tool_name,
                    "status": t.status,
                    "attempts": t.attempts,
                    "plan_version": t.plan_version,
                    "evidence_refs": t.evidence_refs,
                }
                for t in tasks
            ]
        },
        get_request_id(request),
    )


class ReviewBody(BaseModel):
    decision: str  # accept | flag
    note: str = ""


async def _one_task(
    session: AsyncSession,
    m: Mission,
    key: str,
) -> MissionTask | None:
    q = await session.execute(
        select(MissionTask).where(MissionTask.mission_id == m.id, MissionTask.key == key)
    )
    return q.scalar_one_or_none()


@router.post("/missions/{mission_id}/tasks/{key}/retry")
async def retry_task(
    mission_id: str,
    key: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    rid = get_request_id(request)
    if not set(principal.roles) & REVIEW_ROLES:
        return _role_err(rid)
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    if not request.headers.get("Idempotency-Key", ""):
        return err(422, "idempotency_required", "Idempotency-Key header is required.", rid)
    t = await _one_task(session, m, key)
    if t is None:
        return err(404, "not_found", "No such task.", rid)
    t.attempts += 1
    t.status = "queued"
    t.activity_log = list(t.activity_log or []) + [{"event": "retried", "by": principal.user_id}]
    await aud(session, request, principal, "task_retried", m, "task", t.id, after={"key": key})
    await session.commit()
    return ok({"key": key, "status": t.status, "attempts": t.attempts}, rid)


@router.post("/missions/{mission_id}/tasks/{key}/review")
async def review_task(
    mission_id: str,
    key: str,
    body: ReviewBody,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    rid = get_request_id(request)
    if not set(principal.roles) & REVIEW_ROLES:
        return _role_err(rid)
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    if body.decision not in ("accept", "flag"):
        return err(422, "validation_error", "Decision must be accept or flag.", rid)
    t = await _one_task(session, m, key)
    if t is None:
        return err(404, "not_found", "No such task.", rid)
    t.status = "done" if body.decision == "accept" else "needs_review"
    t.activity_log = list(t.activity_log or []) + [
        {"event": f"reviewed:{body.decision}", "by": principal.user_id, "note": body.note}
    ]
    await aud(
        session,
        request,
        principal,
        "task_reviewed",
        m,
        "task",
        t.id,
        after={"key": key, "decision": body.decision},
    )
    await session.commit()
    return ok({"key": key, "status": t.status}, rid)


@router.get("/missions/{mission_id}/runs")
async def run_history(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    runs = await rows_for(session, MissionRun, m.id)
    return ok(
        {
            "runs": [
                {
                    "id": r.id,
                    "trigger": r.trigger,
                    "rule_version": r.rule_version,
                    "status": r.status,
                    "inputs_hash": r.inputs_hash,
                    "tool_versions": r.tool_versions,
                }
                for r in runs
            ]
        },
        get_request_id(request),
    )


@router.get("/missions/{mission_id}/timeline")
async def timeline(
    mission_id: str,
    request: Request,
    since: str | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    ev_q = select(TimelineEvent).where(TimelineEvent.mission_id == m.id)
    ev_q = ev_q.order_by(TimelineEvent.created_at)
    events = (await session.execute(ev_q)).scalars().all()
    au_q = select(AuditEvent).where(AuditEvent.mission_id == m.id)
    au_q = au_q.order_by(AuditEvent.created_at)
    audits = (await session.execute(au_q)).scalars().all()
    items: list[dict[str, Any]] = [
        {"kind": e.kind, "payload": e.payload, "at": e.created_at.isoformat(), "actor": e.actor_id}
        for e in events
    ] + [
        {
            "kind": f"audit:{a.action}",
            "at": a.created_at.isoformat(),
            "actor": a.actor_id,
            "request_id": a.request_id,
        }
        for a in audits
    ]
    if since:
        items = [i for i in items if i["at"] >= since]
    return ok({"events": items}, get_request_id(request))
