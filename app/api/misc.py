"""Workspaces, scenarios/approvals lists, audit + rules read models, settle.

These are the read paths the screens consume (P02 workspace picker, P10
scenario list, P13 approval queue, G13 audit log, G16 rules viewer) plus
the settle action that closes the action->report gate.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import aud, err, log_timeline, must_mission, not_found, rows_for
from app.auth.deps import Principal, get_principal
from app.auth.roles import ADMIN, BUYER, MANAGER
from app.core.envelope import ok
from app.core.request_id import get_request_id
from app.db import get_session
from app.models.foundation import Approval, AuditEvent, Workspace
from app.models.mission import RuleVersion, ScenarioResult

router = APIRouter()

WRITERS = {BUYER, MANAGER, ADMIN}


@router.get("/workspaces")
async def list_workspaces(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Workspaces the principal is a member of (Admin sees all in tenant)."""
    q = select(Workspace).where(Workspace.tenant_id == principal.tenant_id)
    rows = (await session.execute(q)).scalars().all()
    out = []
    for ws in rows:
        member = any(m.get("user_id") == principal.user_id for m in (ws.members or []))
        if member or "Admin" in principal.roles:
            out.append(
                {
                    "id": ws.id,
                    "name": ws.name,
                    "budget_currency": ws.budget_currency,
                }
            )
    return ok({"workspaces": out}, get_request_id(request))


@router.get("/missions/{mission_id}/scenarios")
async def list_scenarios(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    rows = await rows_for(session, ScenarioResult, m.id)
    return ok(
        {
            "scenarios": [
                {
                    "scenario_id": r.scenario_id,
                    "allocations": r.allocations,
                    "objective_value": r.objective_value,
                    "candidate": r.candidate,
                    "savings_vs_baseline": r.savings_vs_baseline,
                }
                for r in rows
            ]
        },
        get_request_id(request),
    )


@router.get("/missions/{mission_id}/approvals")
async def list_approvals(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """All approval rows for the mission (P13 queue + quorum read)."""
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    from app.api.common import rows_for as rf

    rows = await rf(session, Approval, m.id)
    return ok(
        {
            "approvals": [
                {
                    "id": r.id,
                    "lane": r.lane,
                    "status": r.status,
                    "action_class": r.action_class,
                    "expires_at": r.expires_at,
                    "payload_hash": r.payload_hash[:16],
                }
                for r in rows
            ]
        },
        get_request_id(request),
    )


@router.get("/audit")
async def audit_log(
    request: Request,
    limit: int = 200,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Tenant-wide hash-chained events, newest first (G13)."""
    q = select(AuditEvent).where(AuditEvent.tenant_id == principal.tenant_id)
    q = q.order_by(AuditEvent.created_at.desc()).limit(min(limit, 500))
    rows = (await session.execute(q)).scalars().all()
    return ok(
        {
            "events": [
                {
                    "id": r.id,
                    "action": r.action,
                    "object_type": r.object_type,
                    "mission_id": r.mission_id,
                    "actor_id": r.actor_id,
                    "request_id": r.request_id,
                    "reason": r.reason,
                    "event_hash": r.event_hash[:16],
                    "at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        },
        get_request_id(request),
    )


@router.get("/rules")
async def rules(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Rule versions in this tenant (G16 read model)."""
    q = select(RuleVersion).where(RuleVersion.tenant_id == principal.tenant_id)
    q = q.order_by(RuleVersion.created_at.desc())
    rows = (await session.execute(q)).scalars().all()
    return ok(
        {
            "rules": [
                {
                    "version": r.version,
                    "effective_from": r.effective_from,
                    "weights": r.weights,
                    "tolerances": r.tolerances,
                    "fx_policy": r.fx_policy,
                    "changelog": r.changelog,
                }
                for r in rows
            ]
        },
        get_request_id(request),
    )


@router.post("/missions/{mission_id}/actions/settle")
async def settle_actions(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Record that approved actions are executed or explicitly skipped (04 s1)."""
    rid = get_request_id(request)
    if not set(principal.roles) & WRITERS:
        return err(403, "forbidden", "Forbidden for role.", rid)
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    await log_timeline(
        session,
        tenant_id=m.tenant_id,
        mission_id=m.id,
        kind="actions_settled",
        payload={"by": principal.user_id},
        actor_id=principal.user_id,
    )
    await aud(session, request, principal, "actions_settled", m, "mission", m.id)
    await session.commit()
    return ok({"mission_id": m.id, "settled": True}, rid)
