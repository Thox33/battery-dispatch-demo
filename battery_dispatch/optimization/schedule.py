"""Result of the dispatch optimisation."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ScheduleStep:
    """Planned operation in one quarter hour.

    `time` is the start of the quarter hour in UTC. Power is measured at the grid
    connection. `soc_kwh` is the energy stored at the end of the quarter hour.
    """

    time: datetime
    price_eur_per_mwh: float
    charge_kw: float
    discharge_kw: float
    soc_kwh: float


@dataclass(frozen=True, slots=True)
class Schedule:
    """Charge and discharge schedule with its key figures.

    `revenue_eur` is the market result: income from discharging minus the cost of
    charging. `degradation_cost_eur` is reported separately and not deducted from it.
    Energy figures are measured at the grid connection.
    """

    steps: list[ScheduleStep]
    revenue_eur: float
    degradation_cost_eur: float
    charged_kwh: float
    discharged_kwh: float
    equivalent_full_cycles: float
    solver_status: str
    runtime_ms: int
