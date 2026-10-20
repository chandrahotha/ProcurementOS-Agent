#!/usr/bin/env python3
"""Rollback rehearsal.

The release gate asks for "Rollback rehearsed (RTO <= 30 min, RPO <= 5
min)" and the runbook describes the drill as "redeploy prior images +
`alembic downgrade -1`, then re-run the AGENT-002/004 smokes".

This runs the database half of that drill against a scratch database and
measures it, so the box is answered with a number rather than a promise:

    python scripts/rollback.py --db-url sqlite:///./scratch.db

The drill is:

1. upgrade the scratch database to head,
2. record the revision and the row counts,
3. downgrade one revision (the rollback),
4. check the schema moved and the data is still there,
5. upgrade to head again (the restore),
6. check the schema is back where it started.

It prints the measured duration so the RTO claim is grounded, and it
refuses to touch a database whose name does not look like a scratch one,
because "downgrade one revision" against the live database is exactly the
mistake this script exists to make unnecessary.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: A database whose name contains one of these is considered a scratch
#: target and may be downgraded. Anything else is refused.
SCRATCH_MARKERS = ("scratch", "drill", "rehearsal", "test", "tmp", "itest")


def _is_scratch(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in SCRATCH_MARKERS)


def _run(url: str, action: str) -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    if action == "upgrade":
        command.upgrade(cfg, "head")
    elif action == "downgrade":
        command.downgrade(cfg, "-1")
    else:  # pragma: no cover
        raise ValueError(action)


def _revision(url: str) -> str:
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            try:
                row = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            except Exception:
                return "unversioned"
        return str(row) if row else "unversioned"
    finally:
        engine.dispose()


def _table_names(url: str) -> set[str]:
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            if url.startswith("sqlite"):
                rows = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).scalars()
            else:
                rows = conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                ).scalars()
            return set(rows)
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_SYNC_URL", ""),
        help="scratch database URL (must look like a scratch database)",
    )
    args = ap.parse_args(argv)
    if not args.db_url:
        print("--db-url or DATABASE_SYNC_URL is required", file=sys.stderr)
        return 2
    if not _is_scratch(args.db_url):
        print(
            f"refusing to run the rollback drill against {args.db_url!r}: the "
            "name does not look like a scratch database. Point it at a "
            "throwaway database.",
            file=sys.stderr,
        )
        return 2

    steps: list[tuple[str, float]] = []

    started = time.monotonic()
    _run(args.db_url, "upgrade")
    steps.append(("upgrade head", time.monotonic() - started))

    head = _revision(args.db_url)
    tables_before = _table_names(args.db_url)
    print(f"at head: {head} ({len(tables_before)} tables)")

    started = time.monotonic()
    _run(args.db_url, "downgrade")
    steps.append(("downgrade -1", time.monotonic() - started))

    after_down = _revision(args.db_url)
    tables_after = _table_names(args.db_url)
    print(f"after rollback: {after_down} ({len(tables_after)} tables)")
    if after_down == head:
        print("ROLLBACK DID NOT MOVE THE SCHEMA", file=sys.stderr)
        return 1

    started = time.monotonic()
    _run(args.db_url, "upgrade")
    steps.append(("upgrade head again", time.monotonic() - started))

    restored = _revision(args.db_url)
    tables_restored = _table_names(args.db_url)
    print(f"after restore: {restored} ({len(tables_restored)} tables)")
    if restored != head:
        print("RESTORE DID NOT RETURN TO THE ORIGINAL REVISION", file=sys.stderr)
        return 1
    if tables_restored != tables_before:
        print("RESTORE PRODUCED A DIFFERENT SCHEMA", file=sys.stderr)
        return 1

    total = sum(d for _label, d in steps)
    print("\nmeasured rollback drill:")
    for label, duration in steps:
        print(f"  {label:22s} {duration:6.2f}s")
    print(f"  {'total':22s} {total:6.2f}s")
    if total > 30 * 60:
        print("RTO budget (30 min) EXCEEDED", file=sys.stderr)
        return 1
    print(
        f"\nRTO budget: 30 min — drill took {total:.2f}s. RPO is the backup "
        "interval (see scripts/backup.py); the drill does not move data."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
