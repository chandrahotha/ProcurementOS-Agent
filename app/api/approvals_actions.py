"""Approvals + actions over HTTP (05 W6/W7, F13/F14/F20/F21)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.actions.service import dry_run as dry_run_eval
from app.actions.service import execute as execute_action
from app.actions.service import idem_key
from app.api.common import aud, err, must_mission, not_found
from app.approvals.service import ApprovalError, quorum_met, request_approval
from app.approvals.service import decide as decide_service
from app.auth.deps import Principal, get_principal
from app.auth.roles import ADMIN, BUYER, MANAGER
from app.core.envelope import ok
from app.core.request_id import get_request_id
from app.db import get_session

router = APIRouter()
WRITE_ROLES = {BUYER, MANAGER, ADMIN}


class ApprovalRequestBody(BaseModel):
    action_class: str
    payload: dict[str, Any]
    # value_minor/threshold deliberately absent: the server computes AWARD
    # value from certified CostResult rows and the threshold from the
    # tenant's rule version (brain 04 section 2). Client-declared value
    # cannot downgrade lanes.


class DecideBody(BaseModel):
    decision: str  # approved | rejected
    reason: str = ""


@router.post("/missions/{mission_id}/approvals")
async def request_approvals(
    mission_id: str,
    body: ApprovalRequestBody,
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
    try:
        rows = await request_approval(
            session,
            tenant_id=m.tenant_id,
            mission_id=m.id,
            action_class=body.action_class,
            payload=body.payload,
            requested_by=principal.user_id,
        )
    except ApprovalError as e:
        await session.rollback()
        return err(422, "approval_invalid", str(e), rid)
    await aud(
        session,
        request,
        principal,
        "approval_requested",
        m,
        "approval",
        rows[0].id,
        after={"action_class": body.action_class, "lanes": [r.lane for r in rows]},
    )
    await session.commit()
    return ok(
        {
            "approvals": [
                {"id": r.id, "lane": r.lane, "status": r.status, "expires_at": r.expires_at}
                for r in rows
            ]
        },
        rid,
    )


@router.post("/missions/{mission_id}/approvals/{approval_id}/decide")
async def decide_approval(
    mission_id: str,
    approval_id: str,
    body: DecideBody,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    rid = get_request_id(request)
    if body.decision not in ("approved", "rejected"):
        return err(422, "validation_error", "Decision must be approved or rejected.", rid)
    try:
        row = await decide_service(
            session,
            approval_id=approval_id,
            tenant_id=m.tenant_id,
            principal_roles=principal.roles,
            principal_id=principal.user_id,
            decision=body.decision,
            reason=body.reason,
        )
    except ApprovalError as e:
        await session.rollback()
        msg = str(e)
        code = 403 if ("lane" in msg or "Admin" in msg) else 422
        if "expired" in msg:
            code = 410
        return err(code, "approval_decide_failed", msg, rid)
    quorum = False
    try:
        quorum = await quorum_met(
            session,
            tenant_id=m.tenant_id,
            mission_id=m.id,
            action_class=row.action_class,
            payload=row.payload_json,
        )
    except ApprovalError:
        quorum = False
    await aud(
        session,
        request,
        principal,
        "approval_decided",
        m,
        "approval",
        row.id,
        after={"decision": body.decision, "quorum_met": quorum},
    )
    await session.commit()
    return ok({"id": row.id, "status": row.status, "quorum_met": quorum}, rid)


class DryRunBody(BaseModel):
    action_class: str
    payload: dict[str, Any]


@router.post("/missions/{mission_id}/actions/dry-run")
async def action_dry_run(
    mission_id: str,
    body: DryRunBody,
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
    try:
        quorum = await quorum_met(
            session,
            tenant_id=m.tenant_id,
            mission_id=m.id,
            action_class=body.action_class,
            payload=body.payload,
        )
    except ApprovalError as e:
        # Server-side value check refused (e.g. AWARD without certified TCO):
        # the dry-run must say NEEDS-APPROVAL with the reason, not 500.
        return err(422, "dryrun_refused", str(e), rid)
    verdict = dry_run_eval(body.action_class, dict(body.payload), quorum)
    await aud(
        session,
        request,
        principal,
        "action_dryrun",
        m,
        "action",
        None,
        after={"action_class": body.action_class, "verdict": verdict["verdict"]},
    )
    await session.commit()
    return ok({**verdict, "required_key": idem_key(m.id, body.action_class, "v1")}, rid)


class ExecuteBody(BaseModel):
    action_class: str
    payload: dict[str, Any]
    tool_name: str
    version: str = "v1"


@router.post("/missions/{mission_id}/actions/execute")
async def action_execute(
    mission_id: str,
    body: ExecuteBody,
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
    key = request.headers.get("Idempotency-Key", "")
    if not key:
        return err(422, "idempotency_required", "Idempotency-Key header is required.", rid)
    # Snapshot plain values: service.execute may roll back, which expires m.
    tenant_id, mission_id = m.tenant_id, m.id
    from app.actions.service import ActionBlockedError

    try:
        out = await execute_action(
            session,
            tenant_id=tenant_id,
            mission_id=mission_id,
            action_class=body.action_class,
            payload=body.payload,
            tool_name=body.tool_name,
            actor_id=principal.user_id,
            request_id=rid,
            idempotency_key=key,
        )
    except ActionBlockedError as e:
        await session.rollback()
        # The service rolled its own block audit back with the transaction,
        # so re-record it here to keep the denial in the trail.
        from app.audit.writer import append_event

        name = "award_blocked_no_approval" if "quorum" in str(e) else "action_blocked"
        await append_event(
            session,
            tenant_id=tenant_id,
            action=name,
            actor_id=principal.user_id,
            mission_id=mission_id,
            request_id=rid,
            object_type="action",
            reason=str(e),
        )
        await session.commit()
        return err(403, "action_blocked", str(e), rid)
    await session.commit()
    return ok(out, rid)
