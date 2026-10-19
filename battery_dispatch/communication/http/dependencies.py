"""FastAPI dependencies that give routes access to the controller."""

from fastapi import Request

from battery_dispatch.core.controller import Controller


def get_controller(request: Request) -> Controller:
    controller: Controller = request.app.state.controller
    return controller
