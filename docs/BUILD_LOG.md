# Build log — ProcurementOS-Agent

> Append-only journal. Newest entries on top. Each entry says what changed,
> how it was checked, and what is still open. Anything that bends the brain
> gets an ADR link, not a quiet edit.

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
