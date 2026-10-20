"""Alembic env: own schema prefix pos_*, non-destructive migrations.

Uses a sync engine for migrations (standard); the app talks to the same
tables over asyncpg at runtime. URL comes from alembic.ini, overridable
with DATABASE_SYNC_URL for local runs.
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

sync_url = os.environ.get("DATABASE_SYNC_URL") or config.get_main_option("sqlalchemy.url")


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
