"""Test doubles shared across test modules."""

from battery_dispatch.core.component_base import ComponentBase
from battery_dispatch.core.health import ComponentHealth, HealthState


class FakeComponent(ComponentBase):
    def __init__(
        self,
        name: str,
        events: list[str] | None = None,
        state: HealthState = HealthState.OK,
        fail_on_start: bool = False,
    ) -> None:
        super().__init__(name)
        self.events = events if events is not None else []
        self.state = state
        self.fail_on_start = fail_on_start

    async def start(self) -> None:
        if self.fail_on_start:
            raise RuntimeError(f"{self.name} cannot start")
        self.events.append(f"start {self.name}")

    async def stop(self) -> None:
        self.events.append(f"stop {self.name}")

    async def health(self) -> ComponentHealth:
        return ComponentHealth(name=self.name, state=self.state)


class RaisingHealthComponent(FakeComponent):
    async def health(self) -> ComponentHealth:
        raise ValueError("broken")
