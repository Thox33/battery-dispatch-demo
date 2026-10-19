"""Builds the FastAPI application around a controller."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from battery_dispatch import __version__
from battery_dispatch.communication.http.api import health_routes
from battery_dispatch.core.controller import Controller


def create_app(controller: Controller) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        async with controller.running():
            yield

    app = FastAPI(
        title="battery-dispatch-demo",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.controller = controller
    app.include_router(health_routes.router)
    return app
