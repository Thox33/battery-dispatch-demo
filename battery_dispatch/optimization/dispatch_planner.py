"""Loads stored prices for a time range and computes the battery schedule."""

import asyncio
import logging
from datetime import datetime, timedelta

from battery_dispatch.config.config_manager import OptimizationConfig
from battery_dispatch.market_data.models import BIDDING_ZONE_DE_LU
from battery_dispatch.optimization.battery import BatteryParameters
from battery_dispatch.optimization.milp_optimizer import optimize
from battery_dispatch.optimization.schedule import Schedule
from battery_dispatch.storage.repositories.price_repository import PriceRepository


logger = logging.getLogger(__name__)

QUARTER_HOUR = timedelta(minutes=15)


class PricesIncompleteError(Exception):
    """Not every quarter hour of the requested range has a stored price."""

    def __init__(self, expected: int, found: int, first_missing: datetime) -> None:
        super().__init__(
            f"{found} of {expected} quarter-hour prices are stored, "
            f"first missing: {first_missing.isoformat()}"
        )
        self.expected = expected
        self.found = found
        self.first_missing = first_missing


class DispatchPlanner:
    def __init__(self, repository: PriceRepository, config: OptimizationConfig) -> None:
        self._repository = repository
        self._config = config

    async def plan(self, start: datetime, end: datetime, battery: BatteryParameters) -> Schedule:
        """Compute the schedule for the quarter hours of `[start, end)`.

        Raises `PricesIncompleteError` before solving if a price is missing; gaps are never
        filled in. The solver runs in a worker thread so that it does not block the event
        loop.
        """
        prices = await self._repository.list_range(BIDDING_ZONE_DE_LU, start, end)
        expected = _quarter_hours(start, end)
        stored = {p.time for p in prices}
        missing = [t for t in expected if t not in stored]
        if missing:
            raise PricesIncompleteError(
                expected=len(expected), found=len(prices), first_missing=missing[0]
            )

        schedule = await asyncio.to_thread(
            optimize,
            prices,
            battery,
            time_limit_s=self._config.solver_time_limit_s,
            mip_gap_rel=self._config.mip_gap_rel,
        )
        logger.info(
            "Optimised %s to %s: %d steps, revenue %.2f EUR, solver %d ms",
            start,
            end,
            len(schedule.steps),
            schedule.revenue_eur,
            schedule.runtime_ms,
        )
        return schedule


def _quarter_hours(start: datetime, end: datetime) -> list[datetime]:
    times: list[datetime] = []
    time = start
    while time < end:
        times.append(time)
        time += QUARTER_HOUR
    return times
