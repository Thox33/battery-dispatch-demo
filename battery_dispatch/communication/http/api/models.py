"""Request and response models of the HTTP API."""

from datetime import UTC, datetime, timedelta
from typing import ClassVar, Literal, Self

from pydantic import AwareDatetime, BaseModel, model_validator


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
            raise ValueError(f"time range must not exceed {self.max_span.days} days")
        return self


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
