# Producer docs — ProcurementOS-Agent

The product brain (`../prerequisite-docs/`, 12 files) is the **authoritative source
of truth** and is never edited during the build. These producer docs track the
build itself: progress, decisions, contracts, and operations.

| Doc | Purpose |
|---|---|
| `BUILD_LOG.md` | Running journal: what landed per phase, test evidence, deviations |
| `adr/` | Architecture Decision Records — **every deviation from the brain lands here** |
| `API_CONTRACT.md` | Live endpoint inventory (grows from Phase 2; mirrors `05_WORKFLOWS_AND_API.md`) |
| `RUNBOOK.md` | Local runbook + CI order + backup/flag discipline (mirrors `10 §3` add-on) |
| `RELEASE_GATE.md` | Release checklist tracker (mirrors `10 §release gate`) |

Rules: deterministic calculations are source of truth; AI output is untrusted;
awards/money/contracts/external messages require explicit human approval;
demo data is synthetic only (`SYNTHETIC-*`).
