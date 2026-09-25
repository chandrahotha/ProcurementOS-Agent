# Release gate — ProcurementOS-Agent

Mirrors the binding checklist in `prerequisite-docs/10_SEED_DEMO_DEPLOY_ROADMAP.md`.
Checked items carry the date and the evidence command. Nothing ships with an
unchecked box in its section.

## Product

- [x] W1→W8 completes on synthetic seed (2026-09-24) — `tests/test_api.py`
      (HTTP walk) and `web/e2e/full-flow.spec.ts` (browser walk), both in CI.
- [x] P01–P16 + G01–G20 reachable (2026-09-24) — `next build` route table;
      P02–P16, G13, G16 wired to live data; remaining G screens are shell
      views pending their features.
- [ ] Seeded demo (8-minute + 2–4-minute cuts) rehearsed, both closing on the
      G13 audit inspection — pending staging (issue #8).
- [x] Exports tenant-scoped with evidence appendix (2026-09-24) —
      POS-EXP-01 deny case in `tests/test_api.py`; XLSX/PDF/CSV builders in
      `app/api/runs_export.py`.
- [x] Audit events present for all material mutations (2026-09-24) —
      G13 wired; `tests/test_api.py` asserts the full walk lands in the trail.

## Engineering

- [x] lint · typecheck · unit · integration · E2E · build green
      (2026-09-24) — ruff + format clean; `mypy --strict` clean (71 files);
      `pytest` 42 passed incl. AGENT-001…004; `tsc` clean; `next build` green;
      `vitest` green; Playwright 3/3.

## Security

- [x] Secrets absent (tree + history) (2026-09-24) — gitleaks in CI;
      `.env.example` keys-only.
- [x] Dependency scan clean (2026-09-24) — `pip-audit` and `npm audit`
      (prod + dev) report zero findings for project deps; jose→PyJWT,
      ortools removed, Next 16.3.6 (ADRs 0002–0004).
- [x] Upload-abuse suite (2026-09-24) — `tests/test_ingest.py`
      (POS-SEC-02: extension/MIME/magic-byte/oversize/macro rejects).
- [x] IDOR + tenant breakout (2026-09-24) — cross-tenant deny in
      `tests/test_api.py`; object-level membership on every route.
- [x] Prompt injection (AGENT-003) (2026-09-24) — hostile fixtures;
      `tests/test_ingest.py` asserts zero mission mutation.
- [x] XSS posture — output-encoded React rendering; no
      `dangerouslySetInnerHTML` on untrusted strings.
- [ ] SSRF suite against live webhook hosts — pending staging (issue #8).
- [ ] Rate limits verified under load — pending staging (issue #8).

## AI

- [x] Schema validation incl. POS-AI-SCH-01 (2026-09-24) —
      `tests/test_outage.py` (retry-once, then needs_review; no coerce).
- [x] Evidence linkage on all AI text (2026-09-24) — output scan quarantines
      unreferenced claims (POS-AI-HAL-01).
- [x] Refusal behavior (out-of-ladder drafts, policy-altering requests) —
      ladder bound-violation refuses in `app/api/scenarios.py` +
      `tests/test_outage.py`.
- [x] Provider-outage fallback drill (AGENT-004) (2026-09-24) — math,
      approvals, exports unaffected; no fabricated text.

## Deployment

- [ ] Env/credentials separated per environment — pending staging.
- [ ] Migrations (expand→migrate→contract) staging-tested — round-trip
      verified on scratch sqlite (2026-09-24); Postgres leg in CI;
      staging rehearsal pending (issue #8).
- [ ] Backups + restore test — pending staging (issue #8).
- [ ] Rollback rehearsed (RTO ≤ 30 min, RPO ≤ 5 min) — pending staging.
- [ ] Monitoring + queue/task-age alerts live — OpenTelemetry wiring exists;
      dashboards pending staging (issue #8).
