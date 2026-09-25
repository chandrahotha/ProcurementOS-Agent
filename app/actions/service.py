"""Action Center: dry-run preview -> approval check -> idempotent execute (F14, F21).

Dry-run renders ALLOW / DENY / NEEDS-APPROVAL with exact payload + policy cite.
Execute re-verifies payload hash == approved hash, enforces idempotency
(key = mission+action+version), and dispatches ONLY via registry.dispatch.
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals import service as approvals
from app.audit.writer import append_event, payload_hash
from app.models.mission import TimelineEvent
from app.tools import registry


class ActionBlockedError(Exception):
    pass


def dry_run(action_class: str, payload: dict[str, Any], quorum: bool) -> dict[str, Any]:
    # Verdict derives solely from server-computed quorum: the client-declared
    # payload_hash_match flag was removed (it was injected unconditionally by
    # the HTTP layer, making it meaningless).
    from app.approvals.policy import MATERIAL_CLASSES

    if action_class in MATERIAL_CLASSES:
        if quorum:
            return {
                "verdict": "ALLOW",
                "payload": payload,
                "policy": f"{action_class} quorum satisfied",
            }
        return {
            "verdict": "NEEDS-APPROVAL",
            "payload": payload,
            "policy": f"{action_class} requires quorum approval",
        }
    return {"verdict": "ALLOW", "payload": payload, "policy": "non-material"}


def idem_key(mission_id: str, action_class: str, version: str) -> str:
    raw = f"{mission_id}|{action_class}|{version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def _receipt(
    session: AsyncSession, tenant_id: str, mission_id: str, key: str
) -> TimelineEvent | None:
    # Receipt lookup is mission-scoped: the same key against a different
    # mission must never return the first mission's receipt.
    q = await session.execute(
        select(TimelineEvent).where(
            TimelineEvent.tenant_id == tenant_id,
            TimelineEvent.mission_id == mission_id,
            TimelineEvent.kind == "action_receipt",
        )
    )
    for ev in q.scalars().all():
        if (ev.payload or {}).get("idempotency_key") == key:
            return ev
    return None


async def execute(
    session: AsyncSession,
    *,
    tenant_id: str,
    mission_id: str,
    action_class: str,
    payload: dict[str, Any],
    tool_name: str,
    actor_id: str,
    request_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    # Idempotent replay: same key returns the original receipt.
    existing = await _receipt(session, tenant_id, mission_id, idempotency_key)
    if existing is not None:
        return {"receipt": existing.payload, "replayed": True}
    try:
        ok = await approvals.quorum_met(
            session,
            tenant_id=tenant_id,
            mission_id=mission_id,
            action_class=action_class,
            payload=payload,
        )
    except approvals.ApprovalError as e:
        # Server-side value check refused (e.g. AWARD without certified TCO).
        await append_event(
            session,
            tenant_id=tenant_id,
            action="award_blocked_no_approval",
            actor_id=actor_id,
            mission_id=mission_id,
            request_id=request_id,
            object_type="action",
            reason=f"{action_class} execute denied: {e}",
        )
        raise ActionBlockedError(f"{action_class} blocked: {e}") from e
    if not ok:
        await append_event(
            session,
            tenant_id=tenant_id,
            action="award_blocked_no_approval",
            actor_id=actor_id,
            mission_id=mission_id,
            request_id=request_id,
            object_type="action",
            reason=f"{action_class} execute denied: no quorum approval",
        )
        raise ActionBlockedError(f"{action_class} blocked: no quorum approval")
    # Payload-hash match is enforced by quorum_met (hash over exact payload).
    approval_id = payload_hash(payload)[:16]
    try:
        out = registry.dispatch(
            tool_name,
            dict(payload),
            actor_id=actor_id,
            approval_id=approval_id,
            idempotency_key=idempotency_key,
        )
    except (registry.UnknownToolError, registry.ToolDeniedError) as e:
        await append_event(
            session,
            tenant_id=tenant_id,
            action="action_blocked",
            actor_id=actor_id,
            mission_id=mission_id,
            request_id=request_id,
            object_type="action",
            reason=str(e),
        )
        raise ActionBlockedError(str(e)) from e
    receipt = {
        "mission_id": mission_id,
        "action_class": action_class,
        "tool": tool_name,
        "payload_hash": payload_hash(payload),
        "idempotency_key": idempotency_key,
        "result": out["result"],
    }
    session.add(
        TimelineEvent(
            tenant_id=tenant_id,
            mission_id=mission_id,
            kind="action_receipt",
            payload=receipt,
            actor_id=actor_id,
        )
    )
    await append_event(
        session,
        tenant_id=tenant_id,
        action="action_executed",
        actor_id=actor_id,
        mission_id=mission_id,
        request_id=request_id,
        object_type="action",
        after={"payload_hash": receipt["payload_hash"]},
    )
    await session.flush()
    return {"receipt": receipt, "replayed": False}
