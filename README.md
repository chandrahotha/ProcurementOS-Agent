# ProcurementOS-Agent — Autonomous Procurement Agent

Standalone procurement mission agent: intake → plan → evidence → analysis → scenarios → negotiation → approval → action → report — with its own deterministic engine and human approval gates for all material actions.

Deterministic math is the source of truth; AI explains and drafts only. Awards, money, contracts, and external messages never move without explicit human approval. Every material number traces to an evidence span or a reasoned waiver.

## Where this stands

The backend is built and tested end to end over HTTP (full mission walk W1→W8, auth matrix, idempotency, deny cases). The deterministic engine carries golden vectors. All four binding golden tests (AGENT-001…004) are real and green. Every screen is wired to the API, and the full W1→W8 walk passes as a Playwright suite against the sqlite-backed seeded stack. The Slice 15 design system is in: Tailwind 4 over the token contract, Inter + IBM Plex Mono, a persistent app shell (sidebar, topbar, command palette, theme toggle), real KPI dashboards, and all 40+ screens designed.

**Completion pass (2026-10-20).** The findings ledger is at **160 fixed, 0 deferred, 0 open** — every item the 2026-09-25 audit had deferred is closed, each with a command that proves it. Every box in `docs/RELEASE_GATE.md` that said "pending staging" is now answerable with a command, because the thing it needed exists: per-environment env templates and a checker, a reversible migration chain proven on every push, a backup/restore cycle that verifies the restore, a rollback drill that measures itself, an egress policy with a live-host SSRF drill, and metrics with a task-age alert.

**Research context (ADR 0011).** The artefact is stated in postgraduate-thesis terms. The reporting currency is **INR**, the dual-control threshold is **INR 5,00,000**, the corpus is a synthetic Indian supply chain (six suppliers across Coimbatore, Pune, Raipur, Rajkot, Vadodara and Stuttgart, one of them invoiced in USD so the FX path is exercised against an RBI-quoted rate), and the synthetic records carry opaque identifiers rather than placeholder trade names. Every claim the repository makes about itself carries an evidence class — **E1** executed here, **E2** computable but not executed in this environment, **E3** proposed — and the evaluation design, its oracles, its measures and its threats to validity are in [`docs/EVALUATION.md`](docs/EVALUATION.md). The works cited are in [`docs/REFERENCES.md`](docs/REFERENCES.md).

The defects the original audit did not reach are also fixed — including the AI result row that had never been written successfully, the credential-login path that had never run, a rate limiter that counted by address alone, the plan phase that could not execute its own tasks, and a client payload placeholder that made the action gate unreachable.

Current check before every push: `ruff check` + `ruff format --check` clean, `mypy --strict` clean, `pytest` 162 passed + 5 skipped with **no warnings** (the skips are the Postgres leg the weekly job runs), `tsc` + `next build` green, `vitest` green, Playwright green. CI runs the fast gate chain on **every push and pull request** and the heavy legs (Postgres migration + seed + PG tests, container builds, Playwright) weekly and on demand. Dependency trees audit clean: `pip-audit --strict` and `npm audit` (prod + dev) both report zero findings for project deps, and `requirements.lock` pins the resolved set.

Still open, and said so rather than papered over: a real IdP has never been run against a live issuer; the Postgres-backed leg is written and collected but was not executed locally, because the PostgreSQL installation on this machine aborts its background workers; and the operational drills have not been run against a deployed environment, because there is not one.

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
| 13 | All screens wired to the API (P02–P16, G13, G16) | Done | `web/app/**`, `web/e2e/full-flow.spec.ts` |
| 14 | Full W1–W8 Playwright walk on the seeded stack + CI e2e job | Done | `web/playwright.config.ts` (two-server boot) |
| 15 | Styling pass: Tailwind 4 design system, app shell, all screens | Done | `web/app/globals.css`, `web/components/`, `bugs/02-frontend.md` |
| 16 | Completion pass: every deferred finding closed, every release-gate box answerable with a command | Done | `docs/RELEASE_GATE.md`, `docs/BUILD_LOG.md`, `docs/adr/0006`–`0010` |
| 17 | Research framing: INR corpus, evidence classes, evaluation design, component library, plan execution | Done | `docs/adr/0011`, `docs/EVALUATION.md`, `docs/REFERENCES.md` |
| 18 | Staging deploy against a real IdP, restore and rollback rehearsal on the deployed environment, signed release + SBOM, empirical study on a labelled corpus | Next | `docs/RELEASE_GATE.md` § Still open |

Rule of thumb: the build is done and verified — every screen is wired, the
full mission walk passes end to end in CI, and the dependency tree audits
clean. What remains is operations (a staging deploy with a real IdP and a
rehearsal) and the empirical study. Open work is tracked as
[GitHub issues](https://github.com/chandrahotha/ProcurementOS-Agent/issues).

## Run it

```powershell
python scripts/demo.py
```

That seeds the synthetic tenant, builds three demo missions through the
real HTTP endpoints, starts the API and the web app, and prints the
credentials. The password for every seeded persona is `syn-Demo-2026!`;
the personas and what each may do are in the runbook. A guided walk
through the product — what each screen shows and why — is in
[`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md).

| | |
|---|---|
| Web app | http://localhost:3000 |
| API | http://localhost:8000/api/v1 (OpenAPI at `/docs`) |
| Screens | [`docs/screenshots/`](docs/screenshots) — captured with `npx --prefix web tsx web/scripts/screenshots.mts` |

## Repository layout

```text
/app/          ← FastAPI: missions, plans, tasks, ingest, evidence, engine glue,
│                 negotiation, approvals, actions, tools, ai, reports, audit, auth
/engine/       ← deterministic math: sourcing, supplier, cost, risk, scenarios
/worker/       ← RQ queue: task dispatch, retries, poison quarantine, in-process
│                 plan execution for deployments with no broker
/web/          ← Next.js 16 (App Router): P01–P16 + G screens, typed API client,
│                 component library (data / intel / panels)
/alembic/      ← migrations (pos_* schema, expand→migrate→contract)
/seed/         ← synthetic data only (SYNTHETIC-*, refuses prod DBs) + the
                 regenerable fixture corpus and the demo missions
/scripts/      ← operational tools: demo, backup/restore, rollback drill,
                 SSRF drill, task-age alert, env separation, lock, encoding
/tests/        ← pytest incl. AGENT-001…004 golden suites
/docs/         ← producer docs: build log, runbook, release gate, ADRs,
                 evaluation protocol, references, walkthrough
/prerequisite-docs/ ← product brain: vision, PRD, architecture, rules, UX, tests
```

- Start with [`prerequisite-docs/README.md`](prerequisite-docs/README.md) for the product index. The brain is the authoritative reference for every build step — do not edit it during implementation; record deviations as ADRs in `docs/adr/` (see `docs/README.md` for the current set).
- How to run it locally: [`docs/RUNBOOK.md`](docs/RUNBOOK.md). One command for the whole product: `python scripts/demo.py`. The e2e walk: `npm run e2e --prefix web`.
- Live endpoint inventory: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md). Release status per box: [`docs/RELEASE_GATE.md`](docs/RELEASE_GATE.md).
- The evaluation design, the evidence classes and the works cited: [`docs/EVALUATION.md`](docs/EVALUATION.md), [`docs/REFERENCES.md`](docs/REFERENCES.md).
- This product is fully independent: own database, schema, config, and backlog. Zero dependency on any sibling product (see `docs/adr/0001-standalone-no-sibling-coupling.md`).
