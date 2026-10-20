"""Postgres-backed tests — the leg only a real Postgres can prove.

Marked `integration`, so the fast unit job skips them and the weekly heavy job
runs them against the `postgres:16-alpine` service.

Before this module the `integration` marker was registered in `pyproject.toml`
but used by no test anywhere: `pytest -m integration` collected zero tests and
the CI job that claimed to be the "Postgres leg" actually ran the sqlite suite
twice (finding I6). These tests make the marker real.

What only Postgres can answer, and what each test therefore asserts:

* the migration chain really produces every `pos_*` table (sqlite's
  `create_all` would paper over a missing revision),
* the chain is reversible — upgrade head, downgrade base, upgrade head again,
* the unique indexes the schema relies on actually reject a duplicate
  (sqlite does not enforce most of them),
* tenant scoping is enforced by the predicates the app uses, and
* the audit chain stays linear under concurrent appends from two sessions —
  a per-process `asyncio.Lock` cannot protect two processes, so the PG
  advisory lock is the only thing that can.

The tests build their own scratch database and drop it afterwards, so they
never collide with the seed the CI job runs against the main database.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.integration

SYNC_URL = os.environ.get("DATABASE_SYNC_URL", "")
ASYNC_URL = os.environ.get("DATABASE_URL", "")

#: Every table the app expects to exist after `alembic upgrade head`.
EXPECTED_TABLES = {
    "pos_tenant",
    "pos_user",
    "pos_session",
    "pos_role",
    "pos_workspace",
    "pos_supplier",
    "pos_supplier_site",
    "pos_item",
    "pos_document",
    "pos_document_version",
    "pos_evidence_span",
    "pos_transaction",
    "pos_ai_job",
    "pos_ai_result",
    "pos_approval",
    "pos_audit_event",
    "pos_mission",
    "pos_mission_plan",
    "pos_mission_task",
    "pos_mission_run",
    "pos_sourcing_result",
    "pos_cost_result",
    "pos_risk_result",
    "pos_scenario_result",
    "pos_source_link",
    "pos_rule_version",
    "pos_timeline_event",
    "pos_purchase_order",
    "pos_budget_reservation",
    "pos_message_outbox",
}


def _require_postgres() -> None:
    if not SYNC_URL or not ASYNC_URL:
        pytest.skip("DATABASE_SYNC_URL/DATABASE_URL not set — Postgres leg skipped")
    if not ASYNC_URL.startswith("postgresql"):
        pytest.skip("DATABASE_URL is not a Postgres URL — Postgres leg skipped")


def _scratch_db_name() -> str:
    return f"pos_itest_{uuid.uuid4().hex[:10]}"


def _admin_url() -> Any:
    """The maintenance database on the same server, as a sync URL."""
    url = make_url(SYNC_URL)
    return url.set(database="postgres")


def _scratch_urls(db_name: str) -> tuple[str, str]:
    sync = make_url(SYNC_URL).set(database=db_name)
    async_url = make_url(ASYNC_URL).set(database=db_name)
    return sync.render_as_string(hide_password=False), async_url.render_as_string(
        hide_password=False
    )


def _run_alembic(sync_url: str, action: str) -> None:
    """Run an alembic command against `sync_url` in-process."""
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(_repo_root() / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", sync_url)
    if action == "upgrade":
        command.upgrade(cfg, "head")
    elif action == "downgrade":
        command.downgrade(cfg, "base")
    else:  # pragma: no cover - programming error
        raise ValueError(f"unknown action {action!r}")


def _repo_root() -> Any:
    from pathlib import Path

    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def scratch_db() -> Iterator[tuple[str, str]]:
    """Create an isolated scratch database, migrate it, drop it afterwards."""
    _require_postgres()
    from sqlalchemy import create_engine

    db_name = _scratch_db_name()
    engine = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    engine.dispose()

    sync_url, async_url = _scratch_urls(db_name)
    try:
        _run_alembic(sync_url, "upgrade")
        yield sync_url, async_url
    finally:
        eng = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
        with eng.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
        eng.dispose()


@pytest.fixture()
async def pg_session(scratch_db: tuple[str, str]) -> AsyncIterator[AsyncSession]:
    """A session bound to the scratch database, rolled back after each test."""
    _, async_url = scratch_db
    engine = create_async_engine(async_url)
    mk = async_sessionmaker(engine, expire_on_commit=False)
    async with mk() as session:
        yield session
        await session.rollback()
    await engine.dispose()


def test_migration_chain_creates_every_pos_table(scratch_db: tuple[str, str]) -> None:
    """Every table the app queries exists after `alembic upgrade head`."""
    sync_url, _ = scratch_db
    from sqlalchemy import create_engine

    engine = create_engine(sync_url)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).scalars()
        found = set(rows)
    engine.dispose()

    missing = EXPECTED_TABLES - found
    assert not missing, f"migration chain did not create: {sorted(missing)}"


def test_migration_chain_is_reversible(scratch_db: tuple[str, str]) -> None:
    """upgrade head -> downgrade base -> upgrade head leaves the same schema.

    This is the expand->migrate->contract rehearsal the release gate asks
    for, executed against the real engine instead of scratch sqlite.
    """
    sync_url, _ = scratch_db
    from sqlalchemy import create_engine

    def _tables() -> set[str]:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            found = set(
                conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                ).scalars()
            )
        engine.dispose()
        return found

    before = _tables()
    _run_alembic(sync_url, "downgrade")
    after_down = _tables()
    _run_alembic(sync_url, "upgrade")
    after_up = _tables()

    assert EXPECTED_TABLES <= before
    assert not (EXPECTED_TABLES & after_down), "downgrade left pos_* tables behind"
    assert after_up == before, "re-upgrade produced a different schema"


async def test_unique_index_rejects_duplicate_user_email(pg_session: AsyncSession) -> None:
    """`ix_pos_user_tenant_email` is enforced by Postgres, not by luck."""
    from app.models.foundation import User

    tenant = "t-pg-uniq"
    for email in ("dup@syn.example",):
        pg_session.add(User(tenant_id=tenant, email=email, name="A"))
    await pg_session.flush()

    pg_session.add(User(tenant_id=tenant, email="dup@syn.example", name="B"))
    with pytest.raises(IntegrityError):
        await pg_session.flush()
    await pg_session.rollback()


async def test_tenant_predicate_isolates_rows(pg_session: AsyncSession) -> None:
    """A tenant-scoped query returns only that tenant's rows."""
    from sqlalchemy import select

    from app.models.foundation import User

    pg_session.add(User(tenant_id="t-pg-a", email="a@syn.example", name="A"))
    pg_session.add(User(tenant_id="t-pg-b", email="b@syn.example", name="B"))
    await pg_session.flush()

    rows = (
        (await pg_session.execute(select(User).where(User.tenant_id == "t-pg-a"))).scalars().all()
    )
    assert len(rows) == 1
    assert rows[0].email == "a@syn.example"


