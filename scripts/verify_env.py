#!/usr/bin/env python3
"""Check that an environment file is complete and correctly separated.

The release gate asks for "Env/credentials separated per environment", and
the honest version of that box is a command somebody can run and a failure
somebody can act on — not a paragraph in a README.

This checks three things:

1. **Completeness.** Every key the app reads is present. A missing key
   silently falls back to a default, which is how a staging deployment ends
   up writing to the dev bucket.
2. **Placeholders.** Outside development, no value may still be the
   `REPLACE_ME` placeholder from the template.
3. **No development credential leaked forward.** Outside development, no
   value may be one of the dev defaults (`pos/pos`, `posminio123`, the dev
   API base, the local OIDC issuer). This is the check that actually
   separates the environments: a staging file that still says
   `postgresql+asyncpg://pos:pos@localhost:5432/pos` fails here.

Usage:
    python scripts/verify_env.py --env .env.staging --profile staging
    python scripts/verify_env.py --env deploy/env/prod.env.example --profile production
    python scripts/verify_env.py --check-templates

Exit code 1 on any finding, with a file:line report.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Every key the app or the migration chain reads. A key that is missing
#: falls back to a default in app/core/config.py or alembic/env.py, which
#: is the silent failure this script exists to prevent.
REQUIRED_KEYS = (
    "APP_ENV",
    "API_VERSION",
    "DATABASE_URL",
    "DATABASE_SYNC_URL",
    "REDIS_URL",
    "S3_ENDPOINT",
    "S3_BUCKET",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_DEFAULT_REGION",
    "OIDC_ISSUER",
    "OIDC_AUDIENCE",
    "AI_PRIMARY_BASE_URL",
    "AI_PRIMARY_API_KEY",
    "AI_PRIMARY_MODEL",
    "AI_FALLBACK_BASE_URL",
    "AI_FALLBACK_API_KEY",
    "AI_FALLBACK_MODEL",
    "AI_TIMEOUT_S",
    "AI_CIRCUIT_BREAKER_S",
    "OUTBOX_WEBHOOK_URL",
    "NEXT_PUBLIC_API_BASE",
    "WEB_ORIGIN",
)

#: Values that belong to development only. If one of these appears in a
#: staging or production file, the environments are not separated.
DEV_ONLY_VALUES = (
    "pos:pos",
    "posminio123",
    "postgresql+asyncpg://pos:pos",
    "postgresql+psycopg://pos:pos",
    "redis://localhost:6379",
    "http://localhost:9000",
    "http://localhost:8000",
    "http://localhost:3000",
    "syn-Demo-2026!",
)

PLACEHOLDER = "REPLACE_ME"

#: In production these must not be blank, because a blank value silently
#: disables the control it configures.
NON_EMPTY_IN_PRODUCTION = (
    "DATABASE_URL",
    "DATABASE_SYNC_URL",
    "REDIS_URL",
    "S3_ENDPOINT",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "OIDC_ISSUER",
    "OIDC_AUDIENCE",
    "NEXT_PUBLIC_API_BASE",
    "WEB_ORIGIN",
)

TEMPLATES = (
    ("deploy/env/dev.env.example", "dev"),
    ("deploy/env/staging.env.example", "staging"),
    ("deploy/env/prod.env.example", "production"),
)


def parse_env(path: Path) -> dict[str, str]:
    """Read a dotenv file. `export KEY=VALUE` and quotes are tolerated."""
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def check(path: Path, profile: str, *, allow_placeholders: bool = False) -> list[str]:
    """Return a list of findings. Empty means the file passes.

    `allow_placeholders` is for the committed templates: a template is
    *supposed* to hold `REPLACE_ME`, and a filled environment file is not.
    The development-credential check applies either way — that is the check
    that actually separates the environments.
    """
    findings: list[str] = []
    if not path.exists():
        return [f"{path}: file does not exist"]
    values = parse_env(path)
    production = profile == "production"
    non_dev = profile != "dev"

    for key in REQUIRED_KEYS:
        if key not in values:
            findings.append(f"{path}: missing required key {key}")

    for key, value in sorted(values.items()):
        if non_dev and not allow_placeholders and PLACEHOLDER in value:
            findings.append(f"{path}: {key} still holds the {PLACEHOLDER} placeholder")
        if non_dev and value in DEV_ONLY_VALUES:
            findings.append(
                f"{path}: {key} carries the development value {value!r} — "
                "environments are not separated"
            )
        if non_dev and value:
            for dev_value in DEV_ONLY_VALUES:
                if dev_value in value and dev_value not in ("http://localhost:8000",):
                    findings.append(
                        f"{path}: {key} contains the development credential {dev_value!r}"
                    )
                    break

    if production:
        for key in NON_EMPTY_IN_PRODUCTION:
            if not values.get(key):
                findings.append(f"{path}: {key} must not be empty in production")
        if values.get("APP_ENV") != "production":
            findings.append(
                f"{path}: APP_ENV must be 'production' in production, got {values.get('APP_ENV')!r}"
            )

    if profile == "staging" and values.get("APP_ENV") == "development":
        findings.append(f"{path}: APP_ENV must not be 'development' in staging")

    return findings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--env", help="path to the env file to check")
    ap.add_argument(
        "--profile",
        choices=("dev", "staging", "production"),
        default="staging",
        help="which environment the file is meant to be",
    )
    ap.add_argument(
        "--check-templates",
        action="store_true",
        help="check the committed templates in deploy/env/ instead of a file",
    )
    args = ap.parse_args()

    findings: list[str] = []

    if args.check_templates:
        for rel, profile in TEMPLATES:
            path = ROOT / rel
            # A template is allowed to hold placeholders — that is what a
            # template is — but it may not carry a development credential,
            # and it may not be missing a key.
            findings.extend(check(path, profile, allow_placeholders=True))
    elif args.env:
        findings.extend(check(Path(args.env), args.profile))
    else:
        ap.error("one of --env or --check-templates is required")

    if findings:
        print(f"{len(findings)} finding(s):\n")
        for f in findings:
            print(f"  - {f}")
        raise SystemExit(1)

    print("env separation OK" if not args.check_templates else "env templates OK")


if __name__ == "__main__":
    main()
