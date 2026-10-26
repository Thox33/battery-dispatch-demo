"""Creates the components and owns their lifecycle."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from battery_dispatch import __version__
from battery_dispatch.config.config_manager import AppConfig
from battery_dispatch.core.component_base import ComponentBase
from battery_dispatch.core.health import ComponentHealth, HealthState, SystemHealth
from battery_dispatch.market_data.price_importer import PriceImporter
from battery_dispatch.market_data.smard_client import SmardClient
from battery_dispatch.storage.repositories.price_repository import PriceRepository
from battery_dispatch.storage.storage_manager import StorageManager


logger = logging.getLogger(__name__)


class Controller:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.storage = StorageManager(config.database)
        self.smard = SmardClient(config.smard)
        self.prices = PriceRepository(self.storage)
        self.price_importer = PriceImporter(self.smard, self.prices)
        self.components: list[ComponentBase] = [self.storage, self.smard]
        self._started: list[ComponentBase] = []

    async def start(self) -> None:
        for component in self.components:
            logger.info("Starting component %s", component.name)
            try:
                await component.start()
            except Exception:
                logger.exception("Component %s failed to start", component.name)
                await self.stop()
                raise
            self._started.append(component)

    async def stop(self) -> None:
        while self._started:
            component = self._started.pop()
            logger.info("Stopping component %s", component.name)
            try:
                await component.stop()
            except Exception:
                # Keep going so that the remaining components still get stopped.
                logger.exception("Component %s failed to stop", component.name)

    @asynccontextmanager
    async def running(self) -> AsyncGenerator["Controller"]:
        await self.start()
        try:
            yield self
        finally:
            await self.stop()

    async def health(self) -> SystemHealth:
        components = await asyncio.gather(*(self._health_of(c) for c in self.components))
        healthy = all(c.state is HealthState.OK for c in components)
        return SystemHealth(
            state=HealthState.OK if healthy else HealthState.DOWN,
            version=__version__,
            components=list(components),
        )

    @staticmethod
    async def _health_of(component: ComponentBase) -> ComponentHealth:
        try:
            return await component.health()
        except Exception as exc:
            logger.exception("Health check of %s raised", component.name)
            return ComponentHealth(
                name=component.name, state=HealthState.DOWN, detail=type(exc).__name__
            )
