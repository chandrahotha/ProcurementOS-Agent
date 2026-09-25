# ADR-0003 — OR-Tools removed as a dependency; greedy allocator is the certified default

- Status: Accepted
- Date: 2026-09-24

## Context

The brain lists "OR-Tools for scenario optimization"
(`02_ARCHITECTURE.md` §1). OR-Tools was a Phase 0 dependency, but the
scenario engine's certified path was always the deterministic
capacity-aware allocator in `engine/scenario_opt.py`; the OR-Tools branch
was never wired. Meanwhile OR-Tools pins protobuf 5.x, which carried two
unresolved advisories in the dependency audit (issue #7).

## Decision

Drop the `ortools` dependency. `engine/scenario_opt.allocate()` remains
the single certified optimizer: deterministic, versioned, reproducible,
with infeasible-verdict + repair hints (POS-SCEN-01). If a solver upgrade
is ever justified, it lands behind the same tool boundary with golden
vectors — never as a silent dependency swap.

## Consequences

- `pip-audit` is clean for project dependencies; CI installs shrink by
  ~150 MB.
- Every scenario number traces to one implementation with one rule
  version — the audit story gets simpler, not harder.
- The "optimizer" API surface is unchanged; callers see no difference.

## Brain refs

- `02_ARCHITECTURE.md` §1 · `05_WORKFLOWS_AND_API.md` W4 ·
  `09_TEST_PLAN.md` POS-SCEN-01

## Rollback

Re-add `ortools` and wire it behind `scenario_opt` with golden vectors;
the brain's intent is optimization quality, which the greedy path
already satisfies for the capacity-constrained cases we certify.
