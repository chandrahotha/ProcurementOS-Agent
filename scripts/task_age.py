#!/usr/bin/env python3
"""Queue and task-age alerting.

The release gate asks for "Monitoring + queue/task-age alerts live". A
queue that stops draining is the failure this product is least able to
notice on its own: nothing raises, no request fails, the missions simply
stop moving. The only signal is the age of the oldest waiting task.

This is the alert. It reads the waiting tasks and exits non-zero when the
oldest one is older than the threshold, so it can be run from a cron, a
CI job, or a container health probe:

    python scripts/task_age.py --max-age 900
    python scripts/task_age.py --max-age 900 --json

Exit codes: 0 healthy, 1 the queue is stuck, 2 the check could not run.

It reads the database, not Redis: the tasks table is the record of what
is waiting, and it survives a Redis outage (which is exactly when the
alert matters most).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

#: Default threshold: a task waiting fifteen minutes is stuck.
DEFAULT_MAX_AGE_S = 900.0

#: Task states that count as "waiting".
WAITING = ("queued", "running")


async def _collect(db_url: str, tenant_id: str | None) -> dict[str, Any]:
    from sqlalchemy import select

    from app.db import get_session_factory
    from app.models.mission import MissionTask

    factory = get_session_factory(db_url)
    now = time.time()
    async with factory() as session:
        stmt = select(MissionTask).where(MissionTask.status.in_(WAITING))
        if tenant_id:
            stmt = stmt.where(MissionTask.tenant_id == tenant_id)
        rows = (await session.execute(stmt)).scalars().all()

    by_status: dict[str, int] = {}
    ages: list[float] = []
    oldest_key = ""
    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1
        created = row.created_at
        if created is None:
            continue
        stamp = created.timestamp()
        if stamp > now:  # clock skew: do not report a negative age
            continue
        age = now - stamp
        ages.append(age)
        if age == max(ages):
            oldest_key = row.key
    return {
        "depth": len(rows),
        "by_status": by_status,
        "oldest_task_age_s": round(max(ages), 3) if ages else 0.0,
        "oldest_task_key": oldest_key,
        "checked_at": now,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="async database URL (defaults to $DATABASE_URL)",
    )
    ap.add_argument("--tenant", default=None, help="limit the check to one tenant")
    ap.add_argument(
        "--max-age",
        type=float,
        default=DEFAULT_MAX_AGE_S,
        help="seconds a task may wait before it counts as stuck",
    )
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args(argv)

    if not args.db_url:
        print("no DATABASE_URL: cannot check the queue", file=sys.stderr)
        return 2

    try:
        state = asyncio.run(_collect(args.db_url, args.tenant))
    except Exception as exc:
        print(f"task-age check could not run: {exc}", file=sys.stderr)
        return 2

    stuck = state["oldest_task_age_s"] > args.max_age

    if args.json:
        print(json.dumps({**state, "stuck": stuck, "max_age_s": args.max_age}, indent=2))
    else:
        print(f"queue depth:        {state['depth']}")
        print(f"by status:          {state['by_status'] or '{}'}")
        print(f"oldest task age:    {state['oldest_task_age_s']:.1f}s")
        print(f"oldest task:        {state['oldest_task_key'] or '-'}")
        print(f"threshold:          {args.max_age:.1f}s")
        print(f"verdict:            {'STUCK' if stuck else 'healthy'}")

    if stuck:
        print(
            f"ALERT: a task has been waiting {state['oldest_task_age_s']:.0f}s "
            f"(threshold {args.max_age:.0f}s). The queue is not draining.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
