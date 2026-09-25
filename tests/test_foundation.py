"""Phase 1: tenant isolation, RBAC map, audit hash chain (sqlite, no server)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audit.writer import append_event, chain_hash
from app.auth import roles as R
from app.models.base import Base
from app.models.foundation import Tenant, User


async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def test_tenant_isolation() -> None:
    mk = await _session()
    async with mk() as s:
        s.add(Tenant(id="t1", tenant_id="t1", name="T1"))
        s.add(Tenant(id="t2", tenant_id="t2", name="T2"))
        s.add(User(id="u1", tenant_id="t1", email="a@x.io", name="A"))
        s.add(User(id="u2", tenant_id="t2", email="a@x.io", name="B"))
        await s.commit()
        q1 = (await s.execute(select(User).where(User.tenant_id == "t1"))).scalars().all()
        q2 = (await s.execute(select(User).where(User.tenant_id == "t2"))).scalars().all()
        assert [u.id for u in q1] == ["u1"]
        assert [u.id for u in q2] == ["u2"]


async def test_role_maps_deny_by_default() -> None:
    assert R.BUYER in R.REQUEST_ROLES["mission.create"]
    assert R.FINANCE not in R.REQUEST_ROLES["plan.acknowledge"]
    # Dual control is structural: managers are out of finance/compliance
    # lanes so one user can never self-approve a dual-lane action.
    assert R.LANE_ROLES["finance"] == [R.FINANCE]
    assert R.LANE_ROLES["compliance"] == [R.COMPLIANCE]
    assert R.MANAGER not in R.LANE_ROLES["finance"]
    assert R.MANAGER not in R.LANE_ROLES["compliance"]
    assert "Ghost" not in R.ALL_ROLES


async def test_audit_chain_links() -> None:
    mk = await _session()
    async with mk() as s:
        e1 = await append_event(
            s, tenant_id="t1", action="mission_created", actor_id="u1", request_id="r1"
        )
        e2 = await append_event(
            s, tenant_id="t1", action="plan_proposed", actor_id="u1", request_id="r2"
        )
        assert e1.prev_hash == "GENESIS"
        assert e2.prev_hash == e1.event_hash
        assert e2.event_hash == chain_hash(
            e1.event_hash,
            {
                "tenant": "t1",
                "action": "plan_proposed",
                "actor": "u1",
                "mission": None,
                "object": ["", None],
                "before": e2.before_hash,
                "after": e2.after_hash,
                "request": "r2",
            },
        )
