# Build log — ProcurementOS-Agent

> Append-only journal. Newest entries on top. Each entry says what changed,
> how it was checked, and what is still open. Anything that bends the brain
> gets an ADR link, not a quiet edit.

## 2026-09-24 — Issues 6+7 closed: security deps, all screens wired, full-flow E2E

- Deps (issue 7): the audit findings are gone. npm side: `next` 14→16.3.6
  via the official codemod (carries the December security patches; React 19),
  `vitest` 2→5 with `vite` 8 and `@types/node` 26 to settle the peer tree —
  `npm audit` now reports 0 in both prod and dev. Python side: dropped
  `python-jose` for `PyJWT` because jose drags `ecdsa`, which carries an
  unfixable advisory; tests mint real RSA tokens with PyJWT now. Also
  removed the unused `ortools` dependency (its protobuf 5 pin was the last
  flagged transitive). The codemod left an `export const instant = false`
  opt-out on 34 pages; removed them so Turbopack builds clean. One npm
  ERESOLVE knot took three tries to untangle — vitest 5's peers conflict
  with the @types/node 20 pin; bumping all three together resolved it.
- Screens (issue 6): P02 (create with workspace picker), P03 (upload +
  verdicts + generate plan + advance), P04 (DAG + acknowledge + advance),
  P05 (board + retry/review), P06 (quick-fill for the 8 required fields +
  coverage read + advance), P07 (analysis suite + rankings), P08 (TCO
  build-up table), P09 (risk bands), P10 (manual + optimizer + list),
  P11 (ladder + draft), P12 (brief + approval request), P13 (live approval
  queue + decide + quorum advance), P14 (dry-run/execute/settle + advance),
  P15 (runs + replay), P16 (export with download), G13 (audit table),
  G16 (rule versions). New backend reads to feed them: /workspaces,
  /missions/{id}/scenarios, /missions/{id}/approvals, /audit, /rules, plus
  POST /actions/settle for the action→report gate. CORS added for the web
  origin only. Seed now creates the demo workspace (all 7 users, roles per
  persona) and a rule_version row.
- E2E (issue 6): `web/playwright.config.ts` boots two servers — sqlite-backed
  API (seeded with SYNTHETIC data) plus `next start` — and the full-flow
  spec walks W1→W8 through the real UI: create → upload → plan ack →
  evidence quick-fill → analysis → scenario → draft → brief → two-lane
  approve (Manager + Finance) → quorum advance → dry-run → execute →
  settle → export → audit check. Green in ~8s. Three test bugs on the way,
  all mine: a double `dev-` prefix on tokens, decorative header buttons
  shadowing form buttons (scoped locators now), and expecting the Finance
  lane to advance a mission when advance is Writer-only.
