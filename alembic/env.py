"""Alembic env: own schema prefix pos_*, non-destructive migrations.

Uses a sync engine for migrations (standard); the app talks to the same
tables over asyncpg at runtime. The URL comes from the Config, from
DATABASE_SYNC_URL, or from the committed default in alembic.ini - in that
order of precedence, and the order is deliberate: see `sync_url` below.
"""

import os
from logging.config import fileConfig

from sqlalchemy import create_engine

from alembic import context
from app.models import Base  # noqa: F401  (registers pos_* metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# The URL, in order of precedence:
#
#   1. an explicit override on the Config - a caller that says "migrate
#      THIS database" means it, whatever the environment says;
#   2. DATABASE_SYNC_URL - the operator's per-environment target;
#   3. the URL committed in alembic.ini.
#
# (1) and (3) are told apart by comparing against the value the ini file
# itself carries. That has to be read from the file: Alembic's Config
# hands back the same live section that `set_main_option` writes into, so
# the configured value cannot be compared against the ini's own value
# through the Config - they are one object.
#
# It matters: three callers set the URL in-process - the rollback drill
# and two test suites - and the environment variable used to beat them,
# so a test that asked for a scratch database quietly migrated the main
# one instead, and then asserted that the scratch database had no tables
# in it. The env var is the operator's tool; it must not overrule an
# explicit instruction from the code that is asking.
def _committed_default_url() -> str:
    """The URL the committed alembic.ini carries, before any override."""
    import configparser

    if not config.config_file_name:
        return ""
    parser = configparser.ConfigParser()
    try:
        parser.read(config.config_file_name)
        return parser.get("alembic", "sqlalchemy.url", fallback="")
    except (OSError, configparser.Error):
        return ""


_ini_default = _committed_default_url()
_configured = config.get_main_option("sqlalchemy.url", "") or ""
_explicit = _configured if _configured and _configured != _ini_default else ""
sync_url = _explicit or os.environ.get("DATABASE_SYNC_URL") or _ini_default


def _require_credentials(url: str) -> None:
    """Refuse to migrate with a credential-less URL.

    The committed default in alembic.ini carries no password, so a
    forgotten DATABASE_SYNC_URL would otherwise fail deep inside the driver
    with an authentication error that says nothing about what to do. The
    release gate requires the credentials to be per-environment, so the
    operator is told exactly which variable to set.
    """
    if not url:
        raise RuntimeError(
            "no database URL for migrations: set DATABASE_SYNC_URL "
            "(e.g. postgresql+psycopg://user:password@host:5432/db)"
        )
    if "//" not in url or "@" not in url.split("://", 1)[1].split("/", 1)[0]:
        return  # sqlite:///... — no credentials to carry
    credentials = url.split("://", 1)[1].split("/", 1)[0]
    if ":" not in credentials:
        raise RuntimeError(
            "DATABASE_SYNC_URL has no password: set it per environment, e.g. "
            "postgresql+psycopg://user:password@host:5432/db"
        )


def run_migrations_offline() -> None:
    _require_credentials(sync_url)
    context.configure(url=sync_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    _require_credentials(sync_url)
    engine = create_engine(sync_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        # The pool keeps a connection open, and on Windows an open
        # connection holds a lock on a file-backed database: without this,
        # a sqlite migration chain leaves the file undeletable and a
        # caller that wants to clean up after itself cannot.
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
