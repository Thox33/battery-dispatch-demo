from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from battery_dispatch.communication.http.api.models import (
    PriceImportRequest,
    PriceImportResponse,
    PricePointResponse,
    PriceSeriesResponse,
    TimeRange,
)
from battery_dispatch.communication.http.dependencies import (
    get_price_importer,
    get_price_repository,
)
from battery_dispatch.market_data.models import BIDDING_ZONE_DE_LU
from battery_dispatch.market_data.price_importer import PriceImporter
from battery_dispatch.market_data.smard_client import SmardError
from battery_dispatch.storage.repositories.price_repository import PriceRepository


router = APIRouter(prefix="/prices", tags=["prices"])


@router.post(
    "/import",
    responses={status.HTTP_502_BAD_GATEWAY: {"description": "SMARD failed or returned bad data"}},
)
async def import_prices(
    request: PriceImportRequest,
    importer: Annotated[PriceImporter, Depends(get_price_importer)],
) -> PriceImportResponse:
    """Load day-ahead prices for `[start, end)` from SMARD. Repeating an import is safe."""
    try:
        result = await importer.import_range(request.start, request.end)
    except SmardError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return PriceImportResponse(
        start=request.start, end=request.end, fetched=result.fetched, written=result.written
    )


@router.get("")
async def get_prices(
    query: Annotated[TimeRange, Query()],
    repository: Annotated[PriceRepository, Depends(get_price_repository)],
) -> PriceSeriesResponse:
    """Return the stored day-ahead prices for `[start, end)`, ordered by time."""
    points = await repository.list_range(BIDDING_ZONE_DE_LU, query.start, query.end)
    return PriceSeriesResponse(
        bidding_zone=BIDDING_ZONE_DE_LU,
        prices=[
            PricePointResponse(time=p.time, price_eur_per_mwh=p.price_eur_per_mwh) for p in points
        ],
    )
