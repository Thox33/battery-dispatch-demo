import json
import math
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from battery_dispatch.communication.http.dependencies import get_dispatch_planner
from battery_dispatch.communication.http.server import create_app
from battery_dispatch.config.config_manager import AppConfig
from battery_dispatch.core.controller import Controller
from battery_dispatch.optimization.battery import BatteryParameters
from battery_dispatch.optimization.dispatch_planner import PricesIncompleteError
from battery_dispatch.optimization.milp_optimizer import OptimizationError
from battery_dispatch.optimization.schedule import Schedule, ScheduleStep
from tests.fakes import FakeComponent, FakeDispatchPlanner


START = datetime(2026, 10, 25, 22, tzinfo=UTC)
QUARTER = timedelta(minutes=15)

BATTERY = {
    "capacity_kwh": 1000,
    "max_charge_kw": 500,
    "max_discharge_kw": 500,
    "charge_efficiency": 0.95,
    "discharge_efficiency": 0.95,
    "soc_min": 0.1,
    "soc_max": 0.9,
    "soc_initial": 0.5,
}

SCHEDULE = Schedule(
    steps=[
        ScheduleStep(
            time=START, price_eur_per_mwh=-5.0, charge_kw=500.0, discharge_kw=0.0, soc_kwh=618.75
        ),
        ScheduleStep(
            time=START + QUARTER,
            price_eur_per_mwh=120.0,
            charge_kw=0.0,
            discharge_kw=451.25,
            soc_kwh=500.0,
        ),
    ],
    revenue_eur=14.16,
    degradation_cost_eur=0.0,
    charged_kwh=125.0,
    discharged_kwh=112.81,
    equivalent_full_cycles=0.14,
    solver_status="optimal",
    runtime_ms=42,
)


def body(battery: dict[str, Any] | None = None, **times: str) -> dict[str, Any]:
    return {
        "start": "2026-10-25T23:00:00+01:00",
        "end": "2026-10-26T00:30:00+01:00",
        "battery": BATTERY if battery is None else battery,
    } | times


@pytest.fixture
def planner() -> FakeDispatchPlanner:
    return FakeDispatchPlanner(SCHEDULE)


@pytest.fixture
def client(planner: FakeDispatchPlanner) -> Generator[TestClient]:
    controller = Controller(AppConfig())
    controller.components = [FakeComponent("storage")]
    app = create_app(controller)
    app.dependency_overrides[get_dispatch_planner] = lambda: planner
    with TestClient(app) as test_client:
        yield test_client


def test_optimize_returns_schedule(client: TestClient, planner: FakeDispatchPlanner) -> None:
    response = client.post("/dispatch/optimize", json=body())

    assert response.status_code == 200
    assert response.json() == {
        "start": "2026-10-25T22:00:00Z",
        "end": "2026-10-25T23:30:00Z",
        "bidding_zone": "DE-LU",
        "revenue_eur": 14.16,
        "degradation_cost_eur": 0.0,
        "charged_kwh": 125.0,
        "discharged_kwh": 112.81,
        "equivalent_full_cycles": 0.14,
        "solver": {"status": "optimal", "runtime_ms": 42},
        "schedule": [
            {
                "time": "2026-10-25T22:00:00Z",
                "price_eur_per_mwh": -5.0,
                "charge_kw": 500.0,
                "discharge_kw": 0.0,
                "soc_kwh": 618.75,
            },
            {
                "time": "2026-10-25T22:15:00Z",
                "price_eur_per_mwh": 120.0,
                "charge_kw": 0.0,
                "discharge_kw": 451.25,
                "soc_kwh": 500.0,
            },
        ],
    }
    assert planner.requests == [
        (
            START,
            START + 6 * QUARTER,
            BatteryParameters(
                capacity_kwh=1000.0,
                max_charge_kw=500.0,
                max_discharge_kw=500.0,
                charge_efficiency=0.95,
                discharge_efficiency=0.95,
                soc_min=0.1,
                soc_max=0.9,
                soc_initial=0.5,
                degradation_cost_eur_per_mwh=0.0,
            ),
        )
    ]


def test_degradation_cost_is_passed_on(client: TestClient, planner: FakeDispatchPlanner) -> None:
    response = client.post(
        "/dispatch/optimize", json=body(BATTERY | {"degradation_cost_eur_per_mwh": 12.5})
    )

    assert response.status_code == 200
    assert planner.requests[0][2].degradation_cost_eur_per_mwh == 12.5


@pytest.mark.parametrize(
    "battery",
    [
        pytest.param({"capacity_kwh": 0.1}, id="smallest capacity"),
        pytest.param({"capacity_kwh": 10_000_000}, id="largest capacity"),
        pytest.param({"max_charge_kw": 0.1, "max_discharge_kw": 0.1}, id="smallest power"),
        pytest.param(
            {"max_charge_kw": 10_000_000, "max_discharge_kw": 10_000_000}, id="largest power"
        ),
        pytest.param({"charge_efficiency": 0.5, "discharge_efficiency": 0.5}, id="efficiency 0.5"),
        pytest.param({"charge_efficiency": 1, "discharge_efficiency": 1}, id="efficiency 1"),
        pytest.param({"soc_min": 0, "soc_max": 1, "soc_initial": 0}, id="full soc range"),
        pytest.param({"degradation_cost_eur_per_mwh": 10_000}, id="highest degradation cost"),
    ],
)
def test_optimize_accepts_boundary_values(
    client: TestClient, planner: FakeDispatchPlanner, battery: dict[str, float]
) -> None:
    response = client.post("/dispatch/optimize", json=body(BATTERY | battery))

    assert response.status_code == 200
    assert len(planner.requests) == 1


