import pytest

from battery_dispatch.config.config_manager import AppConfig
from battery_dispatch.core.controller import Controller
from battery_dispatch.core.health import HealthState
from tests.fakes import FakeComponent, RaisingHealthComponent


def make_controller(*components: FakeComponent) -> Controller:
    controller = Controller(AppConfig())
    controller.components = list(components)
    return controller


async def test_starts_in_order_and_stops_in_reverse() -> None:
    events: list[str] = []
    controller = make_controller(FakeComponent("a", events), FakeComponent("b", events))

    async with controller.running():
        events.append("running")

    assert events == ["start a", "start b", "running", "stop b", "stop a"]


async def test_failed_start_stops_already_started_components() -> None:
    events: list[str] = []
    controller = make_controller(
        FakeComponent("a", events),
        FakeComponent("b", events, fail_on_start=True),
        FakeComponent("c", events),
    )

    with pytest.raises(RuntimeError, match="b cannot start"):
        await controller.start()

    assert events == ["start a", "stop a"]


async def test_health_is_ok_when_all_components_are_ok() -> None:
    controller = make_controller(FakeComponent("a"), FakeComponent("b"))

    health = await controller.health()

    assert health.state is HealthState.OK
    assert [c.name for c in health.components] == ["a", "b"]


async def test_health_is_down_when_one_component_is_down() -> None:
    controller = make_controller(FakeComponent("a"), FakeComponent("b", state=HealthState.DOWN))

    health = await controller.health()

    assert health.state is HealthState.DOWN


async def test_raising_health_check_counts_as_down() -> None:
    controller = make_controller(RaisingHealthComponent("a"))

    health = await controller.health()

    assert health.state is HealthState.DOWN
    assert health.components[0].detail == "ValueError"
