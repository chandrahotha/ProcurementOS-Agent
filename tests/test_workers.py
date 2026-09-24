"""Issue 4: queue semantics without live Redis (apply_task on sqlite)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.foundation import AuditEvent
from app.models.mission import MissionTask
from worker.queue import MAX_ATTEMPTS, apply_task, backoff, should_quarantine


async def _task(tool="compute_tco", args=None, attempts=0):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    mk = async_sessionmaker(engine, expire_on_commit=False)
    async with mk() as s:
        t = MissionTask(
            tenant_id="t1",
            mission_id="m1",
            key="k",
            title="T",
            tool_name=tool,
            args_json=args or {},
            idempotency_key="idem-1",
            attempts=attempts,
        )
        s.add(t)
        await s.commit()
        await s.refresh(t)
        return mk, t.id


def test_backoff_grows_and_caps():
    for i in range(8):
        assert 0 <= backoff(i) <= 300
    assert backoff(100) == 300
    assert should_quarantine(MAX_ATTEMPTS) is True
    assert should_quarantine(MAX_ATTEMPTS - 1) is False


async def test_auto_tool_runs_and_audits():
    mk, tid = await _task()
    async with mk() as s:
        t = (await s.execute(select(MissionTask).where(MissionTask.id == tid))).scalar_one()
        out = await apply_task(s, t, actor_id="u1", autonomy_level="SUPERVISED", request_id="r1")
        assert out["status"] == "done" and t.result_ref.startswith("compute_tco:")
        evts = (await s.execute(select(AuditEvent))).scalars().all()
        assert any(e.action == "task_completed" for e in evts)


async def test_unknown_tool_blocks_then_quarantines():
    mk, tid = await _task(tool="raw_sql")
    async with mk() as s:
        t = (await s.execute(select(MissionTask).where(MissionTask.id == tid))).scalar_one()
        out = await apply_task(s, t, actor_id="u1", autonomy_level="SUPERVISED")
        assert out["status"] == "blocked" and t.attempts == 1
        evts = (await s.execute(select(AuditEvent))).scalars().all()
        assert any(e.action == "unknown_tool_blocked" for e in evts)
    mk2, tid2 = await _task(tool="raw_sql", attempts=MAX_ATTEMPTS - 1)
    async with mk2() as s:
        t = (await s.execute(select(MissionTask).where(MissionTask.id == tid2))).scalar_one()
        out = await apply_task(s, t, actor_id="u1", autonomy_level="SUPERVISED")
        assert out["status"] == "failed"  # poison quarantined


async def test_material_tool_without_approval_blocked():
    mk, tid = await _task(tool="send_supplier_message", args={"to": "s@x.io"})
    async with mk() as s:
        t = (await s.execute(select(MissionTask).where(MissionTask.id == tid))).scalar_one()
        out = await apply_task(s, t, actor_id="u1", autonomy_level="SUPERVISED")
        assert out["status"] == "blocked"


async def test_assisted_needs_confirm_without_dispatch():
    mk, tid = await _task()
    async with mk() as s:
        t = (await s.execute(select(MissionTask).where(MissionTask.id == tid))).scalar_one()
        out = await apply_task(s, t, actor_id="u1", autonomy_level="ASSISTED")
        assert out["status"] == "needs_review" and t.result_ref is None
