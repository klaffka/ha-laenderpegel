from __future__ import annotations

import abc
from datetime import datetime

import aiohttp

from ..models import GaugeStation


class BaseProvider(abc.ABC):
    code: str
    name: str
    unit: str = "cm"
    has_history: bool = True
    status_enabled: bool = False

    @abc.abstractmethod
    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        """Return all gauge stations of this state's network."""

    async def async_get_series(
        self, session: aiohttp.ClientSession, station_id: str
    ) -> list[tuple[datetime, float]]:
        """Return the most recent measurement series of a station."""
        return []

    async def async_get_gauge_zero(
        self, session: aiohttp.ClientSession, station_id: str
    ) -> float | None:
        """Return the gauge zero point, if known."""
        return None

    async def async_get_station(
        self, session: aiohttp.ClientSession, station_id: str
    ) -> GaugeStation | None:
        """Return the current data of a single station, if available."""
        for station in await self.async_get_stations(session):
            if station.id == station_id:
                return station
        return None
