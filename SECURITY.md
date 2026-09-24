# Security policy — ProcurementOS-Agent

- Report vulnerabilities privately via GitHub Security Advisories (no public issues for 0-days).
- Scope: own API/DB/storage/queue/AI-provider surface; sibling systems are out of scope (no coupling by design, see `docs/adr/0001-standalone-no-sibling-coupling.md`).
- Mandatory controls: OIDC + MFA where supported, deny-by-default RBAC +
  object-level auth, upload quarantine, prompt-injection isolation, approval
  gates on all material actions, append-only hash-chained audit.
- Secrets: server-side only, secret manager in staging/prod, gitleaks in CI,
  never in logs/exports/frontend bundle.
- Synthetic-data only in demo/seed (`SYNTHETIC-*`); no production data in repo.
