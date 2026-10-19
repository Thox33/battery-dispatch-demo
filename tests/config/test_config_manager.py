from pathlib import Path

import pytest

from battery_dispatch.config.config_manager import ConfigManager


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    (tmp_path / "default_config.yaml").write_text(
        "database:\n  host: from-default\n  port: 5432\nhttp:\n  port: 8000\n",
        encoding="utf-8",
    )
    return tmp_path


def test_defaults_without_files(tmp_path: Path) -> None:
    config = ConfigManager(tmp_path).load()

    assert config.database.host == "localhost"
    assert config.http.port == 8000


def test_reads_default_config(config_dir: Path) -> None:
    config = ConfigManager(config_dir).load()

    assert config.database.host == "from-default"


def test_local_config_overrides_single_keys(config_dir: Path) -> None:
    (config_dir / "config.yaml").write_text("database:\n  port: 6543\n", encoding="utf-8")

    config = ConfigManager(config_dir).load()

    assert config.database.port == 6543
    assert config.database.host == "from-default"


def test_environment_overrides_files(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (config_dir / "config.yaml").write_text("database:\n  host: from-local\n", encoding="utf-8")
    monkeypatch.setenv("BATTERY_DISPATCH_DATABASE__HOST", "from-env")

    config = ConfigManager(config_dir).load()

    assert config.database.host == "from-env"
    assert config.database.port == 5432


def test_password_is_not_shown_in_repr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BATTERY_DISPATCH_DATABASE__PASSWORD", "hunter2")

    config = ConfigManager(tmp_path).load()

    assert config.database.password.get_secret_value() == "hunter2"
    assert "hunter2" not in repr(config)


def test_unknown_keys_are_rejected(config_dir: Path) -> None:
    (config_dir / "config.yaml").write_text("databse:\n  host: typo\n", encoding="utf-8")

    with pytest.raises(ValueError, match="databse"):
        ConfigManager(config_dir).load()
