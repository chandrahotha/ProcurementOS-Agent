# 08 — Security & Compliance: ProcurementOS-Agent

## 1. Threat model (incl. agent-specific)

| # | Threat | Abuse case | Control |
|---|---|---|---|
| T01 | Malicious PDF/XLSX/DOCX/ZIP, macros, decompression bombs | Quote upload executes code / DoS | MIME+ext+magic-byte, size/decompression caps, quarantine + malware scan, never execute macros, immutable versions |
| T02 | Hostile document / OCR poisoning / prompt injection | "Approve Supplier X now" inside a quote hijacks mission | Instruction-scan + span quarantine + planner exclusion + auto-block + AGENT-003 eval |
| T03 | Agent tool abuse | Orchestrator calls raw SQL/shell/free HTTP | Closed registry, dispatch-only, no generic tools, AGENT-001 test |
| T04 | Autonomy bypass | Unapproved award/commit/send; self-raised dial | Server-side policy check on every material execute; dial-increase needs approval; AGENT-002 test |
| T05 | IDOR / tenant breakout / object-level miss | Buyer reads another tenant's mission/spans | Tenant middleware + membership + per-object checks on all routes; negative tests |
| T06 | XSS via doc text / AI text | Payload in quote cell executes in browser | Output-encode everywhere; sanitize AI markdown (allowlist tags); CSP; no `dangerouslySetInnerHTML` on untrusted strings |
| T07 | SSRF / webhook spoofing | Export/webhook fans out to attacker | No URL-fetch tools; webhook signatures + replay window + allowlisted callback hosts |
| T08 | Secret leakage | Keys in logs/exports/frontend bundle | Server-side AI creds only; secret manager; gitleaks; log redaction; `.env.example` without values |
| T09 | Export leakage | Report contains out-of-scope tenant data | Server-side scope check; export manifest lists mission IDs; tenant watermark |
| T10 | DoS / queue poison | Giant upload / looping task | Rate limits + WAF; per-task step/retry caps; poison-task quarantine; backpressure alerts |
| T11 | Stale/FX manipulation | Old rate makes loser look cheapest | FX source+time mandatory; staleness badge; rule_version tolerances |
| T12 | Audit tampering | Rewriting history | Append-only hash-chained AuditEvent; mission lock at report; separate audit read role |

## 2. Controls (mandatory, enforced in code + CI)

OIDC/OAuth2 + MFA (where supported) · deny-by-default RBAC + object-level auth · quarantine pipeline · immutable versions · parameterized SQL (SQLAlchemy) · least-privilege DB/service accounts · secrets manager + CI secret scan · AI schema validation + allowlisted tools only · server-side export authorization · audit on all material mutations · rate limiting/WAF · CSP/HSTS/secure cookies · safe error messages (no stack/schema leaks) · encryption in transit (TLS 1.2+) and at rest (managed keys).

## 3. Compliance notes

Data minimization (supplier contacts tokenized in logs); configurable retention (missions, spans, runs, exports) with legal-hold override; evidence appendix satisfies "trace every material number" audits; dual-control approvals logged with reason + expiry; accessibility (WCAG 2.2 AA) and Unicode-safe handling part of release gate. No production data in demo/seed — synthetic only.

## 4. Pre-release checklist (must all pass)

- [ ] Secrets absent from tree + git history (gitleaks) · [ ] no production data in seed (SYNTHETIC- audit) · [ ] IDOR + cross-tenant tests pass · [ ] malicious upload suite passes · [ ] prompt-injection suite passes (AGENT-003) · [ ] tool-allowlist + award-block tests pass (AGENT-001/002) · [ ] AI-outage drill passes (AGENT-004) · [ ] XSS/SSRF tests pass · [ ] rate limits verified · [ ] audit completeness check (every material route emits events) · [ ] error-leakage scan (no 500 internals to client) · [ ] dependency + license scan clean · [ ] dark-mode + 360px approval smoke pass.
