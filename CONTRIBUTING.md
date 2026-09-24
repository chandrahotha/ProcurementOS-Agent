# Contributing — ProcurementOS-Agent

1. Read `prerequisite-docs/README.md` first — the brain is authoritative.
   Never edit it; record deviations as ADRs in `docs/adr/`.
2. Local runbook order: `docs/RUNBOOK.md` (env → DB → migrate → seed →
   api/workers/web → tests → smoke).
3. Standards: Decimal/minor-unit money only (never float); every material
   number links to evidence spans or a reasoned waiver; AI text labeled +
   cited; material actions behind approval quorum; envelope + `request_id`
   on every response.
4. Tests: add/extend golden + negative tests with every behavior change
   (`tests/golden/`, `engine/tests/`). Visual similarity never substitutes
   for span-asserted correctness.
5. Commits: small, scoped, `type(scope): message`. Link the brain section
   and ADR (if any) in the PR body.
