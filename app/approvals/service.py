"""Approvals: policy evaluation, quorum, lanes, expiry, waivers (F13, F20).

Quorum model: a request creates one Approval row per required lane (same
payload_hash). Quorum met when every lane row is approved, unexpired, with
matching payload hash. Admin cannot approve (config-only).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals.policy import required_lanes
from app.audit.writer import payload_hash
from app.auth import roles as R
from app.models.foundation import Approval

EXPIRY_DAYS = 7


class ApprovalError(Exception):
    pass


def _expiry() -> str:
    return (datetime.now(UTC) + timedelta(days=EXPIRY_DAYS)).isoformat()


def _expired(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    try:
        exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        return datetime.now(UTC) > exp
    except Exception:
        return True


async def request_approval(
    session: AsyncSession,
    *,
    tenant_id: str,
    mission_id: str,
    action_class: str,
    payload: dict[str, Any],
    requested_by: str,
    value_minor: int = 0,
    threshold_minor: int = 5_000_000,  # €50k default
) -> list[Approval]:
    lanes = required_lanes(action_class, value_minor, threshold_minor)
    if not lanes:
        raise ApprovalError(f"unknown action class {action_class}")
    ph = payload_hash(payload)
    rows = []
    for lane in lanes:
        row = Approval(
            tenant_id=tenant_id,
            mission_id=mission_id,
            action_class=action_class,
            payload_hash=ph,
            payload_json=payload,
            lane=lane,
            requested_by=requested_by,
            approvers_required=1,
            decisions=[],
            status="pending",
            expires_at=_expiry(),
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


async def decide(
    session: AsyncSession,
    *,
    approval_id: str,
    tenant_id: str,
    principal_roles: list[str],
    principal_id: str,
    decision: str,
    reason: str = "",
) -> Approval:
    q = await session.execute(
        select(Approval).where(Approval.id == approval_id, Approval.tenant_id == tenant_id)
    )
    row = q.scalar_one_or_none()
    if row is None:
        raise ApprovalError("approval not found")
    if "Admin" in principal_roles:
        raise ApprovalError("Admin is config-only and cannot approve")
    allowed = R.LANE_ROLES.get(row.lane, [])
    if not set(principal_roles) & set(allowed):
        raise ApprovalError(f"lane {row.lane} requires {allowed}")
    if decision == "rejected" and not reason.strip():
        raise ApprovalError("reject requires a reason")
    if _expired(row.expires_at):
        row.status = "expired"
        await session.flush()
        raise ApprovalError("approval expired")
    decisions = list(row.decisions or [])
    decisions.append(
        {
            "user_id": principal_id,
            "decision": decision,
            "reason": reason,
            "at": datetime.now(UTC).isoformat(),
        }
    )
    row.decisions = decisions
    row.status = "approved" if decision == "approved" else "rejected"
    await session.flush()
    return row


async def quorum_met(
    session: AsyncSession,
    *,
    tenant_id: str,
    mission_id: str,
    action_class: str,
    payload: dict[str, Any],
) -> bool:
    lanes = required_lanes(
        action_class,
        int(payload.get("value_minor", 0)),
        int(payload.get("threshold_minor", 5_000_000)),
    )
    ph = payload_hash(payload)
    q = await session.execute(
        select(Approval).where(
            Approval.tenant_id == tenant_id,
            Approval.mission_id == mission_id,
            Approval.action_class == action_class,
            Approval.payload_hash == ph,
        )
    )
    rows = q.scalars().all()
    by_lane = {r.lane: r for r in rows}
    for lane in lanes:
        r = by_lane.get(lane)
        if r is None or r.status != "approved" or _expired(r.expires_at):
            return False
    return True
