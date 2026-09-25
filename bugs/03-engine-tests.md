# Engine & Test Findings (E1–E14, T1–T20) — engine/, tests/, seed/, worker/

Status: `[ ]` open · `[x]` fixed · `[~]` deferred with ADR. Engine findings verified by execution.

## Engine bugs

- [x] **E1** UOM normalization converts qty to base units but never the price denomination — per-box pricing silently inflated 24× (verified: seed fixture "2 boxes of 24 pcs, EUR 18.00/box" → 86400 minor instead of 3600). `engine/sourcing_compare.py:45-46`, `engine/money.py:55-61`. → Model price UOM on QuoteLine + golden vector.
- [x] **E2** Docstring promises duplicate-line flagging + validity-conflict enforcement; neither implemented, `notes` never populated (duplicates ranked unflagged; `valid_until='2020-01-01'` still compliant — verified). `engine/sourcing_compare.py:4-6,41-62`. → Implement + pin with tests.
- [x] **E3** Band lookup raises `StopIteration` when composite ≥ 101 (all dims = 101 → composite 101 — verified). `engine/risk_intel.py:7,23`. → `next(..., "CRITICAL")` or clamp.
- [x] **E4** `max_suppliers=0` silently ignored (both offers allocated — verified); negative unit_cost fully allocated with `constraints_ok=True`; float capacities truncated by `int()`. `engine/scenario_opt.py:30-43`. → Validate/reject.
- [x] **E5** `_stale` subtracts naive from aware datetimes — TypeError swallowed, fresh rate always flagged stale (verified). `engine/cost_intel.py:15-21`. → Normalize to UTC.
- [x] **E6** `three_way_diff` never consults `base` — one-sided change falsely flagged `needs_retry` (verified). `app/evidence/conflicts.py:8-21`. → Conflict only when both differ from base.
- [x] **E7** Concession rung uses full room (walk_away − target) instead of opening→target span — third concession lands below target and the ladder's own validator rejects it (ladder(9000,10000) → concessions [9500, 9167, 8834], 8834 rejected — verified). `app/negotiation/ladders.py:19-21`. → `rung = (opening − target) // (steps − 1)`.
- [x] **E8** `draft_within_ladder` refuses drafts below target, contradicting its own comment "Drafts may aim below target"; `hi` bound makes line-36 check dead. `app/negotiation/ladders.py:31-37`. → Allow ≤ walk-away or fix comment.
- [x] **E9** Replay integrity compares summed build-up against converted TCO — non-target-currency TCO falsely "diverged". `app/api/runs_export.py:78-80` vs `engine/cost_intel.py:45-48`. → Compare in source currency or store converted build-up.
- [x] **E10** `convert_minor` rejects valid reverse quote pairs (EUR/USD held, USD→EUR needed) instead of inverting; `FxRate.rate` not runtime-validated. `engine/money.py:21-41`. → Invert + validate.
- [x] **E11** `rank_lines` ties broken by undocumented input order; all non-compliant share rank 0. `engine/sourcing_compare.py:65-70`. → Tie-break by line_id + document rank-0 semantics.
- [x] **E12** Lines rounded twice (after qty×price, again after ×(1+tax_rate)) — inconsistent with money.py's stated convention. `engine/sourcing_compare.py:46-48`. → Document or compute tax on exact product.
- [~] **E13** Tool registry: most handlers are `_echo` — normalize_quote_line, compute_sourcing_rank, compute_supplier_kpis, draft_message never call the engine. `app/tools/registry.py:124-139`. → Wire to real math.
- [x] **E14** `to_csv` derives fieldnames from `rows[0].keys()` — heterogeneous rows raise ValueError mid-write; no formula-injection sanitization for `=`/`+`/`-`/`@`. `app/reports/exporter.py:39-46`. → Union keys + sanitize.

## Seed bugs

- [x] **T11** Prod guard inspects only the FIRST arbitrary row per model (`limit(1)`, no order_by) — non-synthetic rows deeper pass; missing column silently passes. `seed/seed_pos.py:104-107`. → `WHERE NOT synthetic LIMIT 1`.
- [x] **T12** Docstring claims "upsert by code/email/sku" but RuleVersion skipped if any rule row exists; transactions not topped up to 24 on re-run. `seed/seed_pos.py:135-154,190-218`. → Upsert properly.
- [x] **T13** All 13 documents seeded `status="quarantined"`, `sha256="0"*64`, `size=1024`; `HOSTILE-003.docm` declared `mime="application/pdf"`. `seed/seed_pos.py:70,219-238`. → Realistic statuses/hashes + true mime.
- [x] **T14** Workspace membership written only on creation; Supplier/Item lack unique (tenant, code/sku) constraints — concurrent seeds duplicate. `seed/seed_pos.py:124-134`. → Refresh members + add indexes.
- [~] **T15** Seed metadata references `quote-acme.pdf`, `quote-baltic.pdf` etc. but fixtures/ has only QUOTE-ACME-001.txt/pdf + HOSTILE-001/002.txt — 11 of 13 unmatched. `seed/seed_pos.py:53-71`. → Generate matching fixtures or align.

