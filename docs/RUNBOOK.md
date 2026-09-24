# Runbook — ProcurementOS-Agent (mirrors `10 §3` add-ons)

## Local runbook (binding order)

1. Install Node/Python deps (`npm install` in `web/`, `pip install -e ".[dev]"`).
2. Configure env from `.env.example` → `.env` (no values committed).
3. Start DB/queue/storage: `docker compose up postgres redis minio`.
4. Run migrations: `alembic upgrade head`.
5. Synthetic seed: `python seed/seed_pos.py --tenant SYN-TENANT-01`.
6. Start API/workers/web: `docker compose up api worker web` (or uvicorn + `python -m worker.task_worker` + `npm run dev --prefix web`).
7. Run tests: `pytest` then `npm run test --prefix web`.
8. Browser smoke: P01→P16 reachable, golden AGENT-001…004 green.

## CI order (binding)

lint → typecheck → unit → integration → security lint → dependency scan →
secret scan → build. AI-outage drill + hostile-doc suite run in integration.

## Environment separation / backup / flags

- Dev/staging/prod: separate credentials + DBs. Demo: own synthetic DB,
  nightly reset, no shared buckets/queues/keys with staging/prod.
- Backup: PITR + versioned storage; restore tested before every minor release.
- Forward-fix preferred; feature flags guard risky AI-touching tools
  (planner-assist, auto-retry escalation).
- AI outage posture: deterministic results stay available; AI jobs queue with
  retry + idempotency; source docs never lost; recovery replays queue without
  recomputing math.
