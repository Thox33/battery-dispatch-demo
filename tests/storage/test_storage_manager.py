import asyncio
from datetime import UTC, datetime

import pytest

from battery_dispatch.config.config_manager import DatabaseConfig
from battery_dispatch.core.health import HealthState
from battery_dispatch.market_data.models import PricePoint
from battery_dispatch.storage.errors import StorageUnavailableError
from battery_dispatch.storage.repositories.price_repository import PriceRepository
from battery_dispatch.storage.storage_manager import StorageManager


async def test_health_before_start_is_down() -> None:
    storage = StorageManager(DatabaseConfig())

    health = await storage.health()

    assert health.state is HealthState.DOWN
    assert health.detail == "not started"


async def test_unreachable_database_is_reported_not_raised() -> None:
    # Port 1 on localhost is not a PostgreSQL server.
    storage = StorageManager(DatabaseConfig(port=1, health_timeout_s=0.5))
    await storage.start()
    try:
        health = await storage.health()
    finally:
        await storage.stop()

    assert health.state is HealthState.DOWN


async def test_unreachable_database_raises_storage_unavailable() -> None:
    # Port 1 on localhost is not a PostgreSQL server; the connection is refused.
    storage = StorageManager(DatabaseConfig(host="127.0.0.1", port=1))
    repository = PriceRepository(storage)
    start = datetime(2026, 10, 25, 22, tzinfo=UTC)
    await storage.start()
    try:
        with pytest.raises(StorageUnavailableError) as read_error:
            await repository.list_range("TEST-DE", start, datetime(2026, 10, 26, tzinfo=UTC))
        with pytest.raises(StorageUnavailableError) as write_error:
            await repository.upsert("TEST-DE", [PricePoint(time=start, price_eur_per_mwh=1.0)])
    finally:
        await storage.stop()

    assert isinstance(read_error.value.__cause__, OSError)
    assert isinstance(write_error.value.__cause__, OSError)


async def test_other_errors_in_a_session_are_not_translated() -> None:
    storage = StorageManager(DatabaseConfig(host="127.0.0.1", port=1))
    await storage.start()
    try:
        with pytest.raises(ValueError, match="not a storage error"):
            async with storage.session():
                raise ValueError("not a storage error")
    finally:
        await storage.stop()


async def test_os_errors_inside_a_session_count_as_unavailable() -> None:
    storage = StorageManager(DatabaseConfig(host="127.0.0.1", port=1))
    await storage.start()
    try:
        with pytest.raises(StorageUnavailableError) as error:
            async with storage.session():
                raise FileNotFoundError("raised inside the block")
    finally:
        await storage.stop()

    assert isinstance(error.value.__cause__, FileNotFoundError)


async def test_timeout_around_a_session_is_not_translated() -> None:
    storage = StorageManager(DatabaseConfig(host="127.0.0.1", port=1))
    await storage.start()
    try:
        with pytest.raises(TimeoutError) as error:
            async with asyncio.timeout(0.01), storage.session():
                await asyncio.sleep(1)
    finally:
        await storage.stop()

    assert not isinstance(error.value, StorageUnavailableError)


def test_session_before_start_raises() -> None:
    storage = StorageManager(DatabaseConfig())

    with pytest.raises(RuntimeError, match="not started"):
        storage.session()
