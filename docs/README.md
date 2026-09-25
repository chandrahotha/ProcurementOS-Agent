# Producer docs — ProcurementOS-Agent

The product brain (`../prerequisite-docs/`, 12 files) is the **authoritative source
of truth** and is never edited during the build. These producer docs track the
build itself: progress, decisions, contracts, and operations.

| Doc | Purpose |
|---|---|
| `BUILD_LOG.md` | Append-only journal: what landed, test evidence, mistakes and their fixes |
| `adr/` | Architecture Decision Records — every deviation from the brain lives here, never a silent rewrite |
| `API_CONTRACT.md` | Live endpoint inventory, binding envelope + idempotency notes (mirrors `05_WORKFLOWS_AND_API.md`) |
| `RUNBOOK.md` | Quick start (sqlite E2E path), compose dev stack, CI order, backup/rollback/flag discipline |
| `RELEASE_GATE.md` | Release checklist with dated evidence per checked box (mirrors `10 §release gate`) |

Current ADRs:

| ADR | Decision |
|---|---|
| 0001 | Fully standalone product — no sibling coupling at runtime or build time |
| 0002 | Next.js 14 → 16.3.6 security upgrade (React 19, codemod path) |
| 0003 | OR-Tools dependency removed; greedy allocator is the certified optimizer |
| 0004 | JWT validation moved from python-jose to PyJWT (unfixable ecdsa advisory) |
| 0005 | Quote-line totals honor the price denomination (`price_uom`) — fixes a silent 24× inflation |

Standing rules: deterministic calculations are the source of truth; AI output is
untrusted; awards, money, contracts, and external messages require explicit human
approval; demo data is synthetic only (`SYNTHETIC-*`); the brain is never edited —
deviations get an ADR.
