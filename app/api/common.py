"""Shared API helpers: tenant-scoped loading, membership, audit + timeline writes."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.writer import append_event
from app.auth.deps import Principal
from app.core.errors import error_response
from app.core.request_id import get_request_id
from app.models.foundation import Workspace
from app.models.mission import Mission, TimelineEvent


async def must_member(session: AsyncSession, principal: Principal, workspace_id: str) -> Workspace:
    q = await session.execute(
        select(Workspace).where(
            Workspace.id == workspace_id, Workspace.tenant_id == principal.tenant_id
        )
    )
    ws = q.scalar_one_or_none()
    if ws is None:
        raise HTTPException(status_code=404, detail="Not found.")
    member_ids = [m.get("user_id") for m in (ws.members or [])]
    if principal.user_id not in member_ids and "Admin" not in principal.roles:
        raise HTTPException(status_code=403, detail="Not a workspace member.")
    return ws


async def is_member(session: AsyncSession, principal: Principal, workspace_id: str) -> bool:
    try:
        await must_member(session, principal, workspace_id)
        return True
    except HTTPException:
        return False


async def rows_for(session: AsyncSession, model: Any, mission_id: str) -> list[Any]:
    """All rows of a mission-scoped model (shortens the hot query shape)."""
    q = await session.execute(select(model).where(model.mission_id == mission_id))
    return list(q.scalars().all())


async def must_mission(session: AsyncSession, principal: Principal, mission_id: str) -> Mission:
    q = await session.execute(
        select(Mission).where(Mission.id == mission_id, Mission.tenant_id == principal.tenant_id)
    )
    m = q.scalar_one_or_none()
    if m is None:
        # Safe 404: same shape for missing and cross-tenant (no existence leak).
        raise HTTPException(status_code=404, detail="Not found.")
    await must_member(session, principal, m.workspace_id)
    return m


async def log_timeline(
    session: AsyncSession,
    *,
    tenant_id: str,
    mission_id: str,
    kind: str,
    payload: dict[str, Any],
    actor_id: str | None = None,
) -> TimelineEvent:
    ev = TimelineEvent(
        tenant_id=tenant_id, mission_id=mission_id, kind=kind, payload=payload, actor_id=actor_id
    )
    session.add(ev)
    await session.flush()
    return ev


async def aud(
    session: AsyncSession,
    request: Request,
    principal: Principal,
    action: str,
    mission: Mission | None = None,
    object_type: str = "",
    object_id: str | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> None:
    await append_event(
        session,
        tenant_id=principal.tenant_id,
        action=action,
        actor_id=principal.user_id,
        mission_id=mission.id if mission else None,
        request_id=get_request_id(request),
        object_type=object_type,
        object_id=object_id,
        after=after,
        reason=reason,
    )


def err(
    status: int,
    code: str,
    message: str,
    rid: str,
    details: dict[str, Any] | None = None,
) -> Any:
    return error_response(status, code, message, rid, details)


def not_found(request: Request, exc: Exception) -> Any:
    """Safe 404 for missing-or-other-tenant objects (no existence leak)."""
    status = getattr(exc, "status_code", 404)
    if status not in (403, 404):
        status = 404
    code = "forbidden" if status == 403 else "not_found"
    msg = "Not a workspace member." if status == 403 else "Not found."
    return error_response(status, code, msg, get_request_id(request))
