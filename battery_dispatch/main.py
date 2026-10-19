"""Entry point: load configuration, set up logging, serve the API."""

import uvicorn

from battery_dispatch.communication.http.server import create_app
from battery_dispatch.config.config_manager import ConfigManager
from battery_dispatch.core.controller import Controller
from battery_dispatch.logging_setup.logging_configurator import configure_logging


def main() -> None:
    config = ConfigManager().load()
    configure_logging(config.logging)
    app = create_app(Controller(config))
    # log_config=None keeps uvicorn from replacing the logging configuration above.
    uvicorn.run(app, host=config.http.host, port=config.http.port, log_config=None)


if __name__ == "__main__":
    main()
