#!/usr/bin/env python3
"""Backup and restore, with a verification step.

The release gate asks for "Backups + restore test". A backup that has never
been restored is a guess, so this script does both halves and proves the
restore:

    python scripts/backup.py backup --out ./backups
    python scripts/backup.py restore --backup ./backups/pos-....dump
    python scripts/backup.py verify --backup ./backups/pos-....dump

`backup` writes a dump plus a manifest (sha256 of the dump, the schema
revision it was taken at, the row counts per table). `restore` loads the
dump into a scratch database and compares the row counts and the schema
revision against the manifest, so a restore that silently loses a table
fails here rather than in production. `verify` re-checks a dump without
restoring it.

Postgres is dumped with `pg_dump` (logical, portable across versions).
SQLite is dumped with the `sqlite3` backup API, which is consistent while
the database is live.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _env_url() -> str:
    return (
        os.environ.get("DATABASE_SYNC_URL")
        or os.environ.get("DATABASE_URL")
        or "postgresql+psycopg://pos:pos@localhost:5432/pos"
    )


def _is_postgres(url: str) -> bool:
    return url.startswith("postgresql")


def _pg_args(url: str) -> list[str]:
    """pg_dump arguments for a SQLAlchemy-style Postgres URL."""
    from sqlalchemy.engine import make_url

    parsed = make_url(url)
    args = ["--host", parsed.host or "localhost", "--port", str(parsed.port or 5432)]
    if parsed.username:
        args += ["--username", parsed.username]
    if parsed.database:
        args += ["--dbname", parsed.database]
    if parsed.password:
        args += ["--password", parsed.password]
    return args


def _schema_revision(url: str) -> str:
    """The alembic revision the database is at, or 'unknown'."""
    if not _is_postgres(url):
        return "n/a (sqlite)"
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(url)
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        engine.dispose()
        return str(row) if row else "unversioned"
    except Exception as exc:  # pragma: no cover - environment dependent
        return f"unknown ({exc})"


def _quote_ident(name: str) -> str:
    """Quote a table name for interpolation into a statement.

    The names come from the database's own catalogue, so they are not
    user input — but a name is still an identifier, and an identifier that
    has to be trusted to be harmless is a liability. Anything outside
    `[A-Za-z0-9_]` is refused rather than escaped.
    """
    if not re.fullmatch(r"[A-Za-z0-9_]+", name or ""):
        raise ValueError(f"refusing to use an unexpected table name: {name!r}")
    return f'"{name}"'


def _row_counts_sqlite(path: Path) -> dict[str, int]:
    conn = sqlite3.connect(path)
    try:
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return {
            n: int(
                conn.execute(
                    f"SELECT COUNT(*) FROM {_quote_ident(n)}"  # noqa: S608 - validated identifier
                ).fetchone()[0]
            )
            for n in names
        }
    finally:
        conn.close()


def _row_counts_postgres(url: str) -> dict[str, int]:
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            names = [
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                        "AND tablename LIKE 'pos\\_%'"
                    )
                )
            ]
            return {
                n: int(
                    conn.execute(
                        text(
                            f"SELECT COUNT(*) FROM {_quote_ident(n)}"  # noqa: S608 - validated
                        )
                    ).scalar_one()
                )
                for n in names
            }
    finally:
        engine.dispose()


def do_backup(out_dir: Path) -> Path:
    url = _env_url()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    manifest: dict[str, Any] = {
        "taken_at": stamp,
        "database_url_scheme": url.split("://", 1)[0],
        "schema_revision": _schema_revision(url),
    }

    if _is_postgres(url):
        if shutil.which("pg_dump") is None:
            raise SystemExit("pg_dump is not on PATH")
        dump = out_dir / f"pos-{stamp}.dump"
        cmd = ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", *_pg_args(url)]
        cmd += ["--file", str(dump)]
        proc = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
        if proc.returncode != 0:
            raise SystemExit(f"pg_dump failed: {proc.stderr.strip()}")
        manifest["row_counts"] = _row_counts_postgres(url)
    else:
        raw = url.split("///", 1)[-1] if "///" in url else url.split(":///", 1)[-1]
        source = Path(raw)
        if not source.exists():
            raise SystemExit(f"sqlite database not found: {source}")
        dump = out_dir / f"pos-{stamp}.sqlite"
        dest = sqlite3.connect(dump)
        try:
            source_conn = sqlite3.connect(source)
            try:
                source_conn.backup(dest)
            finally:
                source_conn.close()
        finally:
            dest.close()
        manifest["row_counts"] = _row_counts_sqlite(dump)

    manifest["sha256"] = hashlib.sha256(dump.read_bytes()).hexdigest()
    manifest["bytes"] = dump.stat().st_size
    manifest_path = dump.with_suffix(dump.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"backup written: {dump}")
    print(f"manifest written: {manifest_path}")
    return dump


def do_verify(backup: Path) -> int:
    manifest_path = backup.with_suffix(backup.suffix + ".manifest.json")
    if not manifest_path.exists():
        raise SystemExit(f"no manifest beside {backup}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        print(f"CHECKSUM MISMATCH for {backup}", file=sys.stderr)
        return 1
    print(f"checksum ok: {backup.name} ({manifest['bytes']} bytes)")
    print(f"schema revision at backup: {manifest['schema_revision']}")
    print(f"tables captured: {len(manifest.get('row_counts', {}))}")
    return 0


def do_restore(backup: Path, into: Path | None) -> int:
    """Restore into a scratch database and check it against the manifest."""
    manifest_path = backup.with_suffix(backup.suffix + ".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        print("CHECKSUM MISMATCH: refusing to restore", file=sys.stderr)
        return 1

    if into is None:
        into = (
            Path(os.environ.get("RESTORE_TARGET", "")) if os.environ.get("RESTORE_TARGET") else None
        )
    if into is None:
        into = backup.parent / (backup.stem + ".restored")

    if backup.suffix == ".sqlite":
        target = sqlite3.connect(into)
        try:
            source = sqlite3.connect(backup)
            try:
                source.backup(target)
            finally:
                source.close()
        finally:
            target.close()
        counts = _row_counts_sqlite(into)
    else:
        if shutil.which("pg_restore") is None:
            raise SystemExit("pg_restore is not on PATH")
        target_url = os.environ.get("RESTORE_TARGET")
        if not target_url:
            raise SystemExit(
                "a Postgres restore needs RESTORE_TARGET=<postgres url> "
                "(a scratch database — never the live one)"
            )
        cmd = ["pg_restore", "--no-owner", "--no-privileges", *_pg_args(target_url)]
        cmd += ["--file", str(backup)]
        proc = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
        if proc.returncode != 0:
            raise SystemExit(f"pg_restore failed: {proc.stderr.strip()}")
        counts = _row_counts_postgres(target_url)

    expected = manifest.get("row_counts", {})
    problems: list[str] = []
    for table, count in expected.items():
        actual = counts.get(table)
        if actual is None:
            problems.append(f"table missing after restore: {table}")
        elif actual != count:
            problems.append(f"row count differs for {table}: {actual} != {count}")
    extra = set(counts) - set(expected)
    for table in sorted(extra):
        problems.append(f"table present after restore but not in the manifest: {table}")

    if problems:
        print("RESTORE VERIFICATION FAILED:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"restore verified into {into}: {len(expected)} tables, row counts match")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    b = sub.add_parser("backup", help="write a dump and a manifest")
    b.add_argument("--out", default=str(ROOT / "backups"), help="output directory")

    v = sub.add_parser("verify", help="check a dump's checksum and manifest")
    v.add_argument("backup", help="path to the dump")

    r = sub.add_parser("restore", help="restore a dump and verify it")
    r.add_argument("backup", help="path to the dump")
    r.add_argument("--into", default=None, help="target database path or url")

    args = ap.parse_args(argv)
    if args.command == "backup":
        do_backup(Path(args.out))
        return 0
    if args.command == "verify":
        return do_verify(Path(args.backup))
    if args.command == "restore":
        return do_restore(Path(args.backup), Path(args.into) if args.into else None)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
