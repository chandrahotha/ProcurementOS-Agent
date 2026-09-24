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


def run_migrations_offline() -> None:
    context.configure(url=sync_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(sync_url, pool_pre_ping=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
