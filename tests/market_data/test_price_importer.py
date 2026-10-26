from datetime import UTC, datetime, timedelta

from battery_dispatch.market_data.models import BIDDING_ZONE_DE_LU, ImportResult, PricePoint
from battery_dispatch.market_data.price_importer import PriceImporter
from tests.fakes import FakePriceRepository, FakeSmardClient


START = datetime(2026, 10, 26, tzinfo=UTC)
END = START + timedelta(days=1)


async def test_stores_fetched_prices_for_the_bidding_zone() -> None:
    points = [PricePoint(time=START, price_eur_per_mwh=42.0)]
    client = FakeSmardClient(points)
    repository = FakePriceRepository()

    result = await PriceImporter(client, repository).import_range(START, END)

    assert client.requests == [(START, END)]
    assert repository.upserts == [(BIDDING_ZONE_DE_LU, points)]
    assert result == ImportResult(fetched=1, written=1)


async def test_empty_fetch_writes_nothing() -> None:
    repository = FakePriceRepository()

    result = await PriceImporter(FakeSmardClient([]), repository).import_range(START, END)

    assert result == ImportResult(fetched=0, written=0)
