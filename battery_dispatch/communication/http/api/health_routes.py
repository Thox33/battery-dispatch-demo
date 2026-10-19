from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from battery_dispatch.communication.http.dependencies import get_controller
from battery_dispatch.core.controller import Controller
from battery_dispatch.core.health import HealthState, SystemHealth


router = APIRouter(tags=["health"])


@router.get(
    "/health",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": SystemHealth}},
)
async def get_health(
    response: Response,
    controller: Annotated[Controller, Depends(get_controller)],
) -> SystemHealth:
    health = await controller.health()
    if health.state is not HealthState.OK:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return health
