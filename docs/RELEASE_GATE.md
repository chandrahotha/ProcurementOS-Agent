# Release gate — ProcurementOS-Agent (tracker, mirrors `10 §release gate`)

Check every box before any prod deploy.

## Product

- [ ] W1→W8 completes on synthetic seed
- [ ] P01–P16 + G01–G20 reachable
- [ ] 8-min + 2–4-min demos rehearsed (both close on G13 audit inspection)
- [ ] Exports tenant-scoped with evidence appendix
- [ ] Audit events on every material mutation

## Engineering

- [ ] lint · typecheck · unit · integration · E2E · build green

## Security

- [ ] secrets absent (tree + history) · dep scan clean · upload-abuse ·
      IDOR · tenant breakout · prompt injection (AGENT-003) · XSS · SSRF ·
      rate limits verified

## AI

- [ ] schema validation (incl. POS-AI-SCH-01) · evidence linkage on all AI text ·
      refusal behavior · outage drill (AGENT-004)

## Deployment

- [ ] env/credentials separated · migrations (expand→migrate→contract, staged) ·
      backups + restore test · rollback rehearsed (RTO ≤ 30 min, RPO ≤ 5 min) ·
      monitoring + queue/task-age alerts live
