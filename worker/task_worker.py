"""Task worker: executes MissionTasks ONLY via tools.registry.dispatch.

Policy: plan task (tool + typed args + idempotency key) -> autonomy check
-> dispatch -> result persisted + timeline event + evidence refs.
Retries with backoff; poison tasks quarantine after MAX_ATTEMPTS.
Run with live Redis: `python -m worker.task_worker`.
"""

from __future__ import annotations


def main() -> None:
    import os

    from redis import Redis
    from rq import Connection, Queue, Worker

    from app.core.config import settings

    with Connection(Redis.from_url(settings.redis_url)):
        queue = Queue("pos:tasks")
        # Unique per instance: replicas share the queue and the container
        # main process is always PID 1, so the name carries a random suffix
        # (RQ refuses a duplicate worker name at birth).
        name = f"pos-task-worker-{os.getpid()}-{os.urandom(3).hex()}"
        worker = Worker([queue], name=name)
        worker.work()


if __name__ == "__main__":
    main()
