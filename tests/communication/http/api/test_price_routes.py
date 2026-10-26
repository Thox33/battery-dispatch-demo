from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from battery_dispatch.communication.http.dependencies import (
    get_price_importer,
    get_price_repository,
)
from battery_dispatch.communication.http.server import create_app
from battery_dispatch.config.config_manager import AppConfig
from battery_dispatch.core.controller import Controller
from battery_dispatch.market_data.models import ImportResult, PricePoint
from tests.fakes import FakeComponent, FakePriceImporter, FakePriceRepository


START = datetime(2026, 10, 26, tzinfo=UTC)


@pytest.fixture
def importer() -> FakePriceImporter:
    return FakePriceImporter(ImportResult(fetched=96, written=96))


@pytest.fixture
def repository() -> FakePriceRepository:
    return FakePriceRepository([PricePoint(time=START, price_eur_per_mwh=-12.5)])


@pytest.fixture
def client(importer: FakePriceImporter, repository: FakePriceRepository) -> Generator[TestClient]:
    controller = Controller(AppConfig())
    controller.components = [FakeComponent("storage")]
    app = create_app(controller)
    app.dependency_overrides[get_price_importer] = lambda: importer
    app.dependency_overrides[get_price_repository] = lambda: repository
    with TestClient(app) as test_client:
        yield test_client


def test_import_returns_counts(client: TestClient, importer: FakePriceImporter) -> None:
    response = client.post(
        "/prices/import",
        json={"start": "2026-10-26T00:00:00+01:00", "end": "2026-10-27T00:00:00+01:00"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "start": "2026-10-25T23:00:00Z",
        "end": "2026-10-26T23:00:00Z",
        "fetched": 96,
        "written": 96,
    }
    assert importer.requests == [
        (datetime(2026, 10, 25, 23, tzinfo=UTC), datetime(2026, 10, 26, 23, tzinfo=UTC))
    ]


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"start": "2026-10-26T00:00:00", "end": "2026-10-27T00:00:00"}, id="naive"),
        pytest.param(
            {"start": "2026-10-27T00:00:00Z", "end": "2026-10-26T00:00:00Z"}, id="reversed"
        ),
        pytest.param({"start": "2026-01-01T00:00:00Z", "end": "2026-06-01T00:00:00Z"}, id="long"),
    ],
)
def test_import_rejects_invalid_range(
    client: TestClient, importer: FakePriceImporter, body: dict[str, str]
) -> None:
    response = client.post("/prices/import", json=body)

    assert response.status_code == 422
    assert importer.requests == []


def test_import_smard_failure_returns_502(client: TestClient, importer: FakePriceImporter) -> None:
    importer.fail = True

    response = client.post(
        "/prices/import", json={"start": "2026-10-26T00:00:00Z", "end": "2026-10-27T00:00:00Z"}
    )

    assert response.status_code == 502


def test_get_prices(client: TestClient, repository: FakePriceRepository) -> None:
    response = client.get(
        "/prices", params={"start": "2026-10-26T00:00:00Z", "end": "2026-10-27T00:00:00Z"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "bidding_zone": "DE-LU",
        "unit": "EUR/MWh",
        "prices": [{"time": "2026-10-26T00:00:00Z", "price_eur_per_mwh": -12.5}],
    }
    assert repository.queries == [("DE-LU", START, datetime(2026, 10, 27, tzinfo=UTC))]


def test_get_prices_rejects_naive_datetimes(client: TestClient) -> None:
    response = client.get(
        "/prices", params={"start": "2026-10-26T00:00:00", "end": "2026-10-27T00:00:00"}
    )

    assert response.status_code == 422
