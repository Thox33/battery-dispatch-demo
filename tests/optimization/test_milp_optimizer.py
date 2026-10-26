import math
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pulp  # pyright: ignore[reportMissingTypeStubs]
import pytest

from battery_dispatch.config.config_manager import OptimizationConfig
from battery_dispatch.market_data.models import PricePoint
from battery_dispatch.optimization.battery import BatteryParameters
from battery_dispatch.optimization.milp_optimizer import (
    STEP_HOURS,
    OptimizationError,
    optimize,
)
from battery_dispatch.optimization.schedule import Schedule


START = datetime(2026, 10, 26, tzinfo=UTC)
QUARTER = timedelta(minutes=15)
TIME_LIMIT_S = 10.0
# The production default, so that the tests cover the configured solver behaviour.
MIP_GAP_REL = OptimizationConfig().mip_gap_rel
TOLERANCE = 1e-4

BATTERY = BatteryParameters(
    capacity_kwh=1000.0,
    max_charge_kw=500.0,
    max_discharge_kw=500.0,
    charge_efficiency=0.95,
    discharge_efficiency=0.95,
    soc_min=0.1,
    soc_max=0.9,
    soc_initial=0.5,
)
LOSSLESS = BatteryParameters(
    capacity_kwh=100.0,
    max_charge_kw=100.0,
    max_discharge_kw=100.0,
    charge_efficiency=1.0,
    discharge_efficiency=1.0,
    soc_min=0.0,
    soc_max=1.0,
    soc_initial=0.5,
)


def series(prices: list[float], start: datetime = START) -> list[PricePoint]:
    return [
        PricePoint(time=start + i * QUARTER, price_eur_per_mwh=price)
        for i, price in enumerate(prices)
    ]


def day_curve() -> list[float]:
    """One day with a morning and evening peak and a negative midday dip."""
    return [
        60.0 + 50.0 * math.sin(2 * math.pi * (t - 24) / 48) - (120.0 if 44 <= t < 56 else 0.0)
        for t in range(96)
    ]


def run(prices: list[PricePoint], battery: BatteryParameters) -> Schedule:
    return optimize(prices, battery, time_limit_s=TIME_LIMIT_S, mip_gap_rel=MIP_GAP_REL)


def solve(prices: list[float], battery: BatteryParameters = BATTERY) -> Schedule:
    return run(series(prices), battery)


def test_balance_holds_in_every_step() -> None:
    schedule = solve(day_curve())

    energy = BATTERY.initial_energy_kwh
    for step in schedule.steps:
        energy += (
            BATTERY.charge_efficiency * step.charge_kw * STEP_HOURS
            - step.discharge_kw * STEP_HOURS / BATTERY.discharge_efficiency
        )
        assert step.soc_kwh == pytest.approx(energy, abs=TOLERANCE)
        energy = step.soc_kwh


def test_limits_hold() -> None:
    schedule = solve(day_curve())

    for step in schedule.steps:
        assert 0.0 <= step.charge_kw <= BATTERY.max_charge_kw + TOLERANCE
        assert 0.0 <= step.discharge_kw <= BATTERY.max_discharge_kw + TOLERANCE
        assert BATTERY.min_energy_kwh - TOLERANCE <= step.soc_kwh
        assert step.soc_kwh <= BATTERY.max_energy_kwh + TOLERANCE


def test_final_energy_not_below_initial() -> None:
    # Expensive last hour: selling everything at the end would pay without the constraint.
    schedule = solve([10.0] * 4 + [200.0] * 4)

    assert schedule.steps[-1].soc_kwh >= BATTERY.initial_energy_kwh - TOLERANCE


def test_no_simultaneous_charge_and_discharge() -> None:
    schedule = solve([-500.0] * 8 + [-200.0] * 8)

    assert schedule.charged_kwh > 0
    for step in schedule.steps:
        assert step.charge_kw == 0.0 or step.discharge_kw == 0.0


def test_negative_prices_are_used() -> None:
    schedule = solve([-50.0] * 4 + [50.0] * 4)

    assert all(step.charge_kw > 0 for step in schedule.steps[:4])
    assert all(step.charge_kw == 0 for step in schedule.steps[4:])
    assert schedule.revenue_eur > 0


def test_two_steps_by_hand() -> None:
    battery = BatteryParameters(
        capacity_kwh=100.0,
        max_charge_kw=100.0,
        max_discharge_kw=100.0,
        charge_efficiency=0.9,
        discharge_efficiency=0.9,
        soc_min=0.0,
        soc_max=1.0,
        soc_initial=0.5,
    )

    schedule = solve([0.0, 100.0], battery)

    # Charge 25 kWh for free, 22.5 kWh are stored. Discharging back to the initial 50 kWh
    # delivers 22.5 kWh * 0.9 = 20.25 kWh, sold at 100 EUR/MWh.
    first, second = schedule.steps
    assert first.charge_kw == pytest.approx(100.0)
    assert first.soc_kwh == pytest.approx(72.5)
    assert second.discharge_kw == pytest.approx(81.0)
    assert second.soc_kwh == pytest.approx(50.0)
    assert schedule.revenue_eur == pytest.approx(2.025)
    assert schedule.charged_kwh == pytest.approx(25.0)
    assert schedule.discharged_kwh == pytest.approx(20.25)
    assert schedule.equivalent_full_cycles == pytest.approx(0.2025)
    assert schedule.degradation_cost_eur == 0.0
    assert schedule.solver_status == "optimal"


