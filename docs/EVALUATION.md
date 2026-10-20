# Evaluation protocol

The evaluation design for the procurement agent, with the evidence class of
every current result stated explicitly (ADR 0011). A result is reported
here only if a command in this repository produced it; a capability that is
specified but not measured is listed as a protocol, not as a result.

## 1. What is being evaluated

The system under study is a deterministic procurement agent. It runs a
mission through nine gated states — intake, plan, evidence, analysis,
scenarios, negotiation, approval, action, report — and produces a ranked
supplier decision that a human authorises before anything is committed to
the record.

The claim the evaluation is designed to test is narrow and falsifiable:

> The agent produces a procurement decision that is **traceable** to
> evidence and **constrained** by gates, and the deterministic parts of the
> decision are **reproducible** across runs and implementations.

It is *not* a claim that the agent outperforms a human buyer, nor that the
ranking matches a commercial benchmark. No experiment in this repository
supports either, and none is claimed.

## 2. Design

The evaluation is a **fixture-based counterfactual study** with three
arms, run over a synthetic corpus whose construction is fixed and
regenerable (`seed/make_fixtures.py`, deterministic output).

| Arm | Description | Isolates |
|---|---|---|
| **A — Deterministic engine** | The engine's own outputs on the golden vectors | Arithmetic correctness, not the agent |
| **B — Full agent** | The mission walk end to end over HTTP, with the gates live | The agent's orchestration, gating and provenance |
| **C — Agent minus a control** | The same walk with one control disabled (a gate opened, the scan skipped, the dial raised) | The marginal contribution of each control |

Arm C is the methodological core: a control that changes nothing is not a
control, and a control whose removal changes the outcome is the only
evidence that it was doing work.

### 2.1 Corpus

| Property | Value | Source |
|---|---|---|
| Suppliers | 6 (5 domestic, 1 imported) | `seed/make_fixtures.py` |
| Items | 12 | `seed/seed_pos.py` |
| Quotation lines | 4 per analysis run (3 INR, 1 USD) | `seed/make_demo_mission.py` |
| Currency | INR base; USD/INR at 83.50 (synthetic) | `seed/make_fixtures.py` |
| Documents | 13, of which 3 are hostile | `seed/make_fixtures.py` |
| Hostile documents | 1 instruction-injection payload, 1 OCR-poisoned copy, 1 macro-bearing package | `seed/make_fixtures.py` |
| Missions | 3 (one per state) | `seed/make_demo_mission.py` |

The corpus is **synthetic throughout**. It exercises the arithmetic, the
gates and the quarantine; it carries no empirical claim about any real
market, supplier or price.

### 2.2 Ground truth

There is no ground-truth "correct supplier" in a synthetic corpus. The
evaluation therefore uses three **oracle** definitions, each derived from
the engine rather than from an external answer key:

- **O1 — arithmetic oracle.** The expected value of every certified
  figure is recomputed independently from the fixture inputs, using the
  published conventions (integer minor units, banker's rounding per line
  then integer sum, 8-decimal FX rate, reverse-pair inversion by
  division). Any disagreement between the engine and the oracle is a
  defect in one of them.
- **O2 — provenance oracle.** Every certified figure carries at least one
  evidence reference, and every reference resolves to a span in the
  mission, which itself resolves to a document of a known quarantine
  verdict.
- **O3 — control oracle.** For each control, the expected outcome of the
  walk is determined by construction: a hostile document must not reach a
  planner; a payload that was edited after approval must not execute; a
  rejected approval must not produce a receipt.

### 2.3 Measures

| Measure | Definition | Target |
|---|---|---|
| **M1 — arithmetic agreement** | Certified figures matching O1, over all figures produced in a run | 100% |
| **M2 — provenance completeness** | Certified figures with a resolvable evidence reference (O2) | 100% |
| **M3 — reference resolution** | Evidence references resolving to a span, and spans to a document | 100% |
| **M4 — quarantine efficacy** | Hostile documents quarantined, and zero hostile spans reaching a planner's arguments (O3) | 100% |
| **M5 — gate efficacy** | Transitions refused when their precondition is unmet, and permitted when met (O3) | 100% |
| **M6 — hash-lock integrity** | Executes refused when the payload hash does not match the approved one | 100% |
| **M7 — determinism** | Identical inputs producing byte-identical certified results across N runs | 100% |
| **M8 — determinism across implementation** | The engine's golden vectors matching the independent oracle (M1) | 100% |
| **M9 — degradation isolation** | With the model provider unavailable, certified results unchanged and the failure recorded rather than hidden | 100% |
| **M10 — dual control** | A decision-maker unable to approve a row in a lane they are not entitled to, and unable to approve their own request | 100% |

M1–M3, M6 and M10 are **properties of the design**: they are asserted by
the test suite, not estimated from a sample. They are reported as
executable evidence (E1). M4, M5, M7, M8 and M9 are measured over the
fixture corpus and the golden vectors.

### 2.4 Procedure

```powershell
# A — deterministic engine (golden vectors, including the edge cases)
python -m pytest -q engine/tests

# B — full agent, over HTTP, with the gates live
python -m pytest -q tests

# C — control ablations: each control is disabled and the walk re-run
python -m pytest -q tests/test_gates_and_tools.py   # gate efficacy (M5)
python -m pytest -q tests/test_ingest.py            # quarantine efficacy (M4)
python -m pytest -q tests/golden                    # hash lock, dual control (M6, M10)
python -m pytest -q tests/test_ai_path.py           # degradation isolation (M9)
```

