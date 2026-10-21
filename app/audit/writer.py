"""Append-only hash-chained audit writer (brain 03 §3, 08 T12)."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
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


def _tenant_lock_key(tenant_id: str) -> int:
    """A stable 64-bit key for a tenant, for the database's advisory lock.

    The key has to be the same in every process that appends to the
    tenant's chain, so it is derived from the tenant id rather than
    generated.
    """
    digest = hashlib.sha256(tenant_id.encode()).digest()[:8]
    return int.from_bytes(digest, "big", signed=True)


async def _serialise_appends(session: AsyncSession, tenant_id: str) -> None:
    """Serialise appends to one tenant across sessions and processes.

    The chain is a read-modify-write: read the head, link the new event
    to it, insert. The in-process `asyncio.Lock` above only covers one
    process, so on Postgres two requests could read the same head and
    both link to it - a fork, with two events claiming the same
    predecessor, and no way for the verifier to tell which came first.

    Postgres's transaction-scoped advisory lock closes that: the second
    appender blocks until the first has committed, so it sees the first's
    event and links to it. The lock is released by the commit, so it
    cannot outlive the transaction, and a crash cannot strand it.

    SQLite has no advisory locks and does not need them: it serialises
    writes itself, and the local engine is single-writer.
    """
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    import sqlalchemy as sa

    await session.execute(
        sa.text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": _tenant_lock_key(tenant_id)},
    )


def _as_utc(value: datetime | None) -> datetime | None:
    """A stored timestamp as an aware UTC datetime.

    A `DateTime(timezone=True)` column is timezone-aware on Postgres and
    naive on SQLite, which does not store an offset.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _next_created_at(last_created: datetime | None) -> datetime:
    """A timestamp strictly after the chain's previous event.

    The chain is a sequence, and the sequence has to be recoverable from
    the rows. `id` is a random `uuid4().hex` and cannot order anything, so
    the only ordering evidence is `created_at` - and two events written in
    the same microsecond (which happens, in one transaction, on a fast
    machine) would leave the order to the UUID. So the timestamp is
    nudged forward by a microsecond when the clock has not moved on.

    The chain is the truth about order, not the clock: an append-only log
    that could not say which of two events came first is not an audit
    trail. The nudge is bounded by the previous event, so it cannot drift
    ahead of real time by more than the number of events that shared a
    microsecond.
    """
    now = datetime.now(UTC)
    previous = _as_utc(last_created)
    if previous is None:
        return now
    candidate = previous + timedelta(microseconds=1)
    return candidate if candidate > now else now


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
        await _serialise_appends(session, tenant_id)
        hq = await session.execute(
            select(AuditEvent.event_hash, AuditEvent.created_at)
            .where(AuditEvent.tenant_id == tenant_id)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(1)
        )
        head = hq.first()
        prev = head[0] if head is not None else "GENESIS"
        last_created = head[1] if head is not None else None
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
            created_at=_next_created_at(last_created),
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

    The walk follows `prev_hash` backwards from the chain's head rather
    than re-deriving the order from the rows. It used to order by
    `(created_at, id)` and walk forwards, and that was wrong twice over:
    `id` is a random `uuid4().hex`, so two events sharing a timestamp
    were walked in a random order, and an intact chain was reported as
    broken. The chain is a linked list, and a linked list is verified by
    following the links - the rows' physical order is not evidence of
    anything.
    """
    from sqlalchemy import select

    q = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
    rows = (await session.execute(q)).scalars().all()
    if not rows:
        return {"intact": True, "events": 0, "broken_at": None}

    by_hash: dict[str, AuditEvent] = {}
    for ev in rows:
        by_hash.setdefault(ev.event_hash, ev)
    pointed_at = {ev.prev_hash for ev in rows}
    # The head is the event no other event points at. There must be
    # exactly one: two would be a fork, none would mean every event is
    # somebody's predecessor, which is a cycle.
    heads = [ev for ev in rows if ev.event_hash not in pointed_at]
    if len(heads) != 1:
        return {
            "intact": False,
            "events": len(rows),
            "broken_at": heads[0].id if heads else None,
        }

    ev = heads[0]
    walked = 0
    while True:
        # An event's own hash is the hash of its body chained to its
        # predecessor, so a tampered body cannot keep its hash.
        if chain_hash(ev.prev_hash, event_body(ev)) != ev.event_hash:
            return {"intact": False, "events": len(rows), "broken_at": ev.id}
        walked += 1
        if ev.prev_hash == "GENESIS":
            # The root of the chain.
            break
        nxt = by_hash.get(ev.prev_hash)
        if nxt is None:
            # A row was removed from the middle of the chain: its
            # successor points at a hash that no longer resolves.
            return {"intact": False, "events": len(rows), "broken_at": ev.id}
        ev = nxt
    if walked != len(rows):
        # Rows exist that the head's chain does not reach: a fork, with
        # two events claiming the same predecessor.
        return {"intact": False, "events": len(rows), "broken_at": heads[0].id}
    return {"intact": True, "events": len(rows), "broken_at": None}


async def chain_intact(session: AsyncSession, tenant_id: str) -> bool:
    """True when the tenant's audit chain re-walks without a break.

    The action->report gate asks for this: a mission may not be reported as
    complete while the trail that records what happened to it is broken.
    """
    return bool((await verify_chain(session, tenant_id))["intact"])
