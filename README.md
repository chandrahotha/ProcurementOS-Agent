# ProcurementOS-Agent — Autonomous Procurement Agent

Standalone procurement mission agent: intake → plan → evidence → analysis → scenarios → negotiation → approval → action → report — with its own deterministic engine and human approval gates for all material actions.

Deterministic math is the source of truth; AI explains and drafts only. Awards, money, contracts, and external messages never move without explicit human approval. Every material number traces to an evidence span or a reasoned waiver.

## Where this stands

The backend is built and tested end to end over HTTP (full mission walk W1→W8, auth matrix, idempotency, deny cases). The deterministic engine carries golden vectors. All four binding golden tests (AGENT-001…004) are real and green. The web app builds with every route in place; Mission Control, Evidence, Approval, and Action Center are wired to the API.

Current check before every push: `ruff check` + `ruff format --check` clean, `mypy --strict` clean, `pytest` green, `next build` green, `vitest` green, Playwright smoke green.

## Roadmap

| # | Slice | Status | Evidence |
|---|---|---|---|
| 0 | Repo scaffold, compose stack, CI skeleton, producer docs | Done | `docs/BUILD_LOG.md` |
| 1 | Foundation: `pos_*` models, RBAC, hash-chained audit | Done | `tests/test_foundation.py` |
| 2 | Mission engine: state machine, plans, tasks, coverage gate | Done | `tests/test_phase9.py` |
| 3 | Deterministic engine + golden vectors | Done | `engine/tests/test_vectors.py` |
| 4 | Tool registry, approvals/quorum, dry-run + idempotent execute | Done | `tests/golden/test_agent_golden.py` (AGENT-001/002) |
| 5 | Quarantine pipeline + injection isolation | Done | `tests/test_ingest.py` (AGENT-003) |
| 6 | Ladders, AI fallback, hallucination scan, exports | Done | `tests/test_outage.py` (AGENT-004) |
| 7 | Full HTTP API: all endpoints, advance, envelope-on-every-error | Done | `tests/test_api.py` |
| 8 | Alembic `pos_001` + `pos_002`, round-trip verified | Done | `alembic/versions/` |
| 9 | OIDC JWKS validation, dev fallback fenced | Done | `tests/test_oidc.py` |
| 10 | Workers: enqueue, retry/backoff, poison quarantine | Done | `tests/test_workers.py` |
| 11 | Web: typed client, P01/P06/P13/P14 wired, drawer, palette, smoke | Done | `web/e2e/smoke.spec.ts` |
| 12 | Synthetic seed (7 users, 6 suppliers, 12 items, 24 txns) + fixtures | Done | `seed/seed_pos.py`, `seed/fixtures/` |
| 13 | Remaining screen data views (P02–P05, P07–P12, P15–P16, G tables) | Next | issue #6 (remaining) |
| 14 | Styling pass (Tailwind/shadcn over the token CSS) | Next | issue #6 (remaining) |
| 15 | Full W1–W8 Playwright run on seeded demo + rehearsal | Next | issue #6 (remaining) |
| 16 | Staging deploy, real IdP, rollback rehearsal, release gate sign-off | Next | `docs/RELEASE_GATE.md` |

Rule of thumb: about three-quarters of the MVP build is done and verified. What remains is mostly front-of-house (screens, styling, demo) and operations (staging, rehearsal). Open work is tracked as [GitHub issues](https://github.com/chandrahotha/ProcurementOS-Agent/issues).

## Repository layout

```text
/app/          ← FastAPI: missions, plans, tasks, ingest, evidence, engine glue,
│                 negotiation, approvals, actions, tools, ai, reports, audit, auth
/engine/       ← deterministic math: sourcing, supplier, cost, risk, scenarios
/worker/       ← RQ queue: task dispatch, retries, poison quarantine
/web/          ← Next.js 14: P01–P16 + G screens, typed API client, palette
/alembic/      ← migrations (pos_* schema, expand→migrate→contract)
/seed/         ← synthetic data only (SYNTHETIC-*, refuses prod DBs)
/tests/        ← pytest incl. AGENT-001…004 golden suites
/docs/         ← producer docs: build log, runbook, release gate, ADRs
/prerequisite-docs/ ← product brain: vision, PRD, architecture, rules, UX, tests
```

- Start with [`prerequisite-docs/README.md`](prerequisite-docs/README.md) for the product index. The brain is the authoritative reference for every build step — do not edit it during implementation; record deviations as ADRs in `docs/adr/`.
- How to run it locally: [`docs/RUNBOOK.md`](docs/RUNBOOK.md) (binding order: env → DB → migrate → seed → api/workers/web → tests → smoke).
- Live endpoint inventory: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).
- This product is fully independent: own database, schema, config, and backlog. Zero dependency on any sibling product (see `docs/adr/0001-standalone-no-sibling-coupling.md`).
