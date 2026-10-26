"""Battery parameters, the input of the dispatch optimisation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BatteryParameters:
    """Technical and economic parameters of a battery.

    Power is measured at the grid connection. The efficiencies apply on the way into and
    out of the battery, so charging 1 kWh from the grid stores `charge_efficiency` kWh and
    delivering 1 kWh to the grid takes `1 / discharge_efficiency` kWh from storage.
    State-of-charge values are fractions of `capacity_kwh`.
    """

    capacity_kwh: float
    max_charge_kw: float
    max_discharge_kw: float
    charge_efficiency: float
    discharge_efficiency: float
    soc_min: float
    soc_max: float
    soc_initial: float
    degradation_cost_eur_per_mwh: float = 0.0

    @property
    def min_energy_kwh(self) -> float:
        return self.soc_min * self.capacity_kwh

    @property
    def max_energy_kwh(self) -> float:
        return self.soc_max * self.capacity_kwh

    @property
    def initial_energy_kwh(self) -> float:
        return self.soc_initial * self.capacity_kwh

    @property
    def usable_energy_kwh(self) -> float:
        """Energy between the state-of-charge limits, the basis of one full cycle."""
        return self.max_energy_kwh - self.min_energy_kwh
