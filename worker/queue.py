"""Queue wiring: enqueue on pos:* namespace, execute via registry only.

- enqueue_task() is called when plans are acknowledged (API layer).
- apply_task() is the unit under test: policy check, dispatch, persist,
  retry accounting, poison quarantine. No Redis needed.
- run_task_job() is the RQ entrypoint used by live workers.
"""

from __future__ import annotations

import random
from typing import Any

MAX_ATTEMPTS = 5
BACKOFF_CAP_S = 300

#: How long to wait for Redis before deciding it is not there.
CONNECT_TIMEOUT_S = 1.0


def backoff(attempt: int) -> float:
    """Exponential backoff with jitter, capped (seconds)."""
    # Jitter only spreads retries; not a security use (noqa S311).
    return min(float(2 ** max(0, attempt)) + random.uniform(0, 1), BACKOFF_CAP_S)  # noqa: S311


def should_quarantine(attempts: int) -> bool:
    return attempts >= MAX_ATTEMPTS


def _connection() -> Any:
    """A Redis connection with short timeouts.

    The connect timeout matters: the acknowledge endpoint enqueues a plan's
    tasks, and a down Redis must not hold the request open. The default
    socket timeout is None, which means "wait forever" — one down Redis
    turned a single API call into a hang, once per task.
    """
    from redis import Redis

    from app.core.config import settings

    return Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=CONNECT_TIMEOUT_S,
        socket_timeout=CONNECT_TIMEOUT_S,
    )


def queue_available() -> bool:
    """True when the queue is reachable. One ping, one second, no retries."""
    try:
        return bool(_connection().ping())
    except Exception:
        return False


def enqueue_task(mission_id: str, task_key: str, idempotency_key: str) -> str:
    """Enqueue onto the pos: namespace. Returns the RQ job id."""
    from rq import Queue

    queue = Queue("pos:tasks", connection=_connection())
    job = queue.enqueue(
        "worker.queue.run_task_job",
        args=(mission_id, task_key),
        job_id=f"pos:{idempotency_key}",
        retry_kwargs={"max": MAX_ATTEMPTS, "interval": [backoff(i) for i in range(MAX_ATTEMPTS)]},
    )
    return str(job.id)


