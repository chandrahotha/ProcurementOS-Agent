# ADR 0007 — Conflicts are detected, not overwritten

- **Status:** accepted
- **Date:** 2026-10-20
- **Related:** findings B45 (`bugs/01-backend.md`)

## Context

The analysis gate refuses to advance while `blocking_conflicts` is
non-zero. The counter was hardcoded to `0`, because corrections kept no
history: a second correction to the same evidence span simply overwrote
the first, and the last writer won.

`app/evidence/conflicts.py::three_way_diff` had been written for exactly
this case — a key is a conflict only when both sides differ from the base
*and* from each other — and was never wired to anything.

So the gate advertised a control it did not have. The audit deferred the
item because wiring it properly meant giving the evidence model a
"base" value, which the model did not have.

## Decision

Give the evidence span a base value and a conflict state, and use the
existing three-way diff.

- `pos_evidence_span.base_value` — the value the span held before anybody
  corrected it. It is the "base" of the diff.
- `pos_evidence_span.conflict_state` — `""` (no conflict), `"conflict"`
  (a correction disagreed and was refused), `"resolved"`.

A correction that disagrees with a pending one is **refused with 409** and
the stored value is left alone. No silent overwrite. A human resolves the
conflict by re-submitting either the base value (a revert) or the value
that is already stored (an agreement); both clear the conflict, because
in the three-way diff `theirs == base` and `mine == theirs` are both
non-conflicts.

The gate reads the real count: `blocking_conflicts` is the number of
spans in the mission whose conflict state is `conflict`.

## Consequences

- The analysis gate now refuses a mission with an unresolved correction
  conflict, which is what it always claimed to do.
- A conflict is recorded in the audit trail (`evidence_conflict`) and as a
  timeline event, so it is visible without reading the spans.
- The 409 response carries the base, current and proposed values, so the
  client can show the human what the disagreement is.
- Two extra columns and a migration (`pos_006`), both additive: an
  existing span has an empty base and no conflict, so no in-flight
  mission changes verdict.

## Brain refs

`prerequisite-docs/03_DOMAIN_MODEL.md` (evidence spans),
`prerequisite-docs/04_BUSINESS_RULES.md` (no silent overwrite; every
disagreement is a human decision).

## Rollback

`alembic downgrade -1` drops the two columns. The conflict state is
derived, so nothing outside the evidence model depends on it.
