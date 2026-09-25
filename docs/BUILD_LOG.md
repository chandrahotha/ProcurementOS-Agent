# Build log — ProcurementOS-Agent

> Append-only journal. Newest entries on top. Each entry says what changed,
> how it was checked, and what is still open. Anything that bends the brain
> gets an ADR link, not a quiet edit.

## 2026-09-26 — 55→85 wave: real external actions, real auth, real AI touchpoint, staging rehearsal

- **Real external actions (the 'action' claim becomes real):** new
  `pos_purchase_order` / `pos_budget_reservation` / `pos_message_outbox`
  tables (pos_004). `issue_po_intent` now issues a real PO of record with a
  server-computed award value (never client-declared) and a deterministic
  PO number; `reserve_budget_intent` creates a real budget hold;
  `send_supplier_message` writes a transactional outbox row with
  transport-gated delivery (`OUTBOX_WEBHOOK_URL`; empty = stays queued — the
  approval is what authorized it either way). Execute receipts carry real
  object refs, and P14 shows a "Real objects of record" section. Read
  endpoints: `/purchase-orders`, `/budget-reservations`, `/messages`.
- **Real auth:** PBKDF2-SHA256 salted password login (stdlib only) +
  `pos_session` bearer tokens hashed at rest, expiry-bound, revocable.
  `POST /auth/login`, `/auth/me`, `/auth/logout`; sessions resolve before
  the dev fallback; the seed provisions the synthetic demo password. Web
  login takes email + password.
- **Real AI touchpoint:** `HttpxProvider` (server-side, schema-strict) +
  `run_with_fallback` + the hallucination scan wired into the Decision
  Brief when `AI_PRIMARY_BASE_URL` is configured; AIJob/AIResult rows
  persist with cited refs; the brief carries `ai: {ran, status}`; G17 lists
  the tenant's AI history. Unconfigured = deterministic notes only.
- **Staging rehearsal (in-network):** compose stack (Postgres 15432, Redis
  16379) — all four migrations ran on real Postgres, full seed, workers
  draining `pos:tasks` with unique per-instance names (RQ refuses duplicate
  worker names; container PID is always 1), real password login, and the
  full walk to a REAL executed PO with idempotent replay
  (`seed/rehearsal.py`). Docker Desktop on this machine dies between
  sessions, so host port-forwarding is flaky — the rehearsal runs
  in-network (`docker run --network ...`).
- **CI schedule (owner requirement, strict):** the full pipeline runs ONCE
  per week — Monday 03:00 UTC (~4x/month) — plus manual
  `workflow_dispatch`; no push/PR triggers (`gh workflow run ci` forces a
  run).

Checks: ruff + format clean, `mypy --strict` clean (72 files), `pytest` 59
green, `tsc` + `next build` + `vitest` green, lint 0 errors. Rehearsal
evidence as listed.


## 2026-09-25 — Full-repo audit (232 findings) + six fix waves + Slice 15 design system

Four parallel deep audits (backend, frontend, engine+tests, infra) produced
232 raw findings → 160 deduplicated fix units, all tracked in `bugs/`
(FINDINGS.md + one file per area, checkboxed). Fixed in six waves:

- **Wave 1 — Infra/CI** (bugs/04): CI now really runs dep-scan (`pip install -e .`
  before `pip-audit`), npm audit (prod+dev), web ESLint, and coverage
  (pytest-cov); compose `env_file` is optional so `docker compose build` works;
  redis got a health gate; actions pinned to SHAs; caching + concurrency +
  per-job timeouts + least-privilege permissions; all three Dockerfiles run
  non-root with prod-only deps, `npm ci`, and a standalone multi-stage web
  image; loopback port binds + healthchecks + restart policies + pinned
  images; dependabot.yml added; `.env.example` values blanked with unused keys
  marked; tsconfig hardened (`noUncheckedIndexedAccess`).
- **Wave 2 — Engine math** (bugs/03): per-box pricing honored via `price_uom`
  (ADR-0005 — the old math silently inflated 24×); duplicate-line flagging +
  `valid_until` expiry implemented; risk band StopIteration crash fixed;
  scenario_opt rejects negative costs / `max_suppliers=0` / fractional
  capacities; naive-datetime FX staleness fixed; three-way diff uses `base`;
  ladder rungs never overshoot below target (last rung = target exactly);
  savings baseline order-independent; reverse FX pairs invert; deterministic
  rank tie-breaks; tool registry handlers wired to real engine math; CSV/XLSX
  exports hardened (key union + formula-injection neutralization).