- Still open: staging deploy with a real IdP + rehearsal (issue #8), the
  Tailwind/shadcn styling pass (kept hand-rolled token CSS for now —
  it implements the 06 §2 token contract), and worker-on-live-Redis drain.

Checks at close: ruff + format clean, `mypy --strict` clean (71 files),
`pytest` 42 passed, `tsc` clean, `next build` green (38 routes), `vitest`
green, Playwright 3/3 (smoke + 360px + full W1→W8).

## 2026-09-24 — Issues 1–6: API, migrations, OIDC, workers, web, E2E (done)

Closed 1–5, most of 6. Detail per issue is on GitHub; the short version:

- Issue 1 (API): `app/api/` now serves every 05 endpoint plus
  `POST …/advance` (state machine checked against live rows) and
  `POST …/evidence/spans` (extraction output / outage manual entry).
  `tests/test_api.py` walks W1→W8 over HTTP plus the auth matrix
  (401/403/404, cross-tenant, idempotency, smuggled export scope).
  Two real bugs found by the tests and fixed: FastAPI's default
  HTTPException handler was beating the envelope fallback (added explicit
  handlers so every error carries `request_id`), and touching an ORM object
  after `rollback()` blows up on async drivers (snapshot plain values first).
- Issue 2 (migrations): `pos_001` (28 tables, create-only) and `pos_002`
  (`oidc_sub`, batch mode for sqlite). Round-trip upgrade/downgrade/upgrade
  verified, `alembic check` reports zero drift. The `script.py.mako` stub
  had dropped the upgrade/downgrade placeholders — fixed before regenerating.
  Generated versions are excluded from E501/I001 by policy.
- Issue 3 (OIDC): JWKS validation with TTL cache, roles from workspace
  memberships, dev fallback dead when an issuer is set. Tests mint real
  RS256 tokens locally (valid, expired, wrong audience, unknown kid,
  tampered, unknown subject).
- Issue 4 (workers): `worker/queue.py` — RQ enqueue on `pos:*`, `apply_task`
  (autonomy check, registry-only dispatch, audit), jittered backoff,
  poison quarantine at 5 attempts. Tested without Redis.
- Issue 5 (web): typed client for all endpoints, P01/P06/P13/P14 wired,
  EvidenceDrawer, Cmd+K palette, 360px approval CSS. `tsc`, `next build`,
  `vitest` green. Styling is still hand-rolled token CSS, and the rest of
  the screens are shells — both noted in issue 6.
- Issue 6 (E2E/CI): Playwright smoke (P01 load, 360px approval) green,
  `seed/fixtures/` has HOSTILE-001/002 + a clean quote, CI integration job
  now points at the Postgres service for migrate+seed, new `e2e` job runs
  the smoke suite. What's left here: full W1–W8 click-through, the demo
  rehearsal, staging.

Postgres proof (local container, since removed): migrated both revisions,
seeded 7/6/12/24/13, then ran uvicorn against it — mission create, plan
generate (10 tasks), timeline, all 200. One false alarm on the way: a 500
from an inline TestClient script turned out to be TestClient-portal plus
asyncpg on Windows, not the app — the same calls pass under uvicorn.

Checks at push time: ruff + format clean, `mypy --strict` clean,
`pytest` green, `next build` + `vitest` + Playwright green.

## 2026-09-24 — Phases 1–9: backend, engine, gates, seed, web shell (done)

What went in:

- Phase 1: all `pos_*` tables as SQLAlchemy models (foundation + mission +
  a small `pos_transaction` ledger for the supplier KPIs), dev/test auth
  fallback next to the OIDC path, and the hash-chained audit writer.
- Phase 2: the mission state machine as pure logic with tests, the approval
  policy matrix, plan DAG validation/diff, and the coverage helper.
- Phase 3: the deterministic engine — money math in minor units (no floats),
  quote normalization, supplier KPIs, TCO waterfall with FX staleness flags,
  weighted risk bands, and a capacity-aware scenario allocator. Eight golden
  vectors cover mixed UOM/currency/tax, banker's rounding, thin data,
  infeasible constraints, and stale FX.
- Phase 4: closed 14-tool registry, per-lane approval requests with quorum
  checks, and dry-run plus idempotent execute. AGENT-001 and AGENT-002 are
  real tests now: unknown tools rejected, awards blocked without quorum,
  replay of the same idempotency key returns one receipt.
- Phase 5: quarantine pipeline (MIME/extension/magic-byte, size caps, macro
  rejection, SHA-256 versions) and the instruction scanner. AGENT-003 is a
  real test: hostile quote gets flagged, planning inputs stay clean, nothing
  is written, mission holds at evidence.
- Phase 6: negotiation ladders with walk-away enforcement, AI provider
  abstraction with circuit breaker and fallback, hallucination scan, and
  tenant-scoped exports. AGENT-004 is a real test: provider down, math and
  approvals still work, nothing fabricated.
- Phase 7: every screen exists as a route and builds — P01–P16, the G
  screens the release gate names (audit, rules, AI runs, integrations,
  security), plus login, docs, suppliers, reports, settings. `next build`
  passes, 38 routes. Bumped Next 14.2.5 to 14.2.35 for the December
  security patch; noted here so nobody wonders about the diff.
- Phase 8: `seed_pos.py` fills 7 users, 6 suppliers, 12 items, 24
  transactions (Nord capped at 2 for thin data, Delta carries a PPM spike),
  and 13 document rows including the three hostile fixtures. Idempotent —
  second run inserts zero rows. Refuses non-`SYN-` tenants and
  non-synthetic databases.
- Phase 9: negatives for coverage refusal, three-way correction conflicts,
  hallucination quarantine, cross-tenant denial, single-lane insufficiency
  over €50k, illegal state jumps, and bad DAGs.

How it was checked: `ruff check` clean, `ruff format --check` clean,
`mypy --strict` clean across 58 files, `pytest -q` 33 passed, `next build`
green. Seed run twice against throwaway sqlite to prove idempotency.

Bumps along the way, for the record:

- setuptools refused the flat layout, so `pyproject.toml` now names the
  packages explicitly.
- A bulk annotate pass for strict mypy briefly mangled one line in
  `auth/deps.py` and turned `§`/`€` into mojibake in six files (PowerShell
  re-encoding). Fixed by hand, then grepped the tree for stray `Â`.
- `q` as a reused query variable confused mypy's narrowing in the seed
  script; each loop now has its own (`uq`, `sq`, `iq`, `dq`).
- `UTC` import got eaten by `ruff --fix` mid-sequence because the usages
  landed after the import. Re-added, all green.

Still open (filed as GitHub issues, see below): HTTP routers are not mounted
yet — the services are tested through Python, but only `/healthz` answers
over HTTP. Alembic needs its first real migration. OIDC still needs JWKS
validation (fails closed today). Workers, frontend data wiring, Playwright
E2E, and a Postgres-backed CI leg are all queued.

## 2026-09-24 — Phase 0 scaffold (complete, verified)

- Evidence: `ruff check` + `ruff format --check` clean; `mypy` strict clean
  (29 files); `pytest -q` → 3 passed, 4 xfailed (AGENT-001…004 placeholders).
- Fix note: setuptools flat-layout discovery → added
  `[tool.setuptools.packages.find]` include list in `pyproject.toml`.
- Lint note: `S101` ignored in `tests/**` + `engine/tests/**`; E501 wrapped;
  `dict` → `dict[str, Any]` for strict mypy; import sorting via `ruff --fix`.

## 2026-09-24 — Phase 0 scaffold (in progress)

- Env verified: Python 3.12.10, Node v24.16.0 / npm 11.13.0, Docker 29.6.2, git 2.55.
- Pinned stack: Next.js 14.2.5 + React 18.3.1 + TS 5.5, FastAPI 0.115–0.116,
  SQLAlchemy 2 async, Alembic 1.13, Postgres 16, Redis 7, OR-Tools 9.11.
- Scaffold: `app/` (envelope + request_id + health + safe 500s), `worker/`,
  `alembic/`, `engine/tests/`, `tests/` (health green, AGENT-001…004 as strict-xfail
  placeholders), `web/` (tokens + P01 placeholder + typed client),
  `seed/seed_pos.py` (SYN- guard), compose + Dockerfiles, CI skeleton,
  LICENSE/SECURITY/CONTRIBUTING/CoC, docs/ + ADR-0001.
- Next: install deps, run pytest, verify health tests green.
