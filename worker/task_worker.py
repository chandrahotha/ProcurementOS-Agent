"""Task worker: executes MissionTasks ONLY via tools.registry.dispatch (Phase 2+).

Policy: plan task (tool + typed args + idempotency key) -> policy check
(autonomy class + dial) -> enqueue (pos:* namespace) -> worker dispatches
-> result persisted + timeline event + evidence citations.
Retries with backoff+jitter; poison tasks quarantined after N attempts.
"""
