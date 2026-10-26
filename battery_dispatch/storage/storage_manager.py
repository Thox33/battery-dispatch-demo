"""Owns the database engine and hands out sessions."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from battery_dispatch.config.config_manager import DatabaseConfig
from battery_dispatch.core.component_base import ComponentBase
from battery_dispatch.core.health import ComponentHealth, HealthState
from battery_dispatch.storage.adapters.timescaledb.connection import create_engine
from battery_dispatch.storage.errors import StorageUnavailableError


class StorageManager(ComponentBase):
    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__("storage")
        self._config = config
        self._engine: AsyncEngine | None = None
        self._sessions: async_sessionmaker[AsyncSession] | None = None

    async def start(self) -> None:
        # The engine connects lazily. An unreachable database therefore does not stop
        # the application from starting; it shows up in the health check instead.
        self._engine = create_engine(self._config)
        self._sessions = async_sessionmaker(self._engine, expire_on_commit=False)

    async def stop(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
        self._engine = None
        self._sessions = None

    async def health(self) -> ComponentHealth:
        if self._engine is None:
            return ComponentHealth(name=self.name, state=HealthState.DOWN, detail="not started")
        try:
            async with asyncio.timeout(self._config.health_timeout_s):
                async with self._engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
        except (SQLAlchemyError, OSError, TimeoutError) as exc:
            return ComponentHealth(
                name=self.name, state=HealthState.DOWN, detail=type(exc).__name__
            )
        return ComponentHealth(name=self.name, state=HealthState.OK)

    def session(self) -> AbstractAsyncContextManager[AsyncSession]:
        """Open a session for `async with`.

        Connection failures surface from asyncpg as `OSError` (including `TimeoutError`),
        which SQLAlchemy passes on unwrapped. The connection opens lazily inside the block,
        so any `OSError` raised inside the block is raised as `StorageUnavailableError`.
        The block must therefore hold only database work; a timeout belongs around the
        whole `async with`, where it is not translated.
        """
        if self._sessions is None:
            raise RuntimeError("StorageManager is not started")
        return _session_scope(self._sessions)


@asynccontextmanager
async def _session_scope(
    sessions: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    try:
        async with sessions() as session:
            yield session
    except OSError as exc:  # TimeoutError is a subclass of OSError
        raise StorageUnavailableError(f"database unavailable: {type(exc).__name__}") from exc
