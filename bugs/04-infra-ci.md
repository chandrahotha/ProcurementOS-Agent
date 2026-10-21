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
- [x] **I20** Stale tool pins exclude released versions (ruff<0.6, mypy<1.12, alembic<1.14); no Python lockfile. `pyproject.toml:42-44`. → Raise ranges + lock. **Closed 2026-10-20** (ADR 0008): the pins now admit the current releases (`ruff>=0.17,<0.18`, `mypy>=2.4,<3`, `alembic>=1.14,<1.15`), and the code is clean under them — which is how two real `mypy --strict` errors and one formatting difference came to light. `requirements.lock` pins the resolved set; `scripts/lock.py --check` verifies the lock still covers the declared ranges, so a range bump without a refreshed lock fails CI.
- [x] **I21** Redis CI service has no health gate. `ci.yml:56-58`. → `--health-cmd="redis-cli ping"`.
- [x] **I22** Migration env in api image incomplete — `alembic.ini` not copied; compose never runs migrations. `Dockerfile.api:6`. → Copy ini or drop.
- [x] **I23** web tsconfig: `noUncheckedIndexedAccess` + `noImplicitOverride` absent. `web/tsconfig.json:3-30`. → Enable.
- [x] **I24** Web typecheck runs before `next build` generates ambient types (next-env.d.ts gitignored). `ci.yml:108,110`. → Build first.
- [x] **I25** ruff S106 ignored for ALL tests - can mask real credentials in fixtures. `pyproject.toml:58-60`. → Scope to fixtures. **Closed 2026-10-20**: the blanket exemption is gone. The one synthetic test token that still trips the rule carries a line-scoped `noqa` with the reason attached, so a real credential in a test fixture is flagged again.

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

## Completion pass (2026-10-20) — C7–C12

- [x] **C7** The pipeline had no push or pull-request trigger, so a
  regression could sit on `main` for up to seven days and the README's
  "check before every push" was a habit rather than a gate.
  `.github/workflows/ci.yml` → a fast chain on every push and PR, with
  the heavy legs (Postgres, containers, Playwright) still weekly. ADR 0008.
- [x] **C8** The `integration` marker was registered but used by no test,
  so `pytest -m integration` collected nothing and the CI job that
  claimed to be the "Postgres leg" ran the sqlite suite twice.
  `tests/test_postgres.py` → five real Postgres-backed tests.
- [x] **C9** `alembic/versions/a7c41d92e503_pos_003_task_uniqueness.py`
  used `DELETE ... USING`, which is Postgres-only. The migration chain
  died on sqlite with "near \"a\": syntax error", so the release gate's
  "round-trip verified on scratch sqlite" was never true. → standard
  SQL that both engines run, and `tests/test_migrations.py` runs the
  round trip on every push.
- [x] **C10** `alembic.ini` committed a database password in its default
  URL, and `.env.example` documented the variable as
  `DATABASE_URL_SYNC` while `alembic/env.py` reads `DATABASE_SYNC_URL` —
  so a copied template set the wrong key and the migration silently used
  the committed default. → the default carries no password and the
  migration refuses to run without one; the template is correct.
- [x] **C11** `worker/queue.py` opened Redis with the default socket
  timeout, which is "wait forever", and the acknowledge endpoint opened
  a connection per task. A down Redis turned one acknowledgement into a
  ten-task hang. → a one-second connect timeout and a single queue probe
  before the loop.
- [x] **C12** The dependency lock check re-resolved "latest" on every
  run, so a new PyPI release would fail CI for no reason. The check is
  now *consistency* with the declared ranges, which is the mistake worth
  catching.
- [x] **C13** The release gate's "Env/credentials separated per
  environment" box was unticked and unanswerable. →
  `deploy/env/{dev,staging,prod}.env.example` and
  `scripts/verify_env.py`, which refuses a staging or production file
  that still carries a development credential.
- [x] **C14** The release gate's monitoring box claimed OpenTelemetry
  wiring that did not exist. → `app/core/observe.py` +
  `/api/v1/ops/metrics` + `scripts/task_age.py`. ADR 0010.
- [x] **C15** The dependency gate failed on its own terms: `vite@8.3.1`
  is inside the vulnerable range of three `launch-editor` advisories
  (GHSA-698v-4r3x-3vcv, GHSA-r825-w8mm-5pxw, GHSA-587h-7wmj-h5pm), and
  `scripts/npm_audit.py` treats an unaccepted advisory in the development
  tree as a blocker. The range for `vite` is `>=8.3.0, <=8.3.2`, so
  `8.3.5` is outside every listed one. -> vite is `^8.3.5` and the gate
  reports zero unaccepted findings; the one reviewed exception
  (`braces`, no patched release) is unchanged.
- [x] **C16** `lxml` was not in `requirements.lock`, but openpyxl
  serialises through lxml when it is importable and through the stdlib
  ElementTree when it is not, and the two write different bytes for the
  same workbook (namespace placement, `<tag/>` against `<tag />`). The
  committed `price-history.xlsx` was generated with lxml, so
  `seed/make_fixtures.py --check` reported drift on a clean CI install.
  -> `lxml>=6,<7` is a declared dev dependency and is pinned; the
  fixtures are now byte-identical with and without the local install.
- [x] **C17** The repository had no `.gitattributes`, so a Windows
  checkout with `core.autocrlf=true` rewrote the byte-exact corpus: a
  reportlab PDF contains no NUL byte, so git classified it as text and
  converted every LF into CRLF. The committed `quote-syn-sup-01.pdf` is
  2409 bytes and the checked-out file was 2497, so the drift check could
  never pass on a Windows clone. -> `.gitattributes` marks `*.pdf`,
  `*.xlsx`, `*.docm` and `*.png` as `binary` and checks everything else
  out as LF.
- [ ] **C18** The CI chain on `main` is red, and not because of the code:
  the last three push runs (`5ac0867`, `e99a287`, `1bf0aa4`) all fail in
  the *first* job, `lint`, with zero steps executed and no log written,
  which is the signature of a job that never started rather than of a
  lint error (the same command passes locally, and the three weekly
  scheduled runs before that were green through `unit`). Still open: the
  run records show the shape of the failure but the job logs were never
  produced, so the cause is not identified. Next: check the runner
  availability and the account's Actions allowance, then re-run with
  `workflow_dispatch` so a log exists.
