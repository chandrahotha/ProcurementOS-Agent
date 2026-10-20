"""Append-only hash-chained audit writer (brain 03 §3, 08 T12)."""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.foundation import AuditEvent

# Per-tenant in-process lock (B32): concurrent requests in one worker can
# never fork the chain. Cross-process (multi-worker) interleave is rare and
# additionally ordered by (created_at, id) so the head is unambiguous.
_tenant_locks: dict[str, asyncio.Lock] = {}


def _canon(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def chain_hash(prev: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256(f"{prev}|{_canon(payload)}".encode()).hexdigest()


def payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canon(payload).encode()).hexdigest()


async def append_event(
    session: AsyncSession,
    *,
    tenant_id: str,
    action: str,
    actor_id: str | None = None,
    mission_id: str | None = None,
    request_id: str = "",
    object_type: str = "",
    object_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
    source: str = "api",
) -> AuditEvent:
    # prev chain head: latest event_hash for tenant (fallback GENESIS),
    # ordered by (created_at, id) so same-timestamp events never fork (B32).
    lock = _tenant_locks.setdefault(tenant_id, asyncio.Lock())
    async with lock:
        hq = await session.execute(
            select(AuditEvent.event_hash)
            .where(AuditEvent.tenant_id == tenant_id)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(1)
        )
        prev = hq.scalar_one_or_none() or "GENESIS"
        before_h = payload_hash(before or {})
        after_h = payload_hash(after or {})
        body = {
            "tenant": tenant_id,
            "action": action,
            "actor": actor_id,
            "mission": mission_id,
            "object": [object_type, object_id],
            "before": before_h,
            "after": after_h,
            "request": request_id,
        }
        ev = AuditEvent(
            tenant_id=tenant_id,
            actor_id=actor_id,
            mission_id=mission_id,
            request_id=request_id,
            object_type=object_type,
            object_id=object_id,
            action=action,
            before_hash=before_h,
            after_hash=after_h,
            prev_hash=prev,
            event_hash=chain_hash(prev, body),
            reason=reason,
            source=source,
        )
        session.add(ev)
        await session.flush()
        return ev


def event_body(ev: AuditEvent) -> dict[str, Any]:
    """The canonical body a chain hash is computed over.

    Kept next to the writer so the writer and the verifier cannot drift
    apart: a verifier that hashed a different body would report every
    event as tampered, or none.
    """
    return {
        "tenant": ev.tenant_id,
        "action": ev.action,
        "actor": ev.actor_id,
        "mission": ev.mission_id,
        "object": [ev.object_type, ev.object_id],
        "before": ev.before_hash,
        "after": ev.after_hash,
        "request": ev.request_id,
    }


async def verify_chain(session: AsyncSession, tenant_id: str) -> dict[str, Any]:
    """Re-walk the tenant's hash chain end to end.

    Returns `{"intact": bool, "events": n, "broken_at": id | None}`. A chain
    is intact when every event's `prev_hash` is its predecessor's
    `event_hash`, the first event roots at GENESIS, and every stored hash
    matches the hash recomputed from the event body.
    """
    from sqlalchemy import select

    q = (
        select(AuditEvent)
        .where(AuditEvent.tenant_id == tenant_id)
        .order_by(AuditEvent.created_at, AuditEvent.id)
    )
    rows = (await session.execute(q)).scalars().all()

    prev = "GENESIS"
    broken_at: str | None = None
    for ev in rows:
        if ev.prev_hash != prev or chain_hash(prev, event_body(ev)) != ev.event_hash:
            broken_at = ev.id
            break
        prev = ev.event_hash
    return {"intact": broken_at is None, "events": len(rows), "broken_at": broken_at}


async def chain_intact(session: AsyncSession, tenant_id: str) -> bool:
    """True when the tenant's audit chain re-walks without a break.

    The action->report gate asks for this: a mission may not be reported as
    complete while the trail that records what happened to it is broken.
    """
    return bool((await verify_chain(session, tenant_id))["intact"])
