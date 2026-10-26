from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pytest

from battery_dispatch.config.config_manager import SmardConfig
from battery_dispatch.market_data.models import PricePoint
from battery_dispatch.market_data.smard_client import SmardClient, SmardError, packages_for_range


QUARTER = timedelta(minutes=15)
# Two consecutive weekly packages as SMARD publishes them: Monday 00:00 in Europe/Berlin.
# The first week ends with the change from summer to winter time.
WEEK_A = datetime(2026, 10, 18, 22, tzinfo=UTC)
WEEK_B = datetime(2026, 10, 25, 23, tzinfo=UTC)
INDEX_PATH = "/4169/DE/index_quarterhour.json"


def ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def package_path(start: datetime) -> str:
    return f"/4169/DE/4169_DE_quarterhour_{ms(start)}.json"


SMARD_DATA: dict[str, Any] = {
    INDEX_PATH: {"timestamps": [ms(WEEK_B), ms(WEEK_A)]},
    package_path(WEEK_A): {
        "meta_data": {"version": 1},
        "series": [[ms(WEEK_A), 10.0], [ms(WEEK_A + QUARTER), -5.5]],
    },
    package_path(WEEK_B): {
        "meta_data": {"version": 1},
        "series": [[ms(WEEK_B), 20.0], [ms(WEEK_B + QUARTER), None]],
    },
}


def make_client(
    handler: Callable[[httpx2.Request], httpx2.Response], requested: list[str]
) -> SmardClient:
    def recording_handler(request: httpx2.Request) -> httpx2.Response:
        requested.append(request.url.path)
        return handler(request)

    return SmardClient(
        SmardConfig(base_url="https://smard.test"),
        transport=httpx2.MockTransport(recording_handler),
    )


def serve(data: dict[str, Any]) -> Callable[[httpx2.Request], httpx2.Response]:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path not in data:
            return httpx2.Response(404)
        return httpx2.Response(200, json=data[request.url.path])

    return handler


@pytest.fixture
def requested() -> list[str]:
    return []


@pytest.fixture
async def client(requested: list[str]) -> AsyncGenerator[SmardClient]:
    smard = make_client(serve(SMARD_DATA), requested)
    await smard.start()
    yield smard
    await smard.stop()


class TestPackagesForRange:
    index = [ms(WEEK_A), ms(WEEK_B), ms(WEEK_B + timedelta(days=7))]

    def test_range_inside_one_package(self) -> None:
        start = WEEK_B + timedelta(days=1)
        assert packages_for_range(self.index, start, start + timedelta(hours=1)) == [ms(WEEK_B)]

    def test_range_across_package_boundary(self) -> None:
        packages = packages_for_range(self.index, WEEK_B - QUARTER, WEEK_B + QUARTER)
        assert packages == [ms(WEEK_A), ms(WEEK_B)]

    def test_end_is_exclusive(self) -> None:
        assert packages_for_range(self.index, WEEK_A, WEEK_B) == [ms(WEEK_A)]

    def test_last_package_is_open_ended(self) -> None:
        start = WEEK_B + timedelta(days=9)
        packages = packages_for_range(self.index, start, start + timedelta(days=1))
        assert packages == [ms(WEEK_B + timedelta(days=7))]

    def test_range_before_first_package(self) -> None:
        start = WEEK_A - timedelta(days=2)
        assert packages_for_range(self.index, start, start + timedelta(days=1)) == []


async def test_returns_points_within_half_open_range(client: SmardClient) -> None:
    points = await client.fetch_prices(WEEK_A + QUARTER, WEEK_B + QUARTER)

    assert points == [
        PricePoint(time=WEEK_A + QUARTER, price_eur_per_mwh=-5.5),
        PricePoint(time=WEEK_B, price_eur_per_mwh=20.0),
    ]


async def test_skips_values_not_published_yet(client: SmardClient) -> None:
    points = await client.fetch_prices(WEEK_B, WEEK_B + timedelta(days=1))

    assert [p.time for p in points] == [WEEK_B]


async def test_requests_only_needed_packages(client: SmardClient, requested: list[str]) -> None:
    await client.fetch_prices(WEEK_B, WEEK_B + timedelta(hours=1))

    assert requested == [INDEX_PATH, package_path(WEEK_B)]


async def test_times_are_utc(client: SmardClient) -> None:
    points = await client.fetch_prices(WEEK_A, WEEK_A + QUARTER)

    assert points[0].time.tzinfo is UTC


async def test_http_error_raises_smard_error(requested: list[str]) -> None:
    smard = make_client(lambda _request: httpx2.Response(503), requested)
    await smard.start()
    try:
        with pytest.raises(SmardError):
            await smard.fetch_prices(WEEK_A, WEEK_B)
    finally:
        await smard.stop()


async def test_unexpected_format_raises_smard_error(requested: list[str]) -> None:
    data = {**SMARD_DATA, package_path(WEEK_A): {"series": [["not a timestamp", 1.0]]}}
    smard = make_client(serve(data), requested)
    await smard.start()
    try:
        with pytest.raises(SmardError, match="unexpected format"):
            await smard.fetch_prices(WEEK_A, WEEK_A + QUARTER)
    finally:
        await smard.stop()


async def test_fetch_before_start_raises() -> None:
    smard = SmardClient(SmardConfig())

    with pytest.raises(RuntimeError, match="not started"):
        await smard.fetch_prices(WEEK_A, WEEK_B)
