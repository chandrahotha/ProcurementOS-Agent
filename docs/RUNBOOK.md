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

To browse it rather than test it, seed the database and start the two
processes:

```powershell
python seed/seed_pos.py --tenant SYN-TENANT-01 --db-url "sqlite+aiosqlite:///./pos_dev.db"
python seed/make_demo_mission.py --db-url "sqlite+aiosqlite:///./pos_dev.db"
$env:DATABASE_URL = "sqlite+aiosqlite:///./pos_dev.db"
python -m uvicorn app.main:app --port 8000
npm run start --prefix web
```

`make_demo_mission.py` builds three missions through the real HTTP
endpoints, so every screen has real data on first login: one walked to the
approval gate with a pending approval, one stopped at the analysis gate
with certified results, and one blocked in intake by a quarantined
document.

Sign in at http://localhost:3000/login with any seeded persona; the
password is `syn-Demo-2026!` for all of them, and the roles are

| Persona | Role |
|---|---|
| `amara.buyer1@syn.example` | Buyer |
| `luis.buyer2@syn.example` | Buyer |
| `priya.buyer3@syn.example` | Buyer |
| `daniel.manager@syn.example` | ProcurementManager |
| `fatima.finance@syn.example` | FinanceReviewer |
| `chen.compliance@syn.example` | ComplianceReviewer |
| `admin.seed@syn.example` | Admin |

The manager persona is the one that can walk the whole mission: the plan
acknowledgement, the gate advances and the managerial approval all require
it. A buyer is refused at those steps, correctly.

Dev tokens (`dev-{email}`, e.g. `dev-amara.buyer1@syn.example`) are a
dev/test fallback for the connect form on Mission Control. They are
unreachable once `OIDC_ISSUER` is configured.

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

**Every push and every pull request** (the fast chain): lint → typecheck →
unit (with a coverage floor) → security lint → dependency scan → secret
scan → web build/lint/typecheck/test.

**Weekly (Monday 03:00 UTC) and on manual dispatch** (the heavy chain):
the above, plus the Postgres leg (migration chain up/down/up, seed, and
the `integration`-marked tests against real Postgres) → container builds →
Playwright e2e.

Run the same gates locally before you push:

```powershell
python scripts/lock.py --check          # the lock still covers the declared ranges
python -m ruff check app worker engine seed tests alembic scripts
python -m ruff format --check app worker engine seed tests alembic scripts
python -m mypy app worker engine seed scripts
python -m pytest -q                     # 162 passed + 5 skipped (the skips need Postgres)
npm run typecheck --prefix web; npm run lint --prefix web; npm run build --prefix web
npm run test --prefix web
```

## Environment separation

Three templates, one per environment, and a checker that refuses a file
that has not been separated:

```powershell
Copy-Item deploy/env/dev.env.example .env            # local dev
Copy-Item deploy/env/staging.env.example .env.staging # staging
python scripts/verify_env.py --check-templates        # the templates are complete
python scripts/verify_env.py --env .env.staging --profile staging
```

The checker fails when a key is missing, when a `REPLACE_ME` placeholder
is still there, and — the one that matters — when a staging or production
file still carries a development credential such as `pos:pos` or
`redis://localhost:6379`. `alembic.ini` carries no password for the same
reason; the migration refuses to run without `DATABASE_SYNC_URL`.

## Operational drills

Each of these is a command with an exit code, so each can be a cron job,
a CI step or a probe.

```powershell
# Backup, checksum, restore, and verify the restore against the manifest.
python scripts/backup.py backup --out ./backups
python scripts/backup.py verify  ./backups/pos-<stamp>.sqlite
python scripts/backup.py restore ./backups/pos-<stamp>.sqlite --into ./restored.db

# Rollback: upgrade -> downgrade -1 -> upgrade, against a scratch database.
python scripts/rollback.py --db-url sqlite:///./rollback_scratch.db

# SSRF / egress, against a live local webhook host.
python scripts/ssrf_drill.py

# Queue and task age: exits non-zero when the oldest waiting task is stuck.
python scripts/task_age.py --max-age 900

# Encoding: fails on a text file that was written with the wrong code page.
python scripts/check_encoding.py

# The live endpoint inventory, generated from the OpenAPI schema.
python scripts/api_inventory.py
```

The demo is one command, and it is the quickest way to see the product with
data in it:

```powershell
python scripts/demo.py
```

It seeds the tenant, builds the three demo missions, starts both servers
and prints the credentials. `python scripts/demo.py --stop` stops them.

`scripts/rollback.py` refuses to run against a database whose name does
not look like a scratch one, so "downgrade one revision" can never be
pointed at the live database by accident.

## Monitoring

`app/core/observe.py` collects request count, error count and duration per
route, named application counters, and the queue depth with the age of
the oldest waiting task.

- `GET /api/v1/ops/metrics` — Prometheus text exposition (administrators
  only).
- `GET /api/v1/ops/queue-age` — the queue in JSON, with a `stuck` flag
  against the 900 s threshold (administrators only).

A queue that stops draining is the failure this product is least able to
notice on its own: nothing raises, no request fails, the missions simply
stop moving. `scripts/task_age.py` is the alert for it.

## Backup

- Point-in-time recovery where available, plus versioned object storage.
- `scripts/backup.py` writes a dump plus a manifest (sha256, the schema
  revision, the row count of every table) and the restore is *verified*
  against that manifest, so a restore that silently loses a table fails
  here rather than in production.
- Restore is exercised (not just scheduled) before every minor release.

## Rollback

- Prefer forward fixes; feature flags guard risky AI-touching tools
  (planner-assist, auto-retry escalation) so behavior can be disabled
  without a redeploy.
- Migration plan: expand → migrate → contract, downgrade tested in staging.
- Rollback drill: redeploy prior images + `alembic downgrade -1`, then
  re-run the AGENT-002/004 smokes. RTO ≤ 30 min, RPO ≤ 5 min (PITR).
  The database half is scripted and measured by `scripts/rollback.py`;
  the last measured drill took **5.96 s** against the 30-minute budget.

## AI outage posture

Deterministic results stay available; AI jobs queue with retry and
idempotency; source documents are never lost (immutable versions persist
through the outage); recovery replays the queue without recomputing math.
The circuit breaker is per process and has an explicit reset, so a
recovered provider is picked up without a restart.

## Known gaps (honest)

- A real IdP (OIDC) is wired and fail-closed but has never been run
  against a live issuer — staging item.
- The Postgres-backed leg (`tests/test_postgres.py`) is written and is
  collected by the weekly CI job, but it has not been executed locally:
  the PostgreSQL installation on this machine aborts its background workers
  (`STATUS_DLL_INIT_FAILED`) and takes the cluster down with them.
- The operational drills run against a scratch database and a local
  server. They have not been run against a deployed environment, because
  there is not one.
- No container image registry, no signed release, no SBOM.
- The findings ledger from the 2026-09-25 repo audit lives in `bugs/`
  (160 fixed, 0 deferred, 0 open after the 2026-10-20 completion pass).
