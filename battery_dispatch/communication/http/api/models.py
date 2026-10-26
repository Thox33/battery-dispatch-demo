"""Request and response models of the HTTP API."""

from datetime import UTC, datetime, timedelta
from typing import ClassVar, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from battery_dispatch.optimization.battery import BatteryParameters
from battery_dispatch.optimization.schedule import Schedule


class TimeRange(BaseModel):
    """Half-open time range `[start, end)`. Both ends need a timezone and are stored as UTC."""

    max_span: ClassVar[timedelta] = timedelta(days=366)

    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        self.start = self.start.astimezone(UTC)
        self.end = self.end.astimezone(UTC)
        if self.start >= self.end:
            raise ValueError("start must be before end")
        if self.end - self.start > self.max_span:
            raise ValueError(f"time range must not exceed {_describe(self.max_span)}")
        return self


def _describe(span: timedelta) -> str:
    """Describe a span in whole days and hours, for example "31 days and 1 hour"."""
    hours = span // timedelta(hours=1)
    days, hours = divmod(hours, 24)
    parts = [
        f"{n} {unit}{'' if n == 1 else 's'}" for n, unit in ((days, "day"), (hours, "hour")) if n
    ]
    return " and ".join(parts)


class PriceImportRequest(TimeRange):
    # Every week in the range is one request to SMARD.
    max_span: ClassVar[timedelta] = timedelta(days=92)


class PriceImportResponse(BaseModel):
    start: datetime
    end: datetime
    fetched: int
    written: int


class PricePointResponse(BaseModel):
    time: datetime
    price_eur_per_mwh: float


class PriceSeriesResponse(BaseModel):
    bidding_zone: str
    unit: Literal["EUR/MWh"] = "EUR/MWh"
    prices: list[PricePointResponse]


class BatteryRequest(BaseModel):
    """Battery parameters. Power in kW at the grid connection, state of charge as fraction."""

    model_config = ConfigDict(allow_inf_nan=False)

    # The bounds keep the model within the numerical range of the solver: from a small
    # home battery to a grid-scale plant, and efficiencies a real battery reaches.
    capacity_kwh: float = Field(ge=0.1, le=10_000_000)
    max_charge_kw: float = Field(ge=0.1, le=10_000_000)
    max_discharge_kw: float = Field(ge=0.1, le=10_000_000)
    charge_efficiency: float = Field(ge=0.5, le=1)
    discharge_efficiency: float = Field(ge=0.5, le=1)
    soc_min: float = Field(ge=0, le=1)
    soc_max: float = Field(ge=0, le=1)
    soc_initial: float = Field(ge=0, le=1)
    degradation_cost_eur_per_mwh: float = Field(default=0.0, ge=0, le=10_000)

    @model_validator(mode="after")
    def _check_soc(self) -> Self:
        if self.soc_min >= self.soc_max:
            raise ValueError("soc_min must be below soc_max")
        if not self.soc_min <= self.soc_initial <= self.soc_max:
            raise ValueError("soc_initial must lie between soc_min and soc_max")
        return self

    def to_parameters(self) -> BatteryParameters:
        return BatteryParameters(**self.model_dump())


class DispatchRequest(TimeRange):
    """Time range on quarter-hour boundaries and the battery to plan for."""

    # 31 days plus the extra hour of the day when summer time ends, so that every
    # calendar month in Europe/Berlin fits.
    max_span: ClassVar[timedelta] = timedelta(days=31, hours=1)

    battery: BatteryRequest

    @model_validator(mode="after")
    def _check_quarter_hours(self) -> Self:
        for value in (self.start.astimezone(UTC), self.end.astimezone(UTC)):
            if value.minute % 15 or value.second or value.microsecond:
                raise ValueError("start and end must lie on quarter-hour boundaries")
        return self


class SolverInfo(BaseModel):
    status: str
    runtime_ms: int


class ScheduleStepResponse(BaseModel):
    time: datetime
    price_eur_per_mwh: float
    charge_kw: float
    discharge_kw: float
    soc_kwh: float


class DispatchResponse(BaseModel):
    start: datetime
    end: datetime
    bidding_zone: str
    revenue_eur: float
    degradation_cost_eur: float
    charged_kwh: float
    discharged_kwh: float
    equivalent_full_cycles: float
    solver: SolverInfo
    schedule: list[ScheduleStepResponse]

    @classmethod
    def from_schedule(
        cls, start: datetime, end: datetime, bidding_zone: str, schedule: Schedule
    ) -> Self:
        return cls(
            start=start,
            end=end,
            bidding_zone=bidding_zone,
            revenue_eur=schedule.revenue_eur,
            degradation_cost_eur=schedule.degradation_cost_eur,
            charged_kwh=schedule.charged_kwh,
            discharged_kwh=schedule.discharged_kwh,
            equivalent_full_cycles=schedule.equivalent_full_cycles,
            solver=SolverInfo(status=schedule.solver_status, runtime_ms=schedule.runtime_ms),
            schedule=[
                ScheduleStepResponse(
                    time=s.time,
                    price_eur_per_mwh=s.price_eur_per_mwh,
                    charge_kw=s.charge_kw,
                    discharge_kw=s.discharge_kw,
                    soc_kwh=s.soc_kwh,
                )
                for s in schedule.steps
            ],
        )


class PricesIncompleteDetail(BaseModel):
    message: str
    expected: int
    found: int
    first_missing: datetime


class PricesIncompleteResponse(BaseModel):
    detail: PricesIncompleteDetail
