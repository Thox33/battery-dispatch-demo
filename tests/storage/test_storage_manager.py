import pytest

from battery_dispatch.config.config_manager import DatabaseConfig
from battery_dispatch.core.health import HealthState
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


def test_session_before_start_raises() -> None:
    storage = StorageManager(DatabaseConfig())

    with pytest.raises(RuntimeError, match="not started"):
        storage.session()
