"""Common lifecycle interface for the parts of the application."""

from abc import ABC, abstractmethod

from battery_dispatch.core.health import ComponentHealth


class ComponentBase(ABC):
    """A part of the application with an explicit start, stop and health check.

    The controller starts components in registration order and stops them in reverse
    order. `health` must not raise; failures are reported as `HealthState.DOWN`.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def health(self) -> ComponentHealth: ...
