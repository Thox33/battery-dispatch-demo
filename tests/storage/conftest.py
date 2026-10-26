"""Fixtures for tests against a real TimescaleDB.

The tests are skipped if the database is not reachable, unless
`BATTERY_DISPATCH_REQUIRE_DB` is set (as in CI), in which case they fail.
"""

import os
import socket
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from battery_dispatch.config.config_manager import ConfigManager, DatabaseConfig


PROJECT_ROOT = Path(__file__).parents[2]


def _reachable(config: DatabaseConfig) -> bool:
    try:
        with socket.create_connection((config.host, config.port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def database_config() -> DatabaseConfig:
    config = ConfigManager(PROJECT_ROOT / "config").load().database
    if not _reachable(config):
        message = f"TimescaleDB not reachable at {config.host}:{config.port}"
        if os.environ.get("BATTERY_DISPATCH_REQUIRE_DB"):
            pytest.fail(message)
        pytest.skip(f"{message}, start it with: docker compose up -d db")
    command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
    return config