## Test gaps / quality

- [x] **T1** Approval expiry (EXPIRY_DAYS=7) has no test anywhere; golden comment "Expired/mismatched payload must NOT pass" contradicts its assertion. `tests/golden/test_agent_golden.py:112-118`. → Fix comment + expiry test.
- [x] **T2** AGENT-003 never invokes any ingest/planning pipeline — "zero plan/task/approval writes" trivially true; docstring still says AGENT-003/004 "remain strict-xfail placeholders" though both are real. `tests/golden/test_agent_golden.py:170-203`. → Drive real endpoints; fix docstring.
- [x] **T3** AGENT-004 only tests both-providers-down; fallback-success path + "math + approvals + export succeed" never exercised. `tests/golden/test_agent_golden.py:206-217`. → Add fallback case.
- [x] **T4** `test_backoff_grows_and_caps` only asserts `0 <= backoff(i) <= 300` — a constant backoff passes; monotonic growth never pinned. `tests/test_workers.py:34-39`. → Assert strictly increasing.
- [x] **T5** Ladder test never asserts concessions (overshoot + below-target refusal unpinned); `steps < 2` untested. `tests/test_outage.py:31-36`. → Assert + add test.
- [x] **T6** Missing edge vectors: zero qty, single-supplier allocation, ranking ties, negative discounts, stale FX in sourcing_compare, exclusive-tax half-case, composite-101 crash; no property-based tests. `engine/tests/test_vectors.py`. → Add vectors + hypothesis.
- [x] **T7** Cross-tenant "denied" tests only assert a hand-written filtered query returns nothing — verifies the test author's WHERE clause, not the app's authz. `tests/test_phase9.py:53-65`, `tests/test_foundation.py:19-30`. → Call must_mission/must_member or HTTP route.
- [x] **T8** 500-handler envelope shape entirely unpinned (comment promises a crashing route; none exists). `tests/test_health.py:24-27`. → Add test-only crashing route.
- [~] **T9** test_api: `raise_server_exceptions=False` + tolerance assertions `in (403,404)` can't distinguish intended from accidental; giant lifecycle test. `tests/test_api.py:58,102,187`. → Split + pin statuses.
- [x] **T10** No coverage measurement anywhere (no pytest-cov, no [tool.coverage], no CI step). → Add with fail_under=80.
- [x] **T16** `decide()` no terminal-state guard: rejected row can flip to approved; same principal decides same lane twice. `app/approvals/service.py:168-207`. → Refuse non-pending + duplicate decisions.
- [x] **T17** `certified_award_value` takes latest CostResult regardless of `stale_flag` — stale-FX TCO certifies AWARD value. `app/approvals/service.py:63-79`. → Filter stale + tie-break by id.
- [x] **T18** `dry_run` trusts client-supplied `payload_hash_match` flag (default True); HTTP layer injects it unconditionally — meaningless. `app/actions/service.py:26-39`, `app/api/approvals_actions.py:180`. → Derive verdict from server-computed quorum only.
- [x] **T19** Failed run keeps same `inputs_hash` — identical retried request replays the failed run forever (`replayed: True, status: failed`). `app/api/analysis.py:70-79,190-193`. → Exclude failed runs from replay lookup.
- [x] **T20** `coverage_waived` bypasses BOTH coverage ≥80% AND `blocking_conflicts == 0` — waiver admits blocking conflicts; `test_pos_miss_01` pins this combined bypass. `app/missions/machine.py:90`, `tests/test_phase9.py:30-34`. → Waive coverage only; conflict gate independent.
- [x] **T21** `rows_for` filters only by mission_id, no tenant predicate — footgun for future call sites. `app/api/common.py:42-45`. → Add tenant_id.
- [x] **T22** Engine tests placeholder docstring claims vectors "live here" while real vectors are in test_vectors.py. `engine/tests/test_vectors_placeholder.py:1-5`. → Fix.
- [x] **T23** `app/engine/` empty — glue scattered inline with triplicated role sets. → Consolidate or delete (same as B55).
