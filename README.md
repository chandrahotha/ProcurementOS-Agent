# ProcurementOS-Agent — Autonomous Procurement Agent

Standalone, production-grade procurement mission agent: intake → plan → evidence → analysis → scenarios → negotiation → approval → action → report — with its own deterministic engine and human approval gates for all material actions.

## Repository layout

```text
/                          ← application code lives here (upcoming build)
/prerequisite-docs/         ← product brain: vision, PRD, architecture, rules, UX, tests (source of truth)
```

- Start with [`prerequisite-docs/README.md`](prerequisite-docs/README.md) for the product index.
- The product brain is the authoritative reference for every build step. Do not modify it during implementation; record deviations as ADRs.
- This product is fully independent: own database, schema, config, and backlog. Zero dependency on any sibling product.
