from fastapi.testclient import TestClient

from battery_dispatch import __version__
from battery_dispatch.communication.http.server import create_app
from battery_dispatch.config.config_manager import AppConfig
from battery_dispatch.core.controller import Controller
from battery_dispatch.core.health import HealthState
from tests.fakes import FakeComponent


def make_client(state: HealthState) -> TestClient:
    controller = Controller(AppConfig())
    controller.components = [FakeComponent("storage", state=state)]
    return TestClient(create_app(controller))


def test_health_ok() -> None:
    with make_client(HealthState.OK) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "state": "ok",
        "version": __version__,
        "components": [{"name": "storage", "state": "ok", "detail": None}],
    }


def test_health_down_returns_503() -> None:
    with make_client(HealthState.DOWN) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["state"] == "down"
