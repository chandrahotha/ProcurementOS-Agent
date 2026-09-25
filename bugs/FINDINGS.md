# Audit Findings — Master Index

Date: 2026-09-25 · Scope: full repo (backend, frontend, engine, tests, seed, infra) · Source: 4 parallel deep audits → 232 raw findings → **160 deduplicated fix units**.

**Status after the six fix waves: 148 fixed `[x]`, 12 deferred with rationale `[~]`, 0 open.**
Deferred items (with rationale in each file): full DateTime-column migration, AI provider surface in the request path, blocking_conflicts/audit_complete gates, fixture-name alignment, tool-pin raises, coverage fail-under (measured first), S106 fixture scoping, e2e build artifacts, test_api lifecycle split, render_dry_run/log_timeline handler semantics.

Verification at close: ruff + format clean, `mypy --strict` clean, `pytest` 59 green (incl. AGENT-001…004), `tsc` + `next build` green, `vitest` green, Playwright 3/3 (smoke, 360px approval, full W1→W8).

Status legend: `[ ]` open · `[x]` fixed · `[~]` partially fixed / deferred with ADR.

## Files

| File | Area | Findings |
|---|---|---|
| [01-backend.md](01-backend.md) | B1–B57: FastAPI app/, worker/ | 57 |
| [02-frontend.md](02-frontend.md) | F1–F72: web/ (bugs, UX, a11y, design, data) | 72 |
| [03-engine-tests.md](03-engine-tests.md) | E1–E14 + T1–T20: engine/, tests/, seed/ | 34 |
| [04-infra-ci.md](04-infra-ci.md) | I1–I17: CI, Docker, compose, config | 17 |

## Wave plan

1. **Wave 1 — Infra/CI** (I1–I17): unblocks CI verification; config-level edits.
2. **Wave 2 — Engine math** (E1–E14): money/state correctness is the product's source of truth; pinned with new vectors.
3. **Wave 3 — Backend** (B1–B57): security first (dual-control, injection, quarantine evasion), then robustness/perf, then contract gaps.
4. **Wave 4 — Frontend** (F1–F72): design system + app shell + all screens; preserves every e2e hook (`data-screen`, `role="status"` texts, `.gate-grid`/`.row`/`.approval-card`, exact button names).
5. **Wave 5 — Tests** (T1–T20): pin every fixed behavior; add missing edge/property coverage.
6. **Wave 6 — Verification**: ruff, mypy --strict, pytest, tsc, next build, vitest, Playwright W1→W8.

## Ground rules

- Every fix must keep the existing check suite green (README line 11 contract).
- e2e hooks are load-bearing: `main[data-screen='P01'…'P16']`, `role="status"` texts ("clean", "tasks", "Advanced to plan.", "8 spans recorded", "Version 1", "Quorum met", "ALLOW", "Executed.", "settled", "Exported", "Winner", "managerial", "objective", "Draft stored", "complete"), `.gate-grid` buttons ("Create mission", "Export"), `.row` buttons ("Generate plan", "Acknowledge plan", "Request approvals", "Dry-run", "Execute", "Mark actions settled"), `.approval-card` + "Approve", `input[type=file]`, `getByLabel("Title")`, `pos_token` localStorage key.
- Money stays in integer minor units; deterministic math stays the source of truth; AI explains/drafts only.
- Record deviations as ADRs in `docs/adr/`; log every wave in `docs/BUILD_LOG.md`.
