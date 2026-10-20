"""The migration chain, proven on every push.

`docs/RELEASE_GATE.md` claimed "round-trip verified on scratch sqlite". It
was not: `alembic/versions/a7c41d92e503_pos_003_task_uniqueness.py` used
`DELETE ... USING`, which is Postgres-only, so the chain died on sqlite with
"near \"a\": syntax error" before it reached the end. The claim was true only
for the Postgres leg, which ran weekly.

This module runs the whole chain against a throwaway sqlite database — the
engine the dev and test stack use — and asserts:

* every `pos_*` table the application queries exists after `upgrade head`,
* the columns that must be timestamps (B44) really are timestamps and not
  ISO strings in a VARCHAR,
* the chain is reversible: `upgrade head` -> `downgrade base` -> `upgrade
  head` leaves the same schema.

It is fast (no services, no containers), so it belongs in the push/PR chain
rather than only in the weekly heavy leg. The Postgres leg
(`tests/test_postgres.py`) additionally proves the same chain on the engine
that will actually run in production.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Every table the app queries. Kept in sync with app/models/*.py by
#: tests/test_postgres.py, which asserts the same set on Postgres.
EXPECTED_TABLES = {
    "pos_ai_job",
    "pos_ai_result",
    "pos_approval",
    "pos_audit_event",
    "pos_budget_reservation",
    "pos_cost_result",
    "pos_document",
    "pos_document_version",
    "pos_evidence_span",
    "pos_item",
    "pos_message_outbox",
    "pos_mission",
    "pos_mission_plan",
    "pos_mission_run",
    "pos_mission_task",
    "pos_purchase_order",
    "pos_risk_result",
    "pos_role",
    "pos_rule_version",
    "pos_scenario_result",
    "pos_session",
    "pos_source_link",
    "pos_sourcing_result",
    "pos_supplier",
    "pos_supplier_site",
    "pos_tenant",
    "pos_timeline_event",
    "pos_transaction",
    "pos_user",
    "pos_workspace",
}

#: Columns that must be real timestamps (B44), not ISO strings in a VARCHAR.
TIMESTAMP_COLUMNS = (
    ("pos_mission", "deadline"),
    ("pos_approval", "expires_at"),
    ("pos_transaction", "ordered_at"),
)


def _alembic_config(url: str) -> object:
    from alembic.config import Config

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _alembic(url: str, action: str) -> None:
    from alembic import command

    cfg = _alembic_config(url)
    if action == "upgrade":
        command.upgrade(cfg, "head")
    elif action == "downgrade":
        command.downgrade(cfg, "base")
    else:  # pragma: no cover - programming error
        raise ValueError(f"unknown action {action!r}")


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'")).scalars()
        found = set(rows)
    engine.dispose()
    return found


@pytest.fixture(scope="module")
def migrated_db(monkeypatch_module: pytest.MonkeyPatch) -> Iterator[str]:
    """A throwaway sqlite database with the chain applied.

    The URL is delivered through `DATABASE_SYNC_URL`, the same variable the
    deployment uses to point the chain at a per-environment database. If the
    env override stopped working, this fixture would try to reach the
    committed default (a Postgres URL) and the test would fail loudly rather
    than silently migrating the wrong database.
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "mig.db"
        url = f"sqlite:///{path.as_posix()}"
        monkeypatch_module.setenv("DATABASE_SYNC_URL", url)
        _alembic(url, "upgrade")
        yield url


def test_upgrade_head_creates_every_pos_table(migrated_db: str) -> None:
    missing = EXPECTED_TABLES - _tables(migrated_db)
    assert not missing, f"migration chain did not create: {sorted(missing)}"


def test_timestamp_columns_are_real_timestamps(migrated_db: str) -> None:
    """B44: the three columns hold timestamps, not ISO strings in a VARCHAR."""
    from sqlalchemy import DateTime

    engine = create_engine(migrated_db)
    try:
        insp = inspect(engine)
        for table, column in TIMESTAMP_COLUMNS:
            cols = {c["name"]: c for c in insp.get_columns(table)}
            assert column in cols, f"{table}.{column} is missing"
            assert isinstance(cols[column]["type"], DateTime), (
                f"{table}.{column} is {cols[column]['type']!r}, not a DateTime"
            )
    finally:
        engine.dispose()


def test_chain_is_reversible(migrated_db: str) -> None:
    """upgrade head -> downgrade base -> upgrade head leaves the same schema."""
    before = _tables(migrated_db)
    _alembic(migrated_db, "downgrade")
    after_down = _tables(migrated_db)
    _alembic(migrated_db, "upgrade")
    after_up = _tables(migrated_db)

    assert EXPECTED_TABLES <= before
    assert not (EXPECTED_TABLES & after_down), "downgrade left pos_* tables behind"
    assert after_up == before, "re-upgrade produced a different schema"


def test_only_one_migration_head() -> None:
    """A branched history would make `alembic upgrade head` ambiguous."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, f"migration history has {len(heads)} heads: {heads}"


def test_migration_revisions_are_linear() -> None:
    """Every revision except the base has exactly one parent."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    revisions = list(script.walk_revisions())
    assert len(revisions) >= 5, "the chain lost revisions"
    for rev in revisions:
        if rev.down_revision is None:
            continue
        assert isinstance(rev.down_revision, str), (
            f"revision {rev.revision} has a branch parent {rev.down_revision!r}"
        )


def test_alembic_ini_does_not_embed_credentials() -> None:
    """The committed default URL must carry no password."""
    from sqlalchemy.engine import make_url

    ini = (REPO_ROOT / "alembic.ini").read_text(encoding="utf-8")
    default = ""
    for line in ini.splitlines():
        if line.strip().startswith("sqlalchemy.url"):
            default = line.split("=", 1)[1].strip()
    assert default, "alembic.ini lost its default url"
    url = make_url(default)
    assert not url.password, "alembic.ini embeds a password in the default URL"
