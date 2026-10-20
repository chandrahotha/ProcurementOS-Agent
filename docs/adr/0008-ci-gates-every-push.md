# ADR 0008 — CI gates every push; the heavy legs stay weekly

- **Status:** accepted
- **Date:** 2026-10-20
- **Related:** findings I6, I20, I25 (`bugs/04-infra-ci.md`)

## Context

The pipeline ran on a weekly cron and on manual dispatch. There were no
push or pull-request triggers.

That was a deliberate owner instruction at the time, recorded in the
build log: "the full pipeline runs ONCE per week — Monday 03:00 UTC".
The reasoning was cost. The cost is real: the heavy legs need a
Postgres service, a Redis service, three container builds and a Playwright
browser.

The problem is what "no push trigger" means in practice. A regression can
land on `main` and sit there for up to seven days, and the README's
"current check before every push" is a habit, not a gate. The full
pipeline is also not one pipeline: it is nine jobs, of which five need
nothing but Python and Node.

Separately, two tool pins were stale in a way that hid work:

- `ruff>=0.5,<0.6` and `mypy>=1.11,<1.12` excluded the current releases,
  so the code was never checked against them. The current releases found
  two `mypy --strict` errors and one formatting difference that the
  pinned versions accepted.
- `alembic>=1.13,<1.14` excluded the installed `1.14.0`.
- There was no Python lockfile, so two CI runs a week apart could
  resolve different versions of the same dependency.
- `S106` (hardcoded password) was ignored for *every* test, which meant a
  real credential in a test fixture would not have been flagged.

## Decision

Split the pipeline by cost, and gate the cheap half on every push.

- **Every push and pull request** (the fast chain): lint, typecheck,
  unit tests with a coverage floor, security lint, dependency audit,
  secret scan, and the web build/lint/typecheck/test.
- **Weekly schedule and manual dispatch** (the heavy chain): the
  Postgres migration + seed + PG-backed tests, the container builds, and
  the Playwright end-to-end walk.

Both chains are required. A push that breaks the fast chain fails; a
push that breaks the heavy chain is caught on the next weekly run, which
is the same guarantee the owner asked for, only applied to the part that
is cheap enough to run every time.

Tool pins are raised to the current releases, `S106` is scoped to the one
line that needs it, and a `requirements.lock` pins the dependency set.

### On the lockfile

The lock is checked for **consistency with the declared ranges**, not for
equality with a fresh resolution. A lockfile whose check re-resolves
"latest" on every run breaks the moment a new version is published —
which is a property of PyPI, not of this repository, and would make CI
fail for no reason. What must hold is that the lock still covers the
declared ranges, so a range bump without a refreshed lock fails.

## Consequences

- A regression is caught in minutes rather than up to seven days.
- The code is now checked against the current `ruff` and `mypy`, which
  found real issues that the stale pins were hiding.
- Dependency resolution is reproducible: the same pins every run.
- A hardcoded credential in a test is flagged by `S106` again.
- The `integration` marker is now real: `tests/test_postgres.py` uses it,
  so `pytest -m integration` collects tests instead of nothing. The
  weekly leg runs them against real Postgres.
- The weekly schedule is retained, so the owner's cost constraint is
  respected for the part that costs.

## Brain refs

`prerequisite-docs/09_TEST_PLAN.md` (every gate is a command whose result
is captured), `prerequisite-docs/10_SEED_DEMO_DEPLOY_ROADMAP.md` §3
(binding order).

## Rollback

Remove the `push` and `pull_request` triggers from `.github/workflows/ci.yml`
and the heavy chain returns to running weekly only.
