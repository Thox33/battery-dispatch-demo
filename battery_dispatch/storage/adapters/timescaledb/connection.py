"""Engine construction for PostgreSQL with TimescaleDB."""

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from battery_dispatch.config.config_manager import DatabaseConfig


def database_url(config: DatabaseConfig) -> URL:
    return URL.create(
        "postgresql+asyncpg",
        username=config.user,
        password=config.password.get_secret_value(),
        host=config.host,
        port=config.port,
        database=config.name,
    )


def create_engine(config: DatabaseConfig) -> AsyncEngine:
    return create_async_engine(
        database_url(config),
        pool_size=config.pool_size,
        pool_pre_ping=True,
    )
