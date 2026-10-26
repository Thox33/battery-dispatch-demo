"""Builds the FastAPI application around a controller."""

import logging
import math
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from battery_dispatch import __version__
from battery_dispatch.communication.http.api import dispatch_routes, health_routes, price_routes
from battery_dispatch.core.controller import Controller
from battery_dispatch.storage.errors import StorageUnavailableError


logger = logging.getLogger(__name__)

# Static web page that calls the API from the browser.
FRONTEND_DIR = Path(__file__).parent / "frontend"


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
    app.include_router(dispatch_routes.router)
    app.add_api_route("/", _redirect_to_ui, methods=["GET"], include_in_schema=False)
    app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="ui")
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(SQLAlchemyError, _database_error)
    app.add_exception_handler(StorageUnavailableError, _database_error)
    return app


async def _redirect_to_ui() -> RedirectResponse:
    return RedirectResponse("/ui/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


async def _validation_error(_request: Request, exc: Exception) -> JSONResponse:
    # Same body as the FastAPI default, but rejected inputs such as Infinity or NaN are
    # sent back as strings, since JSON has no representation for them.
    errors: Sequence[Any] = exc.errors() if isinstance(exc, RequestValidationError) else []
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": _finite(jsonable_encoder(errors))},
    )


def _finite(value: object) -> object:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _finite(item) for key, item in cast(dict[object, object], value).items()}
    if isinstance(value, list):
        return [_finite(item) for item in cast(list[object], value)]
    return value


async def _database_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.error("Database error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "database unavailable"},
    )
