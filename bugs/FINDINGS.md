# Audit Findings — Master Index

Date: 2026-09-25 · Scope: full repo (backend, frontend, engine, tests, seed, infra) · Source: 4 parallel deep audits → 232 raw findings.

**Status after the six fix waves (2026-09-25): every item closed, none open, twelve deferred with a rationale.**

**Status after the completion pass (2026-10-20): 234 closed, 0 open, 0 deferred.**

**Status after the verification pass (2026-10-21): 238 closed, 2 open, 0 deferred.**
The whole fast gate chain was run against the tree on Windows. It found
three things that were wrong and one thing that was missing, and it found
them because the chain was actually executed rather than assumed. Two are
fixed here (C15, C16, C17 in `04-infra-ci.md`); two are recorded as open
with a diagnosis and a candidate fix, because fixing them properly is a
change to a security-critical path or to the CI account rather than a
patch (C18 in `04-infra-ci.md`, C20 in `01-backend.md`).

**Status after the credential pass (2026-10-21): 239 closed, 2 open, 0 deferred.**
The developer-token authentication path is gone (C21 in `01-backend.md`,
ADR 0012). There is one credential now: an email and a password, exchanged
for a session token. The `pos_user.api_token` column is dropped
(`pos_007`), and the tests sign in through the login endpoint rather than
around it.
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

Verification at the 2026-10-21 pass, on Windows, with the chain executed
rather than assumed: ruff + format clean, `mypy --strict` clean, `pytest`
162 passed + 5 skipped, `tsc` + `next build` green, `vitest` green, and
every drill green (`rollback.py`, `ssrf_drill.py`, `verify_env.py`,
`check_encoding.py`, `make_fixtures.py --check`). Two differences from the
claim above: the CI chain on `main` is red for a reason outside the code
(C18), and one audit test is intermittent (C20), so `pytest` is 162 passed
or 161 passed + 1 failed depending on the run.

Status legend: `[ ]` open · `[x]` fixed · `[~]` partially fixed / deferred with ADR.

## Files

| File | Area | Findings |
|---|---|---|
| [01-backend.md](01-backend.md) | B1–B57 + C1–C21: FastAPI app/, worker/ | 66 |
| [02-frontend.md](02-frontend.md) | F1–F87: web/ (bugs, UX, a11y, design, data) | 87 |
| [03-engine-tests.md](03-engine-tests.md) | E1–E14 + T1–T23: engine/, tests/, seed/ | 37 |
| [04-infra-ci.md](04-infra-ci.md) | I1–I38 + C1–C18: CI, Docker, compose, config | 50 |

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