def test_flat_prices_do_nothing() -> None:
    schedule = solve([50.0] * 8)

    assert all(s.charge_kw == 0.0 and s.discharge_kw == 0.0 for s in schedule.steps)
    assert schedule.revenue_eur == 0.0
    assert schedule.equivalent_full_cycles == 0.0


def test_degradation_cost_suppresses_small_spreads() -> None:
    prices = [50.0, 55.0]
    worn = replace(LOSSLESS, degradation_cost_eur_per_mwh=10.0)

    without_cost = solve(prices, LOSSLESS)
    with_cost = solve(prices, worn)

    assert without_cost.discharged_kwh > 0
    assert with_cost.discharged_kwh == 0.0
    assert with_cost.revenue_eur == 0.0


def test_degradation_cost_is_reported() -> None:
    worn = replace(LOSSLESS, degradation_cost_eur_per_mwh=10.0)

    schedule = solve([0.0, 100.0], worn)

    # 25 kWh charged for free and sold at 100 EUR/MWh, 10 EUR/MWh wear on the sold energy.
    assert schedule.revenue_eur == pytest.approx(2.5)
    assert schedule.degradation_cost_eur == pytest.approx(0.25)


def test_daylight_saving_day() -> None:
    # 2026-10-25 in Europe/Berlin: 25 hours, 100 quarter hours.
    prices = series(day_curve() + day_curve()[:4], start=datetime(2026, 10, 24, 22, tzinfo=UTC))

    schedule = run(prices, BATTERY)

    assert len(schedule.steps) == 100
    assert [s.time for s in schedule.steps] == [p.time for p in prices]
    assert schedule.revenue_eur > 0


def test_empty_prices_are_rejected() -> None:
    with pytest.raises(ValueError, match="at least one price"):
        run([], BATTERY)


def test_solution_without_proof_of_optimality_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def stop_at_time_limit(problem: pulp.LpProblem, *_args: object, **_kwargs: object) -> int:
        problem.assignStatus(  # pyright: ignore[reportUnknownMemberType]
            pulp.LpStatusOptimal, pulp.LpSolutionIntegerFeasible
        )
        return pulp.LpStatusOptimal

    monkeypatch.setattr(pulp.LpProblem, "solve", stop_at_time_limit)

    with pytest.raises(OptimizationError, match="without an optimal solution"):
        solve([0.0, 100.0])


def test_solver_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_problem: pulp.LpProblem, *_args: object, **_kwargs: object) -> int:
        raise pulp.PulpSolverError("cannot execute cbc")

    monkeypatch.setattr(pulp.LpProblem, "solve", fail)

    with pytest.raises(OptimizationError, match="solver failed: cannot execute cbc"):
        solve([0.0, 100.0])


def test_missing_solver_value_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def optimal_without_values(problem: pulp.LpProblem, *_args: object, **_kwargs: object) -> int:
        problem.assignStatus(  # pyright: ignore[reportUnknownMemberType]
            pulp.LpStatusOptimal, pulp.LpSolutionOptimal
        )
        return pulp.LpStatusOptimal

    monkeypatch.setattr(pulp.LpProblem, "solve", optimal_without_values)

    with pytest.raises(OptimizationError, match="no value for charge_0"):
        solve([0.0, 100.0])


@pytest.mark.parametrize(
    "prices",
    [
        pytest.param([50.0] * 8 + [-500.0] * 48 + [50.0] * 8, id="48 x -500 between 50"),
        pytest.param([50.0] * 8 + [-10.0] * 48 + [50.0] * 8, id="48 x -10 between 50"),
        pytest.param([-500.0] * 96, id="96 x -500"),
    ],
)
def test_flat_negative_blocks_solve_quickly(prices: list[float]) -> None:
    # Identical negative prices make many schedules almost equally good, which made
    # proving optimality run into the time limit. The relative gap keeps this fast.
    schedule = optimize(
        series(prices),
        BATTERY,
        time_limit_s=OptimizationConfig().solver_time_limit_s,
        mip_gap_rel=MIP_GAP_REL,
    )

    assert schedule.solver_status == "optimal"
    assert schedule.runtime_ms < 10_000
    assert schedule.revenue_eur > 0
    for step in schedule.steps:
        assert step.charge_kw == 0.0 or step.discharge_kw == 0.0
