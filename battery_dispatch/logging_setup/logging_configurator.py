"""Configures the standard library logging from a YAML dictConfig file."""

import logging
import logging.config

import yaml

from battery_dispatch.config.config_manager import LoggingConfig


def configure_logging(config: LoggingConfig) -> None:
    if config.config_file.is_file():
        logging.config.dictConfig(yaml.safe_load(config.config_file.read_text(encoding="utf-8")))
    else:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).warning(
            "Logging config %s not found, using basic configuration", config.config_file
        )
    if config.level:
        logging.getLogger().setLevel(config.level.upper())
