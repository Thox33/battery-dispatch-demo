"""Reads and writes day-ahead prices."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, select
from sqlalchemy.dialects.postgresql import insert

from battery_dispatch.market_data.models import PricePoint
from battery_dispatch.storage.repositories.schemas.price_schema import day_ahead_prices
from battery_dispatch.storage.storage_manager import StorageManager


# asyncpg allows at most 32767 bind parameters per statement, three are used per row.
_UPSERT_CHUNK_SIZE = 5000


class PriceRepository:
    def __init__(self, storage: StorageManager) -> None:
        self._storage = storage

    async def upsert(self, bidding_zone: str, points: Sequence[PricePoint]) -> int:
        """Insert new prices and update changed ones.

        Returns the number of rows actually written. Rows that already exist with the same
        price are left untouched, so a repeated import returns 0.
        """
        written = 0
        async with self._storage.session() as session, session.begin():
            for offset in range(0, len(points), _UPSERT_CHUNK_SIZE):
                chunk = points[offset : offset + _UPSERT_CHUNK_SIZE]
                statement = insert(day_ahead_prices).values(
                    [
                        {
                            "bidding_zone": bidding_zone,
                            "time": p.time,
                            "price_eur_per_mwh": p.price_eur_per_mwh,
                        }
                        for p in chunk
                    ]
                )
                statement = statement.on_conflict_do_update(
                    index_elements=[day_ahead_prices.c.bidding_zone, day_ahead_prices.c.time],
                    set_={"price_eur_per_mwh": statement.excluded.price_eur_per_mwh},
                    where=day_ahead_prices.c.price_eur_per_mwh.is_distinct_from(
                        statement.excluded.price_eur_per_mwh
                    ),
                )
                result = cast(CursorResult[Any], await session.execute(statement))
                written += result.rowcount
        return written

    async def list_range(
        self, bidding_zone: str, start: datetime, end: datetime
    ) -> list[PricePoint]:
        """Return prices with `start <= time < end`, ordered by time."""
        statement = (
            select(day_ahead_prices.c.time, day_ahead_prices.c.price_eur_per_mwh)
            .where(
                day_ahead_prices.c.bidding_zone == bidding_zone,
                day_ahead_prices.c.time >= start,
                day_ahead_prices.c.time < end,
            )
            .order_by(day_ahead_prices.c.time)
        )
        async with self._storage.session() as session:
            rows = (await session.execute(statement)).all()
        return [PricePoint(time=row.time, price_eur_per_mwh=row.price_eur_per_mwh) for row in rows]
