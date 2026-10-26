"""Builds the FastAPI application around a controller."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from battery_dispatch import __version__
from battery_dispatch.communication.http.api import health_routes, price_routes
from battery_dispatch.core.controller import Controller


logger = logging.getLogger(__name__)


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
    app.include_router(price_routes.router)
    app.add_exception_handler(SQLAlchemyError, _database_error)
    return app


async def _database_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.error("Database error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "database unavailable"},
    )
