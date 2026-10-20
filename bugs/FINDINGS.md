# Audit Findings — Master Index

Date: 2026-09-25 · Scope: full repo (backend, frontend, engine, tests, seed, infra) · Source: 4 parallel deep audits → 232 raw findings.

**Status after the six fix waves (2026-09-25): every item closed, none open, twelve deferred with a rationale.**

**Status after the completion pass (2026-10-20): 234 closed, 0 open, 0 deferred.**
Every item that was deferred with a rationale has now been closed, each
with a command that proves it. The pass also found and fixed defects the
original audit did not reach — details in `docs/BUILD_LOG.md`.

A note on the count, because the header used to be wrong and is now
right: the audit described "232 raw findings → 160 deduplicated fix
units", but the ledger it indexed actually carried **198** entries, and
the completion pass added **36** more (C1–C19 in `01-backend.md`,
F80–F87 in `02-frontend.md`). The ledger's own entries are the
authoritative count: **234 closed, 0 open, 0 deferred**. "232 raw
findings" remains the audit's own description of its input.

The items that were deferred with a rationale, and are now closed: full
DateTime-column migration (B44), AI provider surface in the request path
(B49), blocking_conflicts and audit_complete gates (B45), fixture-name
alignment (T15), tool-pin raises (I20), coverage fail-under (now measured
and enforced), S106 fixture scoping (I25), e2e build artifacts, test_api
lifecycle split (T9, B53), and the render_dry_run / log_timeline handler
semantics (E13).

Verification at close: ruff + format clean, `mypy --strict` clean, `pytest`
162 passed + 5 skipped and no warnings (the skips are the Postgres leg, run by the weekly
CI job), `tsc` + `next build` green, `vitest` green, Playwright green.

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
