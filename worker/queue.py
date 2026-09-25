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


def backoff(attempt: int) -> float:
    """Exponential backoff with jitter, capped (seconds)."""
    # Jitter only spreads retries; not a security use (noqa S311).
    return min(float(2 ** max(0, attempt)) + random.uniform(0, 1), BACKOFF_CAP_S)  # noqa: S311


def should_quarantine(attempts: int) -> bool:
    return attempts >= MAX_ATTEMPTS


def enqueue_task(mission_id: str, task_key: str, idempotency_key: str) -> str:
    """Enqueue onto the pos: namespace. Returns the RQ job id."""
    from redis import Redis
    from rq import Queue

    from app.core.config import settings

    queue = Queue("pos:tasks", connection=Redis.from_url(settings.redis_url))
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
