# ADR 0011 — Thesis context: INR, evidence classes, and the implemented/proposed boundary

- **Status:** accepted
- **Date:** 2026-10-20
- **Related:** ADR 0006, ADR 0007, ADR 0008, ADR 0009, ADR 0010

## Context

The product is a research artefact: an autonomous agent for procurement
intake, sourcing and award, built to a standard intended for a
postgraduate thesis and a publishable paper. Three decisions follow from
that framing and none of them is a code change on its own.

**Currency.** The product reported and modelled amounts in EUR with
European supplier records. A procurement study in the Indian context has to
be denominated in INR, with a realistic cross-rate for imported
components, because the cost model, the approval thresholds and the
approval arithmetic all change when the magnitudes do.

**Identifier discipline.** The synthetic suppliers carried the
conventional placeholder trade name. A research artefact should not carry a
name that reads as a placeholder, and the seeded records should read as
what they are: synthetic records with opaque identifiers and a sector and
location descriptor.

**Evidence discipline.** A thesis has to distinguish what the artefact
*implements*, what it *proposes*, and what has been *experimentally
validated*. The repository already had a strong habit of not overstating
its own status — the release gate refused to claim a Postgres pass it had
not observed, and the findings ledger recorded deferred items with
rationale rather than quietly closing them. That habit is worth making
explicit and reusable, because it is the property that makes the rest of
the evidence readable.

## Decision

### 1. The reporting currency is INR

- The base currency of a mission, a workspace and a transaction is INR.
- The dual-control threshold on an award is INR 5,00,000
  (50,000,000 minor units), set on the tenant's rule version with the
  same value as the fallback default.
- Imported components keep a foreign-currency invoice; the seeded
  corpus carries one USD line so the FX path is exercised on every
  analysis run. The reference rate is quoted as USD/INR from the RBI.
- Money stays in integer minor units throughout. The migration from a
  EUR corpus to an INR one therefore changes the *labels* and the
  *magnitudes*, not the arithmetic: the engine was already
  currency-agnostic, and the golden vectors were re-derived rather than
  re-scaled, with the derivation written into the vector comments.

### 2. Synthetic records carry opaque identifiers

Supplier records are `SYN-SUP-01` … `SYN-SUP-06`, named by sector and
location (`SYN Precision Machining (Coimbatore)`). Part codes stay
descriptive (`SYN-BRKT-A`). No real organisation is named and no
placeholder-looking trade name is used.

### 2a. The product brain is not edited

`prerequisite-docs/` is the authoritative statement of the product and is
read-only during the build; a deviation is recorded here, never by
rewriting it. This ADR is that record: the brain's corpus paragraph still
describes the pre-migration supplier identifiers and the pre-migration
base currency, and it is left exactly as it was. The corpus in
`seed/` and the migration script implement the decision; the brain
remains the statement of intent, and this ADR states where the
implementation departs from it.

The migration script refuses the brain directory for the same reason, so
a future run cannot quietly rewrite it.

### 3. Three evidence classes, used consistently

Every claim the repository makes about itself is one of:

| Class | Meaning | Where it may be used |
|---|---|---|
| **E1 — executed** | A command in this repository produced the result, and the result is recorded | Findings ledger, release gate, evaluation report |
| **E2 — computable** | The result follows deterministically from committed inputs, but has not been executed in this environment | Release gate ("written and collected, not executed") |
| **E3 — proposed** | A design or a capability that is specified but not implemented | Roadmap, brain documents, ADRs |

A claim is never promoted to a stronger class without the corresponding
command and its recorded output. The release gate's "Still open" section
is where E2 and E3 live, and it is deliberately not empty.

### 4. The implemented / proposed / validated boundary is stated in the artefacts themselves

The README, the release gate and the build log each separate what the
system does from what it would do with more data, a live identity
provider or a deployed environment.

## Consequences

- The seeded corpus, the fixtures, the golden vectors, the demo mission
  and the documentation all carry INR magnitudes. The migration was
  scripted (`scripts/rename_synthetic_identifiers.py`) so it is
  reproducible rather than a one-off hand edit.
- The award arithmetic changed: a TCO of INR 6,00,000 is above the
  dual-control threshold where a TCO of EUR 60,000 was above the old
  one. The golden tests were re-derived to the new magnitudes and their
  intent — "a certified value above the threshold escalates to dual
  lanes" — is unchanged.
- A reader can tell, for any statement in the documentation, whether it
  was executed here, is computable, or is proposed. The most important
  instance is the Postgres-backed leg: written and collected (E2), not
  executed in this environment, because the local PostgreSQL installation
  aborts its background workers.
- The evaluation protocol (`docs/EVALUATION.md`) states the metrics, the
  dataset, the procedure and the current evidence class of every result.
  Results that have not been measured are not reported as results.

## Brain refs

`prerequisite-docs/03_DOMAIN_MODEL.md` (money in minor units),
`prerequisite-docs/04_BUSINESS_RULES.md` (the award threshold is a rule
version, not a constant), `prerequisite-docs/09_TEST_PLAN.md` (golden
vectors pin the deterministic behaviour).

## Rollback

The currency change is a data migration plus a re-derivation of the
golden vectors; reverting it means re-running the migration with EUR
magnitudes and restoring the previous vectors. The identifier change is
purely cosmetic. The evidence classes are a documentation convention with
no runtime effect.
