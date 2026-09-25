# Runbook — ProcurementOS-Agent

Everything you need to run this product locally, verified on the current
tree. Binding order comes from `prerequisite-docs/10_SEED_DEMO_DEPLOY_ROADMAP.md` §3.

## Prerequisites

- Python 3.12+ and Node 20+ on PATH
- Docker (only for the full compose stack; the quick path needs nothing else)
- Ports free: 8000 (API), 3000 (web), 5432/6379/9000 (compose services)

## Quick start (sqlite, zero services)

The fastest way to see the whole product:

```powershell
pip install -e ".[dev]"
npm install --prefix web
npm run build --prefix web
npx --prefix web playwright install chromium --only-shell
npm run e2e --prefix web      # boots API + web, seeds SYNTHETIC data, walks W1->W8
```

The e2e config starts two servers itself: the API on `sqlite+aiosqlite:///./e2e_pos.db`
(seeded via `seed/seed_pos.py --tenant SYN-TENANT-01`) and `next start` on :3000.
Browse to http://localhost:3000/agent while the run is live and connect with a
seeded dev token (e.g. `dev-amara.buyer1@syn.example`) — roles map by persona:
buyers (`amara|luis|priya`), manager (`daniel`), finance (`fatima`), compliance (`chen`).
Dev tokens are a dev/test fallback only; they are unreachable once `OIDC_ISSUER`
is configured in the environment.

## Local development (compose stack)

1. Configure env from `.env.example` → `.env` (no values committed, ever).
2. Start services: `docker compose up -d postgres redis minio`.
3. Migrate: `alembic upgrade head` (set `DATABASE_SYNC_URL` if you override the default).
4. Seed (idempotent; refuses non-synthetic DBs):
   `python seed/seed_pos.py --tenant SYN-TENANT-01`
   Creates 7 users, the demo workspace (all users, roles per persona), a rule
   version (rv-1), 6 suppliers, 12 items, 24 transactions, 13 document rows
   including the hostile fixtures.
5. API: `python -m uvicorn app.main:app --reload --port 8000`
   Workers: `python -m worker.task_worker` (needs Redis).
   Web: `npm run dev --prefix web` (client code talks to :8000 by default).
6. Tests: `pytest -q` then `npm run test --prefix web`.

## CI order (binding)

lint → typecheck → unit → integration (postgres + redis services, migrate,
seed, golden suites) → security lint → dependency scan → secret scan →
build → e2e (two-server boot, full W1→W8 walk).

## Environment separation

- Dev / staging / prod: separate credentials and separate databases.
- Demo: its own synthetic DB, nightly reset, never shares buckets, queue
  namespaces, or keys with staging or prod.
- No production data in demo/seed — `SYNTHETIC-*` codes only, enforced by
  the seed guard and CI.

## Backup

- Point-in-time recovery where available, plus versioned object storage.
- Restore is exercised (not just scheduled) before every minor release.

## Rollback

- Prefer forward fixes; feature flags guard risky AI-touching tools
  (planner-assist, auto-retry escalation) so behavior can be disabled
  without a redeploy.
- Migration plan: expand → migrate → contract, downgrade tested in staging.
- Rollback drill: redeploy prior images + `alembic downgrade -1`, then
  re-run the AGENT-002/004 smokes. RTO ≤ 30 min, RPO ≤ 5 min (PITR).

## AI outage posture

Deterministic results stay available; AI jobs queue with retry and
idempotency; source documents are never lost (immutable versions persist
through the outage); recovery replays the queue without recomputing math.

## Known gaps (honest)

- Workers drain on live Redis in staging — not yet exercised.
- Real IdP (OIDC) wired but untested against an actual issuer — staging
  item (issue #8).
- The full findings ledger from the 2026-09-25 repo audit lives in `bugs/`
  (148 fixed, 12 deferred with rationale); the Tailwind 4 design system and
  app shell shipped as Slice 15.