The Postgres-backed arm (`tests/test_postgres.py`, marked `integration`)
runs the same walks against a real PostgreSQL instance. It is collected by
every run and executed only by the weekly CI job.

## 3. Results

### 3.1 Executed (E1)

| Measure | Result | Evidence |
|---|---|---|
| M1 — arithmetic agreement | 19 of 19 golden vectors agree with the oracle | `python -m pytest -q engine/tests` |
| M2 — provenance completeness | Every certified figure in every test fixture carries a reference | `tests/golden/test_agent_golden.py` |
| M3 — reference resolution | Evidence references resolve to spans and spans to documents | `tests/test_api.py::test_full_mission_walk` |
| M4 — quarantine efficacy | Hostile payload flagged; no hostile span reaches a planner's arguments | `tests/test_ingest.py::test_agent_003_hostile_quote_contained` |
| M5 — gate efficacy | The analysis gate refuses an unresolved conflict and admits once it is cleared | `tests/test_gates_and_tools.py::test_a_conflict_blocks_the_analysis_gate` |
| M6 — hash-lock integrity | An edited payload matches no approval row and is refused | `tests/golden/test_agent_golden.py` (AGENT-002) |
| M8 — cross-implementation agreement | The golden vectors are the independent statement of the expected values | `engine/tests/test_vectors.py` |
| M9 — degradation isolation | A dead provider leaves the certified figures unchanged and records the failure | `tests/test_ai_path.py::test_provider_outage_degrades_without_moving_the_numbers` |
| M10 — dual control | A manager cannot decide the finance lane; a requester cannot self-approve | `tests/test_api.py::test_the_finance_lane_cannot_decide_a_managerial_row` |

The suite is **162 passed, 5 skipped**. The five skips are the
Postgres-backed tests, whose status is E2 (below).

### 3.2 Computable but not executed here (E2)

| Item | Why it is not E1 | How to make it E1 |
|---|---|---|
| The five Postgres-backed tests | The PostgreSQL 18 installation on this machine aborts its background workers with `STATUS_DLL_INIT_FAILED` and takes the cluster down, so the leg cannot be run locally | Run `pytest -m integration` against `postgres:16-alpine`; the weekly CI job does exactly this |
| The full 3-mission walk on a deployed environment | There is no deployed environment | Deploy to staging and run `seed/rehearsal.py` |
| Behaviour against a live identity provider | The OIDC path is fail-closed and the tests mint real RS256 tokens, but no live issuer has been used | Point `OIDC_ISSUER` at a staging issuer and run the walk |

### 3.3 Proposed but not implemented (E3)

These are specified in the product brain and are **not** claims. Each
would need its own arm C to be credible.

| Proposed capability | Why it is not implemented | What it would need |
|---|---|---|
| Extraction of quote fields from real PDFs (OCR, table parsing) | The extraction is currently manual entry; a real extractor is a separate subsystem with its own accuracy evaluation | A labelled corpus of real quotations and a field-level precision/recall measurement against human annotation |
| A supplier registry sourced from an external system | No external system is in scope for this artefact | A data-access agreement and a reconciliation procedure against the source |
| A negotiated-outcome measurement (did the award price match the BATNA?) | The outcome data does not exist in the synthetic corpus | A post-award observation window and a pre-registered outcome definition |
| Comparative evaluation against a human buyer or a commercial sourcing tool | Would require human subjects or a commercial licence | An ethics approval and a study protocol |

## 4. Threats to validity

Stated so they can be addressed rather than discovered.

**Construct validity.** The oracles are derived from the same engine the
system uses. This is a real weakness: M1 and M8 would not detect an error
that is consistent between the implementation and the oracle. It is
mitigated by writing the expected values as literals in the golden
vectors, with the derivation in the comment, so the oracle is a separate
statement rather than a second call into the same code. It is not fully
eliminated, and a hand-computed fixture set from an independent source
would be the next step.

**Internal validity.** Arm C re-runs the same fixture corpus with one
control disabled. Because the corpus is small and fixed, a control that
happens not to be exercised by this corpus would show no effect. The
corpus was constructed to exercise each control, and the ablations are
asserted in the test suite rather than observed in aggregate; a larger
corpus with randomised case generation would strengthen the claim.

**External validity.** Every result is on a synthetic corpus. Nothing here
establishes that the ranking matches what a procurement professional would
choose, or that the gates match a real approval policy. The corpus
supports claims about *mechanism* (the traceability, the gating, the
arithmetic), not about *outcomes*.

**Statistical.** No statistical claim is made. Every measure is a
deterministic property asserted over a fixed corpus, so the results are
exact counts rather than estimates, and no confidence interval is
reported. A corpus large enough to support a distributional claim would
be required first.

**Reproducibility.** The corpus, the seed and the golden vectors are
deterministic and regenerable (`python seed/make_fixtures.py --check`
fails on drift; `python scripts/lock.py --check` fails on an inconsistent
dependency set). The synthetic USD/INR rate is a fixture, not an
observation, and is labelled as such in `docs/REFERENCES.md`.

## 5. Reporting rules

1. A number appears in a report only if a command produced it, and the
   command is named.
2. A capability that is specified but not measured is reported under
   "proposed", never under "results".
3. A skipped, unexecuted or environment-blocked check is reported as
   such, with the reason, in the same table as the results.
4. The synthetic rate, the synthetic corpus and the synthetic prices are
   never presented as observations of a market.
5. A claim that the artefact is production-ready requires a sign-off
   against `docs/RELEASE_GATE.md` with every box checked and the
   evidence command for each.
