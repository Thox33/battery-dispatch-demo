"""Domain types for market prices."""

from dataclasses import dataclass
from datetime import datetime


BIDDING_ZONE_DE_LU = "DE-LU"


@dataclass(frozen=True, slots=True)
class PricePoint:
    """Day-ahead price for one quarter hour.

    `time` is the start of the quarter hour, timezone-aware, in UTC.
    """

    time: datetime
    price_eur_per_mwh: float


@dataclass(frozen=True, slots=True)
class ImportResult:
    fetched: int
    written: int
