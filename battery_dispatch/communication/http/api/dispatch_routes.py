import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from battery_dispatch.communication.http.api.models import (
    DispatchRequest,
    DispatchResponse,
    PricesIncompleteDetail,
    PricesIncompleteResponse,
)
from battery_dispatch.communication.http.dependencies import get_dispatch_planner
from battery_dispatch.market_data.models import BIDDING_ZONE_DE_LU
from battery_dispatch.optimization.dispatch_planner import DispatchPlanner, PricesIncompleteError
from battery_dispatch.optimization.milp_optimizer import OptimizationError


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


@router.post(
    "/optimize",
    responses={
        status.HTTP_409_CONFLICT: {
            "model": PricesIncompleteResponse,
            "description": "Prices for the range are incomplete; import them first",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "The solver did not reach an optimal solution"
        },
    },
)
async def optimize_dispatch(
    request: DispatchRequest,
    planner: Annotated[DispatchPlanner, Depends(get_dispatch_planner)],
) -> DispatchResponse:
    """Compute the revenue-maximising schedule for `[start, end)` from the stored prices."""
    try:
        schedule = await planner.plan(request.start, request.end, request.battery.to_parameters())
    except PricesIncompleteError as exc:
        detail = PricesIncompleteDetail(
            message="prices for the range are incomplete, import them first",
            expected=exc.expected,
            found=exc.found,
            first_missing=exc.first_missing,
        )
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=detail.model_dump(mode="json")
        ) from exc
    except OptimizationError as exc:
        logger.error("Optimisation failed: %s", exc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return DispatchResponse.from_schedule(request.start, request.end, BIDDING_ZONE_DE_LU, schedule)
