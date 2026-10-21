"""The audit chain: what "intact" means, and what it has to catch.

The chain stores a sequence but no sequence number. The writer links each
event to the previous event's hash, and the order used to be re-derived
from the rows with `ORDER BY created_at, id` - where `id` is a random
`uuid4().hex`, so two events that shared a timestamp were walked in a
random order and an intact chain was reported as broken. The order is
now carried by the timestamps, which are strictly increasing along the
chain, and the verifier follows the links rather than the rows.

These tests pin what "intact" means:

* a linear chain verifies;
* a tampered event is caught;
* an event removed from the middle is caught;
* a fork - two events claiming the same predecessor - is caught;
* events that share a timestamp still verify, because the order does not
  depend on the clock agreeing with itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audit.writer import append_event, chain_hash, event_body, verify_chain
from app.models.base import Base
from app.models.foundation import AuditEvent

TENANT = "t-audit"


@pytest.fixture()
async def session():
    """A session on a fresh in-memory database with the schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    mk = async_sessionmaker(engine, expire_on_commit=False)
    async with mk() as s:
        yield s
    await engine.dispose()


async def _chain(session: Any, n: int) -> list[AuditEvent]:
    """`n` events appended in order, committed."""
    events = []
    for i in range(n):
        ev = await append_event(
            session, tenant_id=TENANT, action=f"act_{i}", actor_id="a1", request_id=f"r{i}"
        )
        events.append(ev)
    await session.commit()
    return events


async def test_a_linear_chain_verifies(session: Any) -> None:
    events = await _chain(session, 5)
    result = await verify_chain(session, TENANT)
    assert result["intact"] is True
    assert result["events"] == 5
    assert result["broken_at"] is None
    # And it is rooted exactly once.
    roots = [e for e in events if e.prev_hash == "GENESIS"]
    assert len(roots) == 1


async def test_an_empty_chain_verifies(session: Any) -> None:
    result = await verify_chain(session, TENANT)
    assert result["intact"] is True
    assert result["events"] == 0


async def test_a_tampered_event_is_caught(session: Any) -> None:
    """Changing an event's body must break its hash."""
    await _chain(session, 4)
    await session.execute(
        update(AuditEvent)
        .where(AuditEvent.tenant_id == TENANT, AuditEvent.action == "act_2")
        .values(action="act_2_edited")
    )
    await session.commit()
    result = await verify_chain(session, TENANT)
    assert result["intact"] is False
    assert result["broken_at"] is not None


async def test_a_removed_event_is_caught(session: Any) -> None:
    """A hole in the middle leaves a successor pointing at nothing."""
    await _chain(session, 4)
    victim = (
        await session.execute(
            select(AuditEvent).where(AuditEvent.tenant_id == TENANT, AuditEvent.action == "act_1")
        )
    ).scalar_one()
    await session.execute(delete(AuditEvent).where(AuditEvent.id == victim.id))
    await session.commit()
    result = await verify_chain(session, TENANT)
    assert result["intact"] is False


async def test_a_fork_is_caught(session: Any) -> None:
    """Two events claiming the same predecessor is a fork, not a chain."""
    await _chain(session, 3)
    head = (
        await session.execute(
            select(AuditEvent)
            .where(AuditEvent.tenant_id == TENANT)
            .order_by(AuditEvent.created_at.desc())
            .limit(1)
        )
    ).scalar_one()
    # A second event with the same predecessor as the head.
    from app.models.foundation import AuditEvent as AE

    body = {
        "tenant": TENANT,
        "action": "forked",
        "actor": "a1",
        "mission": None,
        "object": ["", None],
        "before": "",
        "after": "",
        "request": "",
    }
    prev = head.prev_hash
    session.add(
        AE(
            tenant_id=TENANT,
            action="forked",
            actor_id="a1",
            prev_hash=prev,
            event_hash=chain_hash(prev, body),
            before_hash="",
            after_hash="",
            request_id="",
            created_at=head.created_at,
        )
    )
    await session.commit()
    result = await verify_chain(session, TENANT)
    assert result["intact"] is False


async def test_events_sharing_a_timestamp_still_verify(session: Any) -> None:
    """The order must not depend on the clock agreeing with itself.

    `id` is a random uuid, so a tie in `created_at` used to leave the
    order to chance, and the chain verified or not at random.
    """
    events = await _chain(session, 6)
    # Force every event onto the same timestamp: the worst case.
    stamp = datetime(2026, 1, 1, tzinfo=UTC)
    for ev in events:
        ev.created_at = stamp
    await session.commit()
    result = await verify_chain(session, TENANT)
    assert result["intact"] is True


async def test_the_timestamps_along_the_chain_increase(session: Any) -> None:
    """The order is carried by the timestamps, so they must not tie."""
    events = await _chain(session, 8)
    stamps = [e.created_at for e in events]
    assert stamps == sorted(stamps)
    assert len(set(stamps)) == len(stamps), "two events share a timestamp"


async def test_the_body_hashed_is_the_body_the_verifier_recomputes(session: Any) -> None:
    """The writer and the verifier must not drift apart."""
    events = await _chain(session, 2)
    for ev in events:
        assert ev.event_hash == chain_hash(ev.prev_hash, event_body(ev))
