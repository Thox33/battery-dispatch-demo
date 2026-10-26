"""Loads the application configuration.

Precedence, highest first:

1. environment variables, prefix `BATTERY_DISPATCH_`, nesting with `__`
   (e.g. `BATTERY_DISPATCH_DATABASE__HOST=db`)
2. `config/config.yaml`, local overrides, not under version control
3. `config/default_config.yaml`
4. defaults in the models below
"""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


CONFIG_DIR_ENV = "BATTERY_DISPATCH_CONFIG_DIR"
DEFAULT_CONFIG_DIR = Path("config")


class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    name: str = "battery_dispatch"
    user: str = "battery_dispatch"
    password: SecretStr = SecretStr("")
    pool_size: int = 5
    health_timeout_s: float = 2.0


class SmardConfig(BaseModel):
    base_url: str = "https://www.smard.de/app/chart_data"
    filter_id: int = 4169  # wholesale price Germany/Luxembourg
    region: str = "DE"
    resolution: str = "quarterhour"
    timeout_s: float = 10.0


class HttpConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000


class OptimizationConfig(BaseModel):
    solver_time_limit_s: float = 30.0
    # The solver stops once the schedule is proven to be within this fraction of the
    # best possible revenue. Proving a tighter gap can take minutes on long blocks of
    # equal negative prices.
    mip_gap_rel: float = Field(default=5e-3, ge=0, lt=1)


class LoggingConfig(BaseModel):
    config_file: Path = DEFAULT_CONFIG_DIR / "logging.yaml"
    level: str | None = None


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BATTERY_DISPATCH_",
        env_nested_delimiter="__",
        extra="forbid",
    )

    database: DatabaseConfig = DatabaseConfig()
    smard: SmardConfig = SmardConfig()
    http: HttpConfig = HttpConfig()
    optimization: OptimizationConfig = OptimizationConfig()
    logging: LoggingConfig = LoggingConfig()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # The YAML files arrive as init arguments; environment variables win over them.
        return env_settings, init_settings


class ConfigManager:
    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = config_dir or Path(os.environ.get(CONFIG_DIR_ENV, DEFAULT_CONFIG_DIR))

    def load(self) -> AppConfig:
        data: dict[str, Any] = {}
        for name in ("default_config.yaml", "config.yaml"):
            data = _deep_merge(data, self._read_yaml(self.config_dir / name))
        return AppConfig(**data)

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        if content is None:
            return {}
        if not isinstance(content, dict):
            raise ValueError(f"{path} must contain a mapping at top level")
        return content  # pyright: ignore[reportUnknownVariableType]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(current, value)  # pyright: ignore[reportUnknownArgumentType]
        else:
            merged[key] = value
    return merged