- **Wave 3 — Backend** (bugs/01): worker pipeline wired (acknowledge enqueues
  tasks); task select pins plan_version + unique index (pos_003); failed runs
  roll back partial results and never replay; evidence refs persist with real
  SourceLink ids; quarantine re-scans corrections; backward transitions
  role-gated; 500-class faults never masked as 404; dual control structural
  (managers out of finance/compliance lanes); production refuses to boot
  without OIDC; dev tokens hashed (seed repairs plaintext); JWKS fetched off
  the event loop with negative caching; upload byte cap + full-archive macro
  scan + filename sanitization; span documents validated (clean, in-mission);
  per-IP rate limiting; 422 envelope on malformed bodies; audit chain
  lock + ordering + full hashes + `/audit/verify`; healthz probes DB/Redis;
  S3 upload implemented; suppliers/profile/ai-jobs/notifications endpoints.
- **Wave 4 — Frontend** (bugs/02): Tailwind 4 design system (tokens, light+
  dark with contrast-fixed tones), Inter + IBM Plex Mono via next/font,
  persistent app shell (sidebar + topbar + theme toggle + user chip), Screen
  v2 (all nine states with skeletons/banners, linked breadcrumbs, wired
  primary buttons), command palette mounted globally (mission-aware, arrow
  keys, "/" focus, focus return), evidence drawer (focus trap, escape, error
  surface, per-span reset), real screens: Dashboard, Login (+persona
  quick-select), mission Overview + shared mission nav (14 screens one click
  away), Analytics, Search, Workspaces, Suppliers directory + profile,
  AI Runs, Documents, Reports, Notifications, Settings index; api-client
  hardened (text-first decode, shared error mapping, 401 → token clear +
  /login, missing client methods); error boundaries + not-found + loading.
- **Wave 5 — Tests** (bugs/03): expiry + terminal-decide golden tests,
  monotonic-backoff pin, ladder rung/bounds vectors, engine edge vectors
  (per-box, ties, composite-101, reverse FX, naive FX, negative costs),
  500/422 envelope pins with a crashing route, circuit-breaker persistence.
- **Wave 6 — Verification**: ruff + format clean, `mypy --strict` clean,
  `pytest` 59 green, `tsc` + `next build` + `vitest` green, Playwright 3/3
  (smoke, 360px approval, full W1→W8) with every e2e hook preserved.

Deferred with rationale (checkboxed `[~]` in bugs/): full DateTime-column
migration (schema change staged with the deploy), AI provider surface in the
request path, blocking_conflicts/audit_complete gates (need a
concurrent-correction structure), fixture-name alignment, tool-pin raises.

Checks: as listed in Wave 6. The e2e now runs against a sqlite-backed seeded
API (two-server boot); staging (issue #8) remains the ops item.

## 2026-09-24 — Brutal-audit fix 1 of N: server-computed award value

The self-audit's finding #1 was real: the approval lanes for an AWARD
trusted the caller's `value_minor` (brain 04 §2 says value is the
deterministic TCO at the current rule version, never client-declared).
A buyer could have declared `value_minor: 1` to dodge the Finance lane.

- `app/approvals/service.py` now computes AWARD value from the awarded
  supplier's latest certified `CostResult` and the dual-control threshold
  from the tenant's newest `RuleVersion` (seeded: EUR 50k). Both
  `request_approval` and `quorum_met` recompute lanes server-side, and a
  forged low value in the payload cannot downgrade anything — proven in
  AGENT-002 with `value_minor: 1` in the payload while the certified TCO
  (EUR 60k) still forces Manager + Finance.
- An AWARD naming a supplier with no certified TCO is refused outright
  (422 at request; blocked with an audit reason at execute) — no guessing.
- API body no longer carries value/threshold fields for approvals; the
  web client and P12 send a minimal hash-locked `{supplier_id}` payload.
- E2E follows the honest math: the demo mission's certified TCO (EUR 47.20)
  is under the threshold, so the walk now exercises a single managerial
  lane; the dual-lane path stays covered by AGENT-002 and POS-APPR-01
  with certified values above the threshold.
- Dependabot: pulled all 34 open alerts via the API and verified every one
  is stale — installed next 16.3.6 / postcss 8.5.23+ / vite 8.3.1 /
  vitest 5.0.1 all sit above their fix versions. They should auto-close
  when dependabot rescans after this push; stragglers get dismissed with
  evidence.

Checks: ruff + format clean, `mypy --strict` clean, `pytest` 42 green
(AGENT-002 strengthened), `tsc` + `next build` + `vitest` + Playwright 3/3
with the updated full-flow. Remaining audit findings (evidence links,
document bytes, real extractor, KPIs from ledger, chain verify, CONC-01,
GUARDED caps, rate limits, egress test, UX suite) are queued in the todo
list and land next.

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
