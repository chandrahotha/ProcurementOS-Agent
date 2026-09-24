# ADR-0001 — Standalone product, native deterministic engine, no sibling coupling

- Status: Accepted
- Date: 2026-09-24

## Context

The brain (`prerequisite-docs/00_IMPROVEMENT_SCOPE.md` §2, `README.md` Isolation
statement) binds ProcurementOS-Agent as fully standalone: own DB schema
(`pos_*`), buckets (`pos-tenant-{id}/`), queue namespace (`pos:*`), config,
secrets, deploy. Capabilities resembling other products are implemented
natively (`sourcing_compare`, `supplier_intel`, `cost_intel`, `risk_intel`).

## Decision

- Zero runtime/build imports, network calls, shared tables/buckets/queues,
  or data copies from any sibling product.
- Reference material is design-time only.
- Violation test stays green: block all hosts except own API/DB/storage/
  AI-provider endpoints; full lifecycle + AGENT-001…004 must pass.

## Consequences

- We (re)implement comparison/supplier/cost/risk math here, versioned by
  local `rule_version`. More upfront work, single audit lineage.
- No cross-product outage or auth surface.

## Brain refs

- `00_IMPROVEMENT_SCOPE.md` §2 · `02_ARCHITECTURE.md` §5 · `04_BUSINESS_RULES.md`
- `09_TEST_PLAN.md` acceptance: "No sibling/network dependency".

## Rollback

N/A (founding constraint; changing it requires a new ADR + brain amendment).
