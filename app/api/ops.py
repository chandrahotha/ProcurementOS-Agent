"""Operations endpoints: metrics and queue state.

`/api/v1/ops/metrics` serves the Prometheus text exposition the app
collects (`app/core/observe.py`). `/api/v1/ops/queue-age` reports how many
tasks are waiting and how long the oldest one has been waiting — the
signal that a queue has stopped draining.

Both are administrator-only. Metrics and queue state describe how the
product is behaving internally, which is not something every caller in a
tenant should read.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import Principal, get_principal
from app.auth.roles import ADMIN
from app.core.envelope import ok
from app.core.observe import prometheus_text, set_queue_state
from app.core.request_id import get_request_id
from app.db import get_session
from app.models.mission import MissionTask

router = APIRouter()

#: A task waiting longer than this is "stuck" and should page someone.
STUCK_TASK_SECONDS = 900.0


@router.get("/ops/metrics")
async def ops_metrics(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Prometheus text exposition. Administrators only."""
    rid = get_request_id(request)
    if ADMIN not in principal.roles:
        from app.api.common import err

        return err(403, "forbidden", "Metrics are for administrators.", rid)
    # Refresh the queue gauges so the scrape is never stale.
    await _refresh_queue(session, principal.tenant_id)
    from fastapi import Response

    return Response(content=prometheus_text(), media_type="text/plain; version=0.0.4")


@router.get("/ops/queue-age")
async def ops_queue_age(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Queue depth and the age of the oldest waiting task."""
    rid = get_request_id(request)
    if ADMIN not in principal.roles:
        from app.api.common import err

        return err(403, "forbidden", "Queue state is for administrators.", rid)
    state = await _refresh_queue(session, principal.tenant_id)
    return ok(
        {
            **state,
            "stuck_task_seconds": STUCK_TASK_SECONDS,
            "stuck": state["oldest_task_age_s"] > STUCK_TASK_SECONDS,
        },
        rid,
    )


async def _refresh_queue(session: AsyncSession, tenant_id: str) -> dict[str, Any]:
    """Count the waiting tasks and find the oldest one."""
    rows = (
        (
            await session.execute(
                select(MissionTask.created_at).where(
                    MissionTask.tenant_id == tenant_id,
                    MissionTask.status.in_(("queued", "running")),
                )
            )
        )
        .scalars()
        .all()
    )
    now = time.time()
    ages: list[float] = []
    for created in rows:
        if created is None:
            continue
        stamp = created.timestamp()
        if stamp > now:  # a clock skew should not report a negative age
            continue
        ages.append(now - stamp)
    depth = len(rows)
    oldest = max(ages) if ages else 0.0
    set_queue_state(depth, oldest)
    return {
        "depth": depth,
        "oldest_task_age_s": round(oldest, 3),
        "waiting_tasks": depth,
    }
