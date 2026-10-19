"""Alembic environment. Reads the database settings from the application configuration."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from battery_dispatch.config.config_manager import ConfigManager
from battery_dispatch.storage.adapters.timescaledb.connection import create_engine, database_url


config = ConfigManager().load()

# No ORM metadata yet; migrations are written by hand.
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(config.database).render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_engine(config.database)
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
