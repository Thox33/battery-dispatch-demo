"""Loads prices from SMARD into the database."""

import logging
from datetime import datetime

from battery_dispatch.market_data.models import BIDDING_ZONE_DE_LU, ImportResult
from battery_dispatch.market_data.smard_client import SmardClient
from battery_dispatch.storage.repositories.price_repository import PriceRepository


logger = logging.getLogger(__name__)


class PriceImporter:
    def __init__(
        self,
        client: SmardClient,
        repository: PriceRepository,
        bidding_zone: str = BIDDING_ZONE_DE_LU,
    ) -> None:
        self._client = client
        self._repository = repository
        self._bidding_zone = bidding_zone

    async def import_range(self, start: datetime, end: datetime) -> ImportResult:
        points = await self._client.fetch_prices(start, end)
        written = await self._repository.upsert(self._bidding_zone, points)
        logger.info(
            "Imported prices %s to %s: %d fetched, %d written", start, end, len(points), written
        )
        return ImportResult(fetched=len(points), written=written)