async def apply_task(
    session: Any,
    task: Any,
    *,
    actor_id: str,
    autonomy_level: str,
    request_id: str = "",
) -> dict[str, Any]:
    """Run one MissionTask row: policy -> dispatch -> persist. Returns outcome."""
    from app.approvals.policy import dial_allows_autonomy
    from app.audit.writer import append_event
    from app.tools import registry

    if task.status == "done":
        # Terminal short-circuit: re-running a completed task must not
        # re-dispatch the tool or append duplicate audit events.
        return {"status": "done", "reason": "already_done", "tool": task.tool_name}
    if task.status == "failed":
        return {"status": "failed", "reason": "quarantined", "tool": task.tool_name}
    tool = registry.ALLOWLIST.get(task.tool_name)
    if tool is None:
        task.attempts += 1
        task.status = "failed" if should_quarantine(task.attempts) else "blocked"
        task.activity_log = list(task.activity_log or []) + [
            {"event": "unknown_tool_blocked", "tool": task.tool_name}
        ]
        await append_event(
            session,
            tenant_id=task.tenant_id,
            action="unknown_tool_blocked",
            actor_id=actor_id,
            mission_id=task.mission_id,
            request_id=request_id,
            object_type="task",
            object_id=task.id,
            reason=f"closed registry rejected {task.tool_name!r}",
        )
        await session.flush()
        return {"status": task.status, "reason": "unknown_tool"}
    if not dial_allows_autonomy(autonomy_level, tool.autonomy_class):
        if autonomy_level == "ASSISTED":
            task.status = "needs_review"
            task.activity_log = list(task.activity_log or []) + [
                {"event": "confirm_required", "dial": autonomy_level}
            ]
            await session.flush()
            return {"status": "needs_review", "reason": "assisted_confirm"}
        task.status = "blocked"
        task.activity_log = list(task.activity_log or []) + [
            {"event": "material_needs_approval", "tool": tool.name}
        ]
        await session.flush()
        return {"status": "blocked", "reason": "approval_required"}
    try:
        registry.dispatch(
            tool.name,
            dict(task.args_json or {}),
            actor_id=actor_id,
            idempotency_key=task.idempotency_key or task.id,
        )
    except (registry.UnknownToolError, registry.ToolDeniedError) as e:
        task.attempts += 1
        task.status = "failed" if should_quarantine(task.attempts) else "blocked"
        task.activity_log = list(task.activity_log or []) + [
            {"event": "dispatch_denied", "error": str(e)}
        ]
        await session.flush()
        return {"status": task.status, "reason": str(e)}
    except Exception as e:
        # Runtime failures (bad args, engine errors) must still bookkeep (B14):
        # attempts increment, status moves, audit records — DB and queue state
        # never diverge silently.
        task.attempts += 1
        task.status = "failed" if should_quarantine(task.attempts) else "blocked"
        task.activity_log = list(task.activity_log or []) + [
            {"event": "dispatch_error", "error": str(e)}
        ]
        await append_event(
            session,
            tenant_id=task.tenant_id,
            action="task_failed",
            actor_id=actor_id,
            mission_id=task.mission_id,
            request_id=request_id,
            object_type="task",
            object_id=task.id,
            reason=str(e),
        )
        await session.flush()
        return {"status": task.status, "reason": str(e)}
    task.status = "done"
    task.result_ref = f"{tool.name}:{tool.version}"
    task.activity_log = list(task.activity_log or []) + [
        {"event": "tool_called", "tool": tool.name, "tool_version": tool.version}
    ]
    await append_event(
        session,
        tenant_id=task.tenant_id,
        action="task_completed",
        actor_id=actor_id,
        mission_id=task.mission_id,
        request_id=request_id,
        object_type="task",
        object_id=task.id,
        after={"tool": tool.name, "tool_version": tool.version},
    )
    await session.flush()
    return {"status": "done", "tool": tool.name}


def run_task_job(mission_id: str, task_key: str, actor_id: str = "worker") -> dict[str, Any]:
    """RQ job body: builds a session, loads the task row, applies it."""
    import asyncio

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.models.base import Base  # noqa: F401
    from app.models.mission import MissionTask

    async def _run() -> dict[str, Any]:
        engine = create_async_engine(settings.database_url)
        mk = async_sessionmaker(engine, expire_on_commit=False)
        async with mk() as session:
            from app.models.mission import Mission, MissionPlan

            # Keys repeat across plan versions (B2): pin the current plan
            # version so the select never raises MultipleResultsFound.
            plan_q = await session.execute(
                select(MissionPlan.version)
                .where(MissionPlan.mission_id == mission_id)
                .order_by(MissionPlan.version.desc())
                .limit(1)
            )
            version = plan_q.scalar_one_or_none()
            stmt = select(MissionTask).where(
                MissionTask.mission_id == mission_id, MissionTask.key == task_key
            )
            if version is not None:
                stmt = stmt.where(MissionTask.plan_version == version)
            stmt = stmt.order_by(MissionTask.plan_version.desc()).limit(1)
            q = await session.execute(stmt)
            task = q.scalar_one_or_none()
            if task is None:
                return {"status": "missing", "reason": "no such task"}
            m = await session.get(Mission, mission_id)
            autonomy = m.autonomy_level if m else "SUPERVISED"
            out = await apply_task(session, task, actor_id=actor_id, autonomy_level=autonomy)
            await session.commit()
            return out

    return asyncio.run(_run())


