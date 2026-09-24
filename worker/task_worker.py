"""Task worker: executes MissionTasks ONLY via tools.registry.dispatch.

Policy: plan task (tool + typed args + idempotency key) -> autonomy check
-> dispatch -> result persisted + timeline event + evidence refs.
Retries with backoff; poison tasks quarantine after MAX_ATTEMPTS.
Run with live Redis: `python -m worker.task_worker`.
"""

from __future__ import annotations


def main() -> None:
    from redis import Redis
    from rq import Connection, Queue, Worker

    from app.core.config import settings
    from worker.queue import MAX_ATTEMPTS

    with Connection(Redis.from_url(settings.redis_url)):
        queue = Queue("pos:tasks")
        worker = Worker([queue], name="pos-task-worker")
        worker.work(max_jobs=MAX_ATTEMPTS * 100)


if __name__ == "__main__":
    main()
