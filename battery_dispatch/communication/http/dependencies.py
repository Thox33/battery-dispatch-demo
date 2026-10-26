"""FastAPI dependencies that give routes access to the controller and its parts."""

from typing import Annotated

from fastapi import Depends, Request

from battery_dispatch.core.controller import Controller
from battery_dispatch.market_data.price_importer import PriceImporter
from battery_dispatch.storage.repositories.price_repository import PriceRepository


def get_controller(request: Request) -> Controller:
    controller: Controller = request.app.state.controller
    return controller


def get_price_importer(controller: Annotated[Controller, Depends(get_controller)]) -> PriceImporter:
    return controller.price_importer


def get_price_repository(
    controller: Annotated[Controller, Depends(get_controller)],
) -> PriceRepository:
    return controller.prices