def test_optimize_accepts_calendar_month_with_daylight_saving_change(
    client: TestClient, planner: FakeDispatchPlanner
) -> None:
    # 31 days and one hour in Europe/Berlin.
    response = client.post(
        "/dispatch/optimize",
        json=body(start="2026-09-30T00:00:00+02:00", end="2026-10-31T00:00:00+01:00"),
    )

    assert response.status_code == 200
    assert planner.requests[0][1] - planner.requests[0][0] == timedelta(days=31, hours=1)


def _json(request_body: dict[str, Any]) -> str:
    # The standard encoder writes Infinity and NaN, which Python's JSON parser accepts.
    return json.dumps(request_body)


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(
            _json(body(start="2026-10-25T23:00:00", end="2026-10-26T00:00:00")), id="naive range"
        ),
        pytest.param(
            _json(body(start="2026-10-26T00:00:00Z", end="2026-10-25T00:00:00Z")),
            id="reversed range",
        ),
        pytest.param(
            _json(body(start="2026-09-30T00:00:00+02:00", end="2026-10-31T01:00:00+01:00")),
            id="range over 31 days and one hour",
        ),
        pytest.param(_json(body(start="2026-10-25T22:05:00Z")), id="start off quarter hour"),
        pytest.param(_json(body(end="2026-10-25T23:30:30Z")), id="end off quarter hour"),
        pytest.param(_json(body(BATTERY | {"capacity_kwh": 0})), id="capacity zero"),
        pytest.param(_json(body(BATTERY | {"capacity_kwh": 0.09})), id="capacity below minimum"),
        pytest.param(
            _json(body(BATTERY | {"capacity_kwh": 10_000_001})), id="capacity above maximum"
        ),
        pytest.param(_json(body(BATTERY | {"max_charge_kw": 0.09})), id="charge power too low"),
        pytest.param(
            _json(body(BATTERY | {"max_charge_kw": 10_000_001})), id="charge power too high"
        ),
        pytest.param(
            _json(body(BATTERY | {"max_discharge_kw": -1})), id="discharge power negative"
        ),
        pytest.param(
            _json(body(BATTERY | {"max_discharge_kw": 10_000_001})), id="discharge power too high"
        ),
        pytest.param(
            _json(body(BATTERY | {"charge_efficiency": 0.49})), id="charge efficiency too low"
        ),
        pytest.param(
            _json(body(BATTERY | {"discharge_efficiency": 0.49})),
            id="discharge efficiency too low",
        ),
        pytest.param(
            _json(body(BATTERY | {"discharge_efficiency": 1.1})), id="efficiency above one"
        ),
        pytest.param(_json(body(BATTERY | {"soc_min": -0.1})), id="soc_min negative"),
        pytest.param(_json(body(BATTERY | {"soc_max": 1.1})), id="soc_max above one"),
        pytest.param(
            _json(body(BATTERY | {"soc_min": 0.9, "soc_max": 0.9})), id="soc_min not below max"
        ),
        pytest.param(_json(body(BATTERY | {"soc_initial": 0.05})), id="soc_initial below min"),
        pytest.param(_json(body(BATTERY | {"soc_initial": 0.95})), id="soc_initial above max"),
        pytest.param(
            _json(body(BATTERY | {"degradation_cost_eur_per_mwh": -1})), id="degradation negative"
        ),
        pytest.param(
            _json(body(BATTERY | {"degradation_cost_eur_per_mwh": 10_000.01})),
            id="degradation above maximum",
        ),
        pytest.param(
            _json(body({k: v for k, v in BATTERY.items() if k != "capacity_kwh"})),
            id="missing field",
        ),
        pytest.param(_json(body(BATTERY | {"capacity_kwh": math.inf})), id="capacity infinity"),
        pytest.param(_json(body(BATTERY | {"soc_min": math.nan})), id="soc_min nan"),
        pytest.param(
            _json(body(BATTERY | {"degradation_cost_eur_per_mwh": 12.5})).replace("12.5", "1e400"),
            id="degradation overflowing to infinity",
        ),
    ],
)
def test_optimize_rejects_invalid_request(
    client: TestClient, planner: FakeDispatchPlanner, content: str
) -> None:
    response = client.post(
        "/dispatch/optimize", content=content, headers={"content-type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["detail"]
    assert planner.requests == []


def test_incomplete_prices_return_409(client: TestClient, planner: FakeDispatchPlanner) -> None:
    planner.error = PricesIncompleteError(expected=6, found=4, first_missing=START + QUARTER)

    response = client.post("/dispatch/optimize", json=body())

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "message": "prices for the range are incomplete, import them first",
            "expected": 6,
            "found": 4,
            "first_missing": "2026-10-25T22:15:00Z",
        }
    }


def test_solver_failure_returns_500(client: TestClient, planner: FakeDispatchPlanner) -> None:
    planner.error = OptimizationError("solver stopped without an optimal solution: Solution Found")

    response = client.post("/dispatch/optimize", json=body())

    assert response.status_code == 500
    assert "optimal" in response.json()["detail"]


def test_database_error_returns_503(client: TestClient, planner: FakeDispatchPlanner) -> None:
    planner.error = SQLAlchemyError("connection refused")

    response = client.post("/dispatch/optimize", json=body())

    assert response.status_code == 503


def test_too_long_range_names_the_limit(client: TestClient) -> None:
    response = client.post(
        "/dispatch/optimize",
        json=body(start="2026-09-30T00:00:00+02:00", end="2026-10-31T00:15:00+01:00"),
    )

    assert response.status_code == 422
    assert "time range must not exceed 31 days and 1 hour" in response.json()["detail"][0]["msg"]