async def execute_plan_tasks(
    session: Any,
    mission_id: str,
    *,
    actor_id: str = "api",
    request_id: str = "",
    autonomy_level: str = "SUPERVISED",
) -> dict[str, Any]:
    """Run a mission's plan tasks in dependency order, in this process.

    The queue (Redis + a worker) is the production transport: the API
    enqueues, a separate worker executes. That is the right shape when a
    broker is available.

    When there is no broker — the zero-service local run the runbook
    promises, or a deployment whose Redis is down — the plan would
    otherwise sit acknowledged with every task in `queued` and nothing
    would ever happen to the mission. This is the fallback: the *same*
    `apply_task`, the same policy checks, the same autonomy dial, the same
    audit events. The only difference is that the work happens in the API
    process instead of in a worker.

    Dependency order is honoured, because a plan's DAG is the order the
    tools are meant to run in. A cycle is refused rather than half-run.
    """
    from sqlalchemy import select

    from app.models.mission import Mission, MissionPlan, MissionTask

    version_q = await session.execute(
        select(MissionPlan.version)
        .where(MissionPlan.mission_id == mission_id)
        .order_by(MissionPlan.version.desc())
        .limit(1)
    )
    version = version_q.scalar_one_or_none()
    if version is None:
        return {"ran": 0, "results": [], "reason": "no plan"}

    plan = (
        await session.execute(
            select(MissionPlan).where(
                MissionPlan.mission_id == mission_id, MissionPlan.version == version
            )
        )
    ).scalar_one_or_none()
    tasks = (
        (
            await session.execute(
                select(MissionTask).where(
                    MissionTask.mission_id == mission_id,
                    MissionTask.plan_version == version,
                )
            )
        )
        .scalars()
        .all()
    )
    if not tasks:
        return {"ran": 0, "results": [], "reason": "no tasks"}

    # The dependency graph lives in the plan's task specs, not on the task
    # rows: the rows carry the tool and its args, the specs carry the DAG.
    specs = list(plan.taskspecs or []) if plan is not None else []
    order = _dependency_order(specs)
    if order is None:
        return {"ran": 0, "results": [], "reason": "dependency cycle"}
    by_key = {t.key: t for t in tasks}
    ordered = [by_key[k] for k in order if k in by_key]
    # A task row the specs do not mention still runs, at the end: it is
    # part of the plan even if the spec list is incomplete.
    ordered += [t for t in tasks if t.key not in order]

    mission = await session.get(Mission, mission_id)
    autonomy = autonomy_level or (mission.autonomy_level if mission else "SUPERVISED")

    results: list[dict[str, Any]] = []
    for task in ordered:
        if task.status == "done":
            results.append({"key": task.key, "status": "done", "reason": "already_done"})
            continue
        outcome = await apply_task(
            session, task, actor_id=actor_id, autonomy_level=autonomy, request_id=request_id
        )
        results.append({"key": task.key, **outcome})
    return {"ran": len(results), "results": results, "plan_version": version}


def _dependency_order(specs: list[dict[str, Any]]) -> list[str] | None:
    """Order task keys so a task runs after everything it depends on.

    Returns None when the DAG has a cycle: a plan that cannot be ordered
    is refused, not half-executed.
    """
    known = {str(s.get("key", "")) for s in specs}
    ordered: list[str] = []
    placed: set[str] = set()
    remaining = list(specs)

    while remaining:
        progressed = False
        for spec in list(remaining):
            key = str(spec.get("key", ""))
            deps = [str(d) for d in (spec.get("depends_on") or []) if str(d) in known]
            if all(d in placed for d in deps):
                ordered.append(key)
                placed.add(key)
                remaining.remove(spec)
                progressed = True
        if not progressed:
            return None
    return ordered


async def ping_redis() -> bool:
    """Health probe for /healthz (B35): never raises, just reports."""
    try:
        from redis.asyncio import Redis

        from app.core.config import settings

        client = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        try:
            return bool(await client.ping())
        finally:
            await client.aclose()
    except Exception:
        return False
