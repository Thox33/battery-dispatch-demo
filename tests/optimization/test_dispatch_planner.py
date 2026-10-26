from datetime import UTC, datetime, timedelta

import pytest

from battery_dispatch.config.config_manager import OptimizationConfig
from battery_dispatch.market_data.models import BIDDING_ZONE_DE_LU, PricePoint
from battery_dispatch.optimization.battery import BatteryParameters
from battery_dispatch.optimization.dispatch_planner import DispatchPlanner, PricesIncompleteError
from tests.fakes import FakePriceRepository


START = datetime(2026, 10, 26, tzinfo=UTC)
QUARTER = timedelta(minutes=15)
END = START + 4 * QUARTER

BATTERY = BatteryParameters(
    capacity_kwh=100.0,
    max_charge_kw=100.0,
    max_discharge_kw=100.0,
    charge_efficiency=0.95,
    discharge_efficiency=0.95,
    soc_min=0.0,
    soc_max=1.0,
    soc_initial=0.5,
)


def points(prices: dict[int, float]) -> list[PricePoint]:
    return [
        PricePoint(time=START + i * QUARTER, price_eur_per_mwh=price)
        for i, price in sorted(prices.items())
    ]


def planner(stored: list[PricePoint]) -> tuple[DispatchPlanner, FakePriceRepository]:
    repository = FakePriceRepository(stored)
    return DispatchPlanner(repository, OptimizationConfig(solver_time_limit_s=10.0)), repository


async def test_complete_prices_are_optimized() -> None:
    dispatch_planner, repository = planner(points({0: 10.0, 1: -20.0, 2: 80.0, 3: 120.0}))

    schedule = await dispatch_planner.plan(START, END, BATTERY)

    assert repository.queries == [(BIDDING_ZONE_DE_LU, START, END)]
    assert [s.time for s in schedule.steps] == [START + i * QUARTER for i in range(4)]
    assert schedule.revenue_eur > 0


async def test_incomplete_prices_raise() -> None:
    dispatch_planner, _ = planner(points({0: 10.0, 1: 20.0, 3: 40.0}))

    with pytest.raises(PricesIncompleteError) as excinfo:
        await dispatch_planner.plan(START, END, BATTERY)

    assert excinfo.value.expected == 4
    assert excinfo.value.found == 3
    assert excinfo.value.first_missing == START + 2 * QUARTER


async def test_no_stored_prices_raise() -> None:
    dispatch_planner, _ = planner([])

    with pytest.raises(PricesIncompleteError) as excinfo:
        await dispatch_planner.plan(START, END, BATTERY)

    assert excinfo.value.expected == 4
    assert excinfo.value.found == 0
    assert excinfo.value.first_missing == START
