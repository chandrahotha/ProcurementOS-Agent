# Infra & CI Findings (I1–I17) — .github/, Docker, compose, config

Status: `[ ]` open · `[x]` fixed · `[~]` deferred with ADR.

## Bugs (CI fails / dead config)

- [x] **I1** `docker compose build` fails: `env_file: .env` on api/worker defaults `required: true`; `.env` is gitignored and never created in the workflow. `.github/workflows/ci.yml:104` + `docker-compose.yml:59,77`. → `required: false` or stub `.env`.
- [x] **I2** CI e2e fails: `aiosqlite` undeclared (used by every test file + `app/db.py:43` + playwright config); e2e job installs only `.` not `.[dev]`. `.github/workflows/ci.yml:119`, `web/playwright.config.ts:18,25`. → Add dep + install `.[dev]`.
- [x] **I3** dep-scan job vacuous: audits only the ephemeral env (pip-audit itself); project never installed. `.github/workflows/ci.yml:81-89`. → `pip install -e .` first.
- [x] **I4** README + RELEASE_GATE claim "npm audit clean" but no npm audit job exists. `.github/workflows/ci.yml` vs `README.md:11`, `docs/RELEASE_GATE.md:33-35`. → Add job or drop claim.
- [x] **I5** Web ESLint never runs in CI (`lint: eslint .` defined, never executed). `web/package.json:9`. → Add to build job.
- [x] **I6** `-m "not integration"` is a no-op — no marker registered, no test marked; unit job runs everything, integration job re-runs identical suite (golden twice). `pyproject.toml:47-49` + `ci.yml:39,71`. → Register marker + mark DB/Redis tests, or delete filter + duplicate.
- [x] **I7** Runtime `NEXT_PUBLIC_API_BASE` in compose is dead config (Next inlines at build time; Dockerfile.web builds without it). `docker-compose.yml:97-98` + `web/lib/api-client.ts:4` + `Dockerfile.web:6`. → Build arg or remove.

## Security

- [x] **I8** All three Dockerfiles run as root (no `USER`). → Non-root USER + chown.
- [x] **I9** Insecure compose defaults: `pos/pos`, `posminio123` committed; Redis no password; 5432/6379/9000/9001 published on all interfaces. `docker-compose.yml:7-9,20-23,36-40`. → Loopback binds + env-only secrets.
- [x] **I10** Production API image installs dev extras (pytest/mypy/ruff/pip-audit). `Dockerfile.api:4`. → Prod-only; multi-stage.
- [x] **I11** Actions pinned by mutable major tags (`checkout@v4`, `setup-python@v5`, `setup-node@v4`, `gitleaks-action@v2`). `ci.yml:14,25,35,60,77,86,96,103,117,120`. → Pin to SHAs.
- [x] **I12** No `permissions:` block — default GITHUB_TOKEN scope. `ci.yml`. → `permissions: contents: read`.
- [x] **I13** `python-multipart>=0.0.12` floor admits CVE-2024-24762 ReDoS range (fixed in 0.0.18; FastAPI 0.141's standard extra requires ≥0.0.18). `pyproject.toml:26`. → Raise floor.

## Config

- [x] **I14** No healthchecks for api/worker/web (compose only covers postgres/redis/minio; web short-syntax `depends_on: api` doesn't wait for health). `Dockerfile.*` + `docker-compose.yml:55-100`. → Add HEALTHCHECK + service healthchecks.
- [x] **I15** `npm ci || npm install` fallback in Dockerfile.web defeats lockfile reproducibility. `Dockerfile.web:4`. → Plain `npm ci`.
- [x] **I16** Web image ships all node_modules; no `output: "standalone"`. `Dockerfile.web:1-8` + `web/next.config.mjs`. → Standalone + multi-stage.
- [x] **I17** Floating `:latest` tags on minio + mock-ai. `docker-compose.yml:33,50`. → Pin versions.
- [x] **I18** `[tool.alembic]` in pyproject is dead config at pinned alembic 1.13 (pyproject support added in 1.16). `pyproject.toml:76-77`. → Remove.
- [x] **I19** Stale mypy override for removed `jose`. `pyproject.toml:72-74`. → Drop.
- [~] **I20** Stale tool pins exclude released versions (ruff<0.6, mypy<1.12, alembic<1.14); no Python lockfile. `pyproject.toml:42-44`. → Raise ranges + lock.
- [x] **I21** Redis CI service has no health gate. `ci.yml:56-58`. → `--health-cmd="redis-cli ping"`.
- [x] **I22** Migration env in api image incomplete — `alembic.ini` not copied; compose never runs migrations. `Dockerfile.api:6`. → Copy ini or drop.
- [x] **I23** web tsconfig: `noUncheckedIndexedAccess` + `noImplicitOverride` absent. `web/tsconfig.json:3-30`. → Enable.
- [x] **I24** Web typecheck runs before `next build` generates ambient types (next-env.d.ts gitignored). `ci.yml:108,110`. → Build first.
- [~] **I25** ruff S106 ignored for ALL tests — can mask real credentials in fixtures. `pyproject.toml:58-60`. → Scope to fixtures.

## Improvements

- [x] **I26** No caching anywhere in CI (pip/npm/playwright). → Enable caches.
- [x] **I27** No concurrency groups — overlapping full-pipeline runs. → `concurrency: cancel-in-progress`.
- [x] **I28** No timeout-minutes on any job (default 360). → Per-job timeouts.
- [x] **I29** No coverage reporting (pytest-cov/vitest). → Add + upload.
- [x] **I30** Dockerfile.web never built in CI (build job builds only api+worker). → Add web.
- [x] **I31** e2e re-does the build instead of consuming artifacts. `ci.yml:107-110` vs `122-123`. → Artifacts.
- [x] **I32** security-lint skips alembic (and tests). `ci.yml:79`. → Include alembic.
- [x] **I33** No resource limits or restart policies in compose. → Add.
- [x] **I34** Dependabot claimed (BUILD_LOG) but no `.github/dependabot.yml`. → Add config.
- [x] **I35** `npx --prefix web playwright install` fragile invocation from repo root. `ci.yml:124` + `docs/RUNBOOK.md:20`. → Run inside web/.
- [x] **I36** `.env.example` header says "NO VALUES, keys only" but carries values. → Blank values or reword.
- [x] **I37** ~13 documented env keys consumed by nothing (REQUEST_ID_HEADER, S3_*, OIDC_CLIENT_*, AI_PRIMARY_*, MFA_ENFORCED, SEED_ADMIN_*). `.env.example` vs `app/core/config.py:6-21`. → Add Settings fields or remove keys.
- [x] **I38** README says e2e runs "against the seeded synthetic stack" — actually sqlite-backed API with no postgres/redis/minio. `README.md:9`. → Reword.
