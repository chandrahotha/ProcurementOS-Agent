# Producer docs — ProcurementOS-Agent

The product is built from a product brief that is the **authoritative source of
truth** and is never edited during the build. That brief is the maintainer's
private working document: it is deliberately kept out of this repository, so
the references to it below are citations, not links. These producer docs are
the public record — they track the build itself: progress, decisions,
contracts, and operations.

| Doc | Purpose |
|---|---|
| `BUILD_LOG.md` | Append-only journal: what landed, test evidence, mistakes and their fixes |
| `adr/` | Architecture Decision Records — every deviation from the brain lives here, never a silent rewrite |
| `API_CONTRACT.md` | Live endpoint inventory, binding envelope + idempotency notes (mirrors `05_WORKFLOWS_AND_API.md`). Generated from the OpenAPI schema by `scripts/api_inventory.py` and checked against it by `tests/test_api_contract.py` |
| `RUNBOOK.md` | Quick start (sqlite E2E path), compose dev stack, CI order, backup/rollback/flag discipline |
| `RELEASE_GATE.md` | Release checklist with dated evidence per checked box (mirrors `10 §release gate`) |
| `EVALUATION.md` | Evaluation design: oracles, measures, procedure, threats to validity, and the evidence class of every result |
| `REFERENCES.md` | Works cited by the artefact, and the one fixture value that must not be cited as an observation |
| `WALKTHROUGH.md` | A guided pass over the product: what each screen shows and why |

Current ADRs:

| ADR | Decision |
|---|---|
| 0001 | Fully standalone product — no sibling coupling at runtime or build time |
| 0002 | Next.js 14 → 16.3.6 security upgrade (React 19, codemod path) |
| 0003 | OR-Tools dependency removed; greedy allocator is the certified optimizer |
| 0004 | JWT validation moved from python-jose to PyJWT (unfixable ecdsa advisory) |
| 0005 | Quote-line totals honor the price denomination (`price_uom`) — fixes a silent 24× inflation |
| 0006 | Timestamps are real columns, not ISO strings in a `VARCHAR` |
| 0007 | Correction conflicts are detected and refused, never silently overwritten |
| 0008 | CI gates every push; the heavy legs (Postgres, containers, e2e) stay weekly |
| 0009 | Outbound calls go through one egress policy (scheme, host allowlist, no redirect following) |
| 0010 | Request/queue observability, and explicit handling of the two process-wide counters |
| 0011 | Research context: INR base currency, opaque synthetic identifiers, and the E1/E2/E3 evidence classes |

Standing rules: deterministic calculations are the source of truth; AI output is
untrusted; awards, money, contracts, and external messages require explicit human
approval; demo data is synthetic only (`SYNTHETIC-*`); the brain is never edited —
deviations get an ADR. A claim about the artefact's own state is E1 (executed),
E2 (computable, not executed here) or E3 (proposed) — see ADR 0011.