async def test_audit_chain_stays_linear_under_concurrent_appends(
    scratch_db: tuple[str, str],
) -> None:
    """Two concurrent sessions must not fork the hash chain.

    The writer holds a per-process `asyncio.Lock`; across two connections
    that lock protects nothing, so the chain's linearity is a property of the
    serialised read-modify-write plus the database's own transaction
    isolation. This test proves it on the engine that will actually run.
    """
    from app.audit.writer import append_event
    from app.models.foundation import AuditEvent

    _, async_url = scratch_db
    engine = create_async_engine(async_url)
    mk = async_sessionmaker(engine, expire_on_commit=False)
    tenant = "t-pg-audit"

    async def _append(n: int) -> None:
        async with mk() as session:
            await append_event(
                session,
                tenant_id=tenant,
                action=f"pg_concurrent_{n}",
                actor_id="pg-test",
            )
            await session.commit()

    try:
        await asyncio.gather(*(_append(i) for i in range(6)))
    finally:
        await engine.dispose()

    engine2 = create_async_engine(async_url)
    mk2 = async_sessionmaker(engine2, expire_on_commit=False)
    try:
        async with mk2() as session:
            from sqlalchemy import select

            events = (
                (
                    await session.execute(
                        select(AuditEvent)
                        .where(AuditEvent.tenant_id == tenant)
                        .order_by(AuditEvent.created_at, AuditEvent.id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(events) == 6
            # Each event must chain to its predecessor: exactly one GENESIS
            # root, and every other event's prev_hash is the previous event's
            # event_hash. A fork would show two roots or a dangling prev.
            roots = [e for e in events if e.prev_hash == "GENESIS"]
            assert len(roots) == 1, f"chain forked: {len(roots)} roots"
            for prev, cur in zip(events, events[1:], strict=False):
                assert cur.prev_hash == prev.event_hash, "chain broken between events"
    finally:
        await engine2.dispose()
