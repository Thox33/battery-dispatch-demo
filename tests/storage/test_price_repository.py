from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete

from battery_dispatch.config.config_manager import DatabaseConfig
from battery_dispatch.market_data.models import PricePoint
from battery_dispatch.storage.repositories.price_repository import PriceRepository
from battery_dispatch.storage.repositories.schemas.price_schema import day_ahead_prices
from battery_dispatch.storage.storage_manager import StorageManager


pytestmark = pytest.mark.integration

ZONE = "TEST-A"
OTHER_ZONE = "TEST-B"
START = datetime(2026, 10, 26, tzinfo=UTC)
QUARTER = timedelta(minutes=15)


def day(prices: list[float]) -> list[PricePoint]:
    return [
        PricePoint(time=START + i * QUARTER, price_eur_per_mwh=price)
        for i, price in enumerate(prices)
    ]


async def _clean(storage: StorageManager) -> None:
    async with storage.session() as session, session.begin():
        await session.execute(
            delete(day_ahead_prices).where(day_ahead_prices.c.bidding_zone.like("TEST-%"))
        )


@pytest.fixture
async def repository(database_config: DatabaseConfig) -> AsyncGenerator[PriceRepository]:
    storage = StorageManager(database_config)
    await storage.start()
    await _clean(storage)
    yield PriceRepository(storage)
    await _clean(storage)
    await storage.stop()


async def test_inserts_and_reads_back_in_order(repository: PriceRepository) -> None:
    points = day([30.0, 25.0, 40.0])

    written = await repository.upsert(ZONE, list(reversed(points)))

    assert written == 3
    assert await repository.list_range(ZONE, START, START + timedelta(days=1)) == points


async def test_repeated_upsert_writes_nothing(repository: PriceRepository) -> None:
    points = day([30.0, 25.0, 40.0])
    await repository.upsert(ZONE, points)

    written = await repository.upsert(ZONE, points)

    assert written == 0
    assert len(await repository.list_range(ZONE, START, START + timedelta(days=1))) == 3


async def test_changed_price_is_updated(repository: PriceRepository) -> None:
    await repository.upsert(ZONE, day([30.0, 25.0]))

    written = await repository.upsert(ZONE, day([30.0, 26.5]))

    assert written == 1
    stored = await repository.list_range(ZONE, START, START + timedelta(days=1))
    assert [p.price_eur_per_mwh for p in stored] == [30.0, 26.5]


async def test_negative_prices_are_stored(repository: PriceRepository) -> None:
    await repository.upsert(ZONE, day([-120.5, 0.0]))

    stored = await repository.list_range(ZONE, START, START + timedelta(days=1))

    assert [p.price_eur_per_mwh for p in stored] == [-120.5, 0.0]


async def test_range_end_is_exclusive(repository: PriceRepository) -> None:
    await repository.upsert(ZONE, day([1.0, 2.0, 3.0]))

    stored = await repository.list_range(ZONE, START, START + 2 * QUARTER)

    assert [p.price_eur_per_mwh for p in stored] == [1.0, 2.0]


async def test_bidding_zones_are_separate(repository: PriceRepository) -> None:
    await repository.upsert(ZONE, day([1.0]))
    await repository.upsert(OTHER_ZONE, day([2.0]))

    stored = await repository.list_range(OTHER_ZONE, START, START + QUARTER)

    assert [p.price_eur_per_mwh for p in stored] == [2.0]


async def test_returned_times_are_utc(repository: PriceRepository) -> None:
    await repository.upsert(ZONE, day([1.0]))

    stored = await repository.list_range(ZONE, START, START + QUARTER)

    assert stored[0].time == START
    assert stored[0].time.utcoffset() == timedelta(0)
