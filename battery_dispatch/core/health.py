"""Health model shared by components, controller and the /health endpoint."""

from enum import StrEnum

from pydantic import BaseModel


class HealthState(StrEnum):
    OK = "ok"
    DOWN = "down"


class ComponentHealth(BaseModel):
    name: str
    state: HealthState
    detail: str | None = None


class SystemHealth(BaseModel):
    state: HealthState
    version: str
    components: list[ComponentHealth]
