"""Alembic env: own schema prefix pos_*, non-destructive migrations (expand->migrate->contract)."""

from logging.config import fileConfig

from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None  # Phase 1 wires SQLAlchemy Base.metadata here.


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Phase 1: engine_from_config + connection + Base.metadata.
    context.configure(url=config.get_main_option("sqlalchemy.url"))
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
