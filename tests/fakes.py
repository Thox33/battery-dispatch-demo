"""Test doubles shared across test modules."""

from collections.abc import Sequence
from datetime import datetime

from battery_dispatch.config.config_manager import DatabaseConfig, OptimizationConfig, SmardConfig
from battery_dispatch.core.component_base import ComponentBase
from battery_dispatch.core.health import ComponentHealth, HealthState
from battery_dispatch.market_data.models import ImportResult, PricePoint
from battery_dispatch.market_data.price_importer import PriceImporter
from battery_dispatch.market_data.smard_client import SmardClient, SmardError
from battery_dispatch.optimization.battery import BatteryParameters
from battery_dispatch.optimization.dispatch_planner import DispatchPlanner
from battery_dispatch.optimization.schedule import Schedule
from battery_dispatch.storage.repositories.price_repository import PriceRepository
from battery_dispatch.storage.storage_manager import StorageManager


class FakeComponent(ComponentBase):
    def __init__(
        self,
        name: str,
        events: list[str] | None = None,
        state: HealthState = HealthState.OK,
        fail_on_start: bool = False,
    ) -> None:
        super().__init__(name)
        self.events = events if events is not None else []
        self.state = state
        self.fail_on_start = fail_on_start

    async def start(self) -> None:
        if self.fail_on_start:
            raise RuntimeError(f"{self.name} cannot start")
        self.events.append(f"start {self.name}")

    async def stop(self) -> None:
        self.events.append(f"stop {self.name}")

    async def health(self) -> ComponentHealth:
        return ComponentHealth(name=self.name, state=self.state)


class RaisingHealthComponent(FakeComponent):
    async def health(self) -> ComponentHealth:
        raise ValueError("broken")


class FakeSmardClient(SmardClient):
    def __init__(self, points: list[PricePoint]) -> None:
        super().__init__(SmardConfig())
        self.points = points
        self.requests: list[tuple[datetime, datetime]] = []

    async def fetch_prices(self, start: datetime, end: datetime) -> list[PricePoint]:
        self.requests.append((start, end))
        return self.points


class FakePriceRepository(PriceRepository):
    def __init__(self, stored: list[PricePoint] | None = None) -> None:
        super().__init__(StorageManager(DatabaseConfig()))
        self.stored = stored or []
        self.error: Exception | None = None
        self.upserts: list[tuple[str, list[PricePoint]]] = []
        self.queries: list[tuple[str, datetime, datetime]] = []

    async def upsert(self, bidding_zone: str, points: Sequence[PricePoint]) -> int:
        self.upserts.append((bidding_zone, list(points)))
        if self.error is not None:
            raise self.error
        return len(points)

    async def list_range(
        self, bidding_zone: str, start: datetime, end: datetime
    ) -> list[PricePoint]:
        self.queries.append((bidding_zone, start, end))
        if self.error is not None:
            raise self.error
        return self.stored


class FakePriceImporter(PriceImporter):
    def __init__(self, result: ImportResult | None = None, fail: bool = False) -> None:
        super().__init__(FakeSmardClient([]), FakePriceRepository())
        self.result = result or ImportResult(fetched=0, written=0)
        self.fail = fail
        self.error: Exception | None = None
        self.requests: list[tuple[datetime, datetime]] = []

    async def import_range(self, start: datetime, end: datetime) -> ImportResult:
        self.requests.append((start, end))
        if self.fail:
            raise SmardError("request to SMARD failed")
        if self.error is not None:
            raise self.error
        return self.result


class FakeDispatchPlanner(DispatchPlanner):
    def __init__(self, schedule: Schedule, error: Exception | None = None) -> None:
        super().__init__(FakePriceRepository(), OptimizationConfig())
        self.schedule = schedule
        self.error = error
        self.requests: list[tuple[datetime, datetime, BatteryParameters]] = []

    async def plan(self, start: datetime, end: datetime, battery: BatteryParameters) -> Schedule:
        self.requests.append((start, end, battery))
        if self.error is not None:
            raise self.error
        return self.schedule
