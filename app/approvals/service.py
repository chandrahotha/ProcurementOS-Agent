"""Approvals: policy evaluation, quorum, lanes, expiry, waivers (F13, F20).

Quorum model: a request creates one Approval row per required lane (same
payload_hash). Quorum met when every lane row is approved, unexpired, with
matching payload hash. Admin cannot approve (config-only).

Value is NEVER client-declared for AWARD (brain 04 section 2: "Value =
deterministic TCO of the action payload at current rule_version"). The
server reads the awarded supplier's latest certified CostResult and the
threshold from the tenant's active rule version. A forged low
value_minor in the payload cannot downgrade the lanes because both
request and quorum recompute them from certified rows.
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
from app.models.mission import CostResult, RuleVersion

EXPIRY_DAYS = 7
DEFAULT_THRESHOLD_MINOR = 5_000_000  # EUR 50k fallback when no rule row


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


async def certified_award_value(
    session: AsyncSession,
    *,
    tenant_id: str,
    mission_id: str,
    supplier_id: str,
) -> int:
    """Latest certified TCO for the supplier in this mission (minor units).

    Raises ApprovalError when no certified cost exists: an AWARD without
    analysis is refused rather than guessed.
    """
    q = (
        select(CostResult)
        .where(
            CostResult.tenant_id == tenant_id,
            CostResult.mission_id == mission_id,
            CostResult.supplier_id == supplier_id,
            # Stale-FX TCO never certifies an AWARD value (fail closed).
            CostResult.stale_flag.is_(False),
        )
        .order_by(CostResult.created_at.desc(), CostResult.id.desc())
        .limit(1)
    )
    row = (await session.execute(q)).scalar_one_or_none()
    if row is None:
        raise ApprovalError(
            f"no certified TCO for supplier {supplier_id!r}; "
            "run the analysis suite before requesting an AWARD"
        )
    return int(row.tco_minor)


async def rule_threshold(session: AsyncSession, tenant_id: str) -> int:
    """Dual-control threshold from the newest rule version (fallback 50k)."""
    q = (
        select(RuleVersion)
        .where(RuleVersion.tenant_id == tenant_id)
        .order_by(RuleVersion.created_at.desc())
        .limit(1)
    )
    rv = (await session.execute(q)).scalar_one_or_none()
    if rv is None:
        return DEFAULT_THRESHOLD_MINOR
    try:
        return int((rv.tolerances or {}).get("award_dual_control_minor", DEFAULT_THRESHOLD_MINOR))
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLD_MINOR


async def lanes_for(
    session: AsyncSession,
    *,
    tenant_id: str,
    mission_id: str,
    action_class: str,
    payload: dict[str, Any],
) -> list[str]:
    """Required lanes with server-side value for AWARD (brain 04 section 2).

    Non-AWARD classes have fixed lanes regardless of value, so their
    payload-declared value (if any) is irrelevant to lane selection.
    """
    if action_class == "AWARD":
        supplier_id = str(payload.get("supplier_id", ""))
        if not supplier_id:
            raise ApprovalError("AWARD payload must name a supplier_id")
        value = await certified_award_value(
            session, tenant_id=tenant_id, mission_id=mission_id, supplier_id=supplier_id
        )
        threshold = await rule_threshold(session, tenant_id)
    else:
        raw = payload.get("value_minor", 0)
        try:
            value = int(raw or 0)
        except (TypeError, ValueError):
            raise ApprovalError("value_minor must be a number") from None
        threshold = DEFAULT_THRESHOLD_MINOR
    return required_lanes(action_class, value, threshold)


async def request_approval(
    session: AsyncSession,
    *,
    tenant_id: str,
    mission_id: str,
    action_class: str,
    payload: dict[str, Any],
    requested_by: str,
) -> list[Approval]:
    # value_minor/threshold args intentionally removed from the signature:
    # the server computes them (see module docstring).
    lanes = await lanes_for(
        session,
        tenant_id=tenant_id,
        mission_id=mission_id,
        action_class=action_class,
        payload=payload,
    )
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
    if row.status != "pending":
        # Decisions are terminal: an approved/rejected/expired row can never
        # be flipped by a later decide call.
        raise ApprovalError(f"approval already {row.status}; decisions are terminal")
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
    # Lanes recomputed from certified rows: the payload hash locks WHAT was
    # approved; the server decides WHICH lanes that payload requires. A
    # payload the server cannot value (e.g. AWARD naming a supplier with no
    # certified TCO) can never satisfy quorum -> False, not an error.
    try:
        lanes = await lanes_for(
            session,
            tenant_id=tenant_id,
            mission_id=mission_id,
            action_class=action_class,
            payload=payload,
        )
    except ApprovalError:
        return False
    if not lanes:
        # Unknown action class: an empty lane set must never satisfy quorum.
        return False
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
