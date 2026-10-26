"""Client for the open SMARD chart data API of the German Federal Network Agency.

SMARD serves a time series as weekly packages. An index lists the start of every package
in milliseconds since epoch; a package covers the time until the next one starts. Values
that are not published yet are `null`.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx2
from pydantic import BaseModel, ValidationError

from battery_dispatch.config.config_manager import SmardConfig
from battery_dispatch.core.component_base import ComponentBase
from battery_dispatch.core.health import ComponentHealth, HealthState
from battery_dispatch.market_data.models import PricePoint


class SmardError(Exception):
    """SMARD could not be reached or returned data in an unexpected shape."""


class _Index(BaseModel):
    timestamps: list[int]


class _Package(BaseModel):
    series: list[tuple[int, float | None]]


class SmardClient(ComponentBase):
    def __init__(
        self, config: SmardConfig, transport: httpx2.AsyncBaseTransport | None = None
    ) -> None:
        super().__init__("smard")
        self._config = config
        self._transport = transport
        self._client: httpx2.AsyncClient | None = None

    async def start(self) -> None:
        self._client = httpx2.AsyncClient(
            base_url=self._config.base_url,
            timeout=self._config.timeout_s,
            transport=self._transport,
        )

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.aclose()
        self._client = None

    async def health(self) -> ComponentHealth:
        # SMARD is only needed for imports, so its availability does not affect health.
        if self._client is None:
            return ComponentHealth(name=self.name, state=HealthState.DOWN, detail="not started")
        return ComponentHealth(name=self.name, state=HealthState.OK)

    async def fetch_prices(self, start: datetime, end: datetime) -> list[PricePoint]:
        """Return all published prices with `start <= time < end`, ordered by time."""
        index = await self._fetch_index()
        points: list[PricePoint] = []
        for package in packages_for_range(index, start, end):
            points.extend(await self._fetch_package(package))
        return [p for p in points if start <= p.time < end]

    async def _fetch_index(self) -> list[int]:
        c = self._config
        data = await self._get_json(f"/{c.filter_id}/{c.region}/index_{c.resolution}.json")
        try:
            return sorted(_Index.model_validate(data).timestamps)
        except ValidationError as exc:
            raise SmardError("unexpected index format") from exc

    async def _fetch_package(self, package: int) -> list[PricePoint]:
        c = self._config
        path = f"/{c.filter_id}/{c.region}/{c.filter_id}_{c.region}_{c.resolution}_{package}.json"
        data = await self._get_json(path)
        try:
            series = _Package.model_validate(data).series
        except ValidationError as exc:
            raise SmardError(f"unexpected format of package {package}") from exc
        return [
            PricePoint(time=_from_ms(ts), price_eur_per_mwh=price)
            for ts, price in series
            if price is not None
        ]

    async def _get_json(self, path: str) -> Any:
        if self._client is None:
            raise RuntimeError("SmardClient is not started")
        try:
            response = await self._client.get(path)
            response.raise_for_status()
            return response.json()
        except (httpx2.HTTPError, ValueError) as exc:
            raise SmardError(f"request to SMARD failed: {path}") from exc


def packages_for_range(index: Sequence[int], start: datetime, end: datetime) -> list[int]:
    """Select the packages of a sorted index that overlap `[start, end)`."""
    start_ms, end_ms = _to_ms(start), _to_ms(end)
    selected: list[int] = []
    for i, package in enumerate(index):
        next_package = index[i + 1] if i + 1 < len(index) else None
        if package < end_ms and (next_package is None or next_package > start_ms):
            selected.append(package)
    return selected


def _to_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _from_ms(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, UTC)
