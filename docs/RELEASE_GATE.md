# Release gate — ProcurementOS-Agent

Mirrors the binding checklist in `prerequisite-docs/10_SEED_DEMO_DEPLOY_ROADMAP.md`.
Checked items carry the date and the evidence command. Nothing ships with an
unchecked box in its section.

## Product

- [x] W1→W8 completes on synthetic seed (2026-09-25) — `tests/test_api.py`
      (HTTP walk) and `web/e2e/full-flow.spec.ts` (browser walk), both in CI.
- [x] P01–P16 + G01–G20 reachable (2026-09-25) — `next build` route table;
      P02–P16, G13, G16 wired to live data; Dashboard/Login/Analytics/Search/
      Workspaces/Suppliers/Notifications/AI-Runs wired (2026-09-25); the
      Slice 15 design system (Tailwind 4 + app shell) ships the styled UI.
- [ ] Seeded demo (8-minute + 2–4-minute cuts) rehearsed, both closing on the
      G13 audit inspection — pending staging (issue #8).
- [x] Exports tenant-scoped with evidence appendix (2026-09-25) —
      POS-EXP-01 deny case in `tests/test_api.py`; every scope id
      tenant-checked; XLSX/PDF/CSV builders in `app/api/runs_export.py`.
- [x] Audit events present for all material mutations (2026-09-25) —
      G13 wired with full hashes + `/audit/verify` chain re-walk;
      `tests/test_api.py` asserts the full walk lands in the trail.

## Engineering

- [x] lint · typecheck · unit · integration · E2E · build green
      (2026-09-25) — ruff + format clean; `mypy --strict` clean (68 files);
      `pytest` 59 passed incl. AGENT-001…004; `tsc` clean; `next build` green;
      `vitest` green; Playwright 3/3.

## Security

- [x] Secrets absent (tree + history) (2026-09-25) — gitleaks in CI;
      `.env.example` values blanked, unused keys marked.
- [x] Dependency scan clean (2026-09-25) — `pip-audit` and `npm audit`
      (prod + dev) report zero findings for project deps; jose→PyJWT,
      ortools removed, Next 16.3.6 (ADRs 0002–0004); python-multipart floor
      raised above the ReDoS range; dep-scan now audits the installed project.
- [x] Upload-abuse suite (2026-09-25) — `tests/test_ingest.py`
      (POS-SEC-02: extension/MIME/magic-byte/oversize/macro rejects);
      full-archive macro scan for OOXML + 25 MB cap during read + filename
      sanitization + span-document validation.
- [x] IDOR + tenant breakout (2026-09-25) — cross-tenant deny in
      `tests/test_api.py` (authz layer itself pinned, T7); object-level
      membership on every route; safe-404 for non-members.
- [x] Prompt injection (AGENT-003) (2026-09-25) — hostile fixtures;
      `tests/test_ingest.py` asserts zero mission mutation; corrections
      re-scanned so injected text cannot evade quarantine (B10).
- [x] Dual control (2026-09-25) — managers out of finance/compliance lanes
      (structural, not advisory); unknown action class never satisfies
      quorum; decisions terminal; `tests/test_foundation.py` pins the map.
- [x] XSS posture — output-encoded React rendering; no
      `dangerouslySetInnerHTML` on untrusted strings (the theme-init script
      is a static trusted constant).
- [x] Rate limits implemented (2026-09-25) — per-IP fixed-window on write
      methods, 429 with the error envelope (`app/core/ratelimit.py`);
      verified under load pending staging (issue #8).
- [ ] SSRF suite against live webhook hosts — pending staging (issue #8).

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
