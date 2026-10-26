"""Revenue-maximising battery schedule as a mixed-integer linear program.

Per quarter hour `t` the model has charge power `c_t`, discharge power `d_t` (kW, at the
grid connection), stored energy `e_t` (kWh, end of step) and a binary `u_t` that allows
either charging or discharging:

    e_t = e_(t-1) + charge_efficiency * c_t * dt - d_t * dt / discharge_efficiency
    c_t <= max_charge_kw * u_t
    d_t <= max_discharge_kw * (1 - u_t)
    e_T >= e_0

The objective is the market revenue minus the degradation cost of discharged energy.
Without the binary, negative prices would make charging and discharging in the same
step profitable, since the efficiency losses then destroy energy the market pays to take.
See docs/decisions/0003-milp-for-battery-dispatch.md.

PuLP ships without type information. Expressions are therefore built from explicit
coefficient lists instead of operator overloading, which keeps them typed.
"""

import time
from collections.abc import Sequence

import pulp  # pyright: ignore[reportMissingTypeStubs]

from battery_dispatch.market_data.models import PricePoint
from battery_dispatch.optimization.battery import BatteryParameters
from battery_dispatch.optimization.schedule import Schedule, ScheduleStep


STEP_HOURS = 0.25
KWH_PER_MWH = 1000.0
# Solver results closer to zero than this are treated as zero.
ZERO_TOLERANCE = 1e-6

STATUS_OPTIMAL = "optimal"

type _Terms = list[tuple[pulp.LpVariable, float]]


class OptimizationError(Exception):
    """The solver did not return a proven optimal schedule."""


def optimize(
    prices: Sequence[PricePoint],
    battery: BatteryParameters,
    *,
    time_limit_s: float,
    mip_gap_rel: float,
) -> Schedule:
    """Compute the revenue-maximising schedule for consecutive quarter-hour prices.

    Runs the CBC solver bundled with PuLP in a subprocess and blocks until it returns.
    The result is optimal within the relative gap `mip_gap_rel`: its objective is proven
    to be at most that fraction below the best possible one. Raises `OptimizationError`
    if the solver fails or stops before reaching that proof, for example at the time
    limit.
    """
    if not prices:
        raise ValueError("at least one price is required")

    steps = range(len(prices))
    charge = [pulp.LpVariable(f"charge_{t}", 0.0, battery.max_charge_kw) for t in steps]
    discharge = [pulp.LpVariable(f"discharge_{t}", 0.0, battery.max_discharge_kw) for t in steps]
    energy = [
        pulp.LpVariable(f"energy_{t}", battery.min_energy_kwh, battery.max_energy_kwh)
        for t in steps
    ]
    charging = [pulp.LpVariable(f"charging_{t}", cat=pulp.LpBinary) for t in steps]

    problem = pulp.LpProblem("battery_dispatch", pulp.LpMaximize)

    degradation_eur_per_kwh = battery.degradation_cost_eur_per_mwh / KWH_PER_MWH
    objective: _Terms = []
    for t in steps:
        price_eur_per_kwh = prices[t].price_eur_per_mwh / KWH_PER_MWH
        objective.append((charge[t], -price_eur_per_kwh * STEP_HOURS))
        objective.append((discharge[t], (price_eur_per_kwh - degradation_eur_per_kwh) * STEP_HOURS))
    problem += pulp.LpAffineExpression(objective)

    for t in steps:
        # e_t - e_(t-1) - charge_efficiency * dt * c_t + dt / discharge_efficiency * d_t = 0
        balance: _Terms = [
            (energy[t], 1.0),
            (charge[t], -battery.charge_efficiency * STEP_HOURS),
            (discharge[t], STEP_HOURS / battery.discharge_efficiency),
        ]
        if t == 0:
            balance_rhs = battery.initial_energy_kwh
        else:
            balance.append((energy[t - 1], -1.0))
            balance_rhs = 0.0
        problem += _constraint(f"balance_{t}", balance, pulp.LpConstraintEQ, balance_rhs)
        problem += _constraint(
            f"charge_only_{t}",
            [(charge[t], 1.0), (charging[t], -battery.max_charge_kw)],
            pulp.LpConstraintLE,
            0.0,
        )
        problem += _constraint(
            f"discharge_only_{t}",
            [(discharge[t], 1.0), (charging[t], battery.max_discharge_kw)],
            pulp.LpConstraintLE,
            battery.max_discharge_kw,
        )
    problem += _constraint(
        "final_energy", [(energy[-1], 1.0)], pulp.LpConstraintGE, battery.initial_energy_kwh
    )

    started = time.perf_counter()
    _solve(problem, time_limit_s, mip_gap_rel)
    runtime_ms = round((time.perf_counter() - started) * 1000)

    schedule_steps = [
        ScheduleStep(
            time=prices[t].time,
            price_eur_per_mwh=prices[t].price_eur_per_mwh,
            charge_kw=_value(charge[t]),
            discharge_kw=_value(discharge[t]),
            soc_kwh=_value(energy[t]),
        )
        for t in steps
    ]
    return _summarise(schedule_steps, battery, runtime_ms)


def _summarise(steps: list[ScheduleStep], battery: BatteryParameters, runtime_ms: int) -> Schedule:
    # Figures come from the cleaned schedule, not from the solver's objective value.
    charged_kwh = sum(s.charge_kw for s in steps) * STEP_HOURS
    discharged_kwh = sum(s.discharge_kw for s in steps) * STEP_HOURS
    revenue_eur = sum(
        s.price_eur_per_mwh / KWH_PER_MWH * (s.discharge_kw - s.charge_kw) * STEP_HOURS
        for s in steps
    )
    return Schedule(
        steps=steps,
        revenue_eur=revenue_eur,
        degradation_cost_eur=battery.degradation_cost_eur_per_mwh / KWH_PER_MWH * discharged_kwh,
        charged_kwh=charged_kwh,
        discharged_kwh=discharged_kwh,
        equivalent_full_cycles=discharged_kwh / battery.usable_energy_kwh,
        solver_status=STATUS_OPTIMAL,
        runtime_ms=runtime_ms,
    )


def _constraint(name: str, terms: _Terms, sense: int, rhs: float) -> pulp.LpConstraint:
    return pulp.LpConstraint(pulp.LpAffineExpression(terms), sense, name, rhs)


def _solve(problem: pulp.LpProblem, time_limit_s: float, mip_gap_rel: float) -> None:
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_s, gapRel=mip_gap_rel)
    try:
        problem.solve(solver)  # pyright: ignore[reportUnknownMemberType]
    except pulp.PulpSolverError as exc:
        raise OptimizationError(f"solver failed: {exc}") from exc
    # CBC reports a run stopped at the time limit with a feasible solution as status
    # "Optimal"; only the solution status tells whether optimality was proven. A run that
    # stops because the gap is reached counts as optimal in both.
    sol_status = int(problem.sol_status)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    if sol_status != pulp.LpSolutionOptimal:
        raise OptimizationError(
            f"solver stopped without an optimal solution: {pulp.LpSolution.get(sol_status)}"
        )


def _value(variable: pulp.LpVariable) -> float:
    value = variable.value()
    if value is None:
        raise OptimizationError(f"solver returned no value for {variable.name}")
    value = float(value)
    return 0.0 if abs(value) < ZERO_TOLERANCE else value
