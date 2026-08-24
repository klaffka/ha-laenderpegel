from __future__ import annotations

import aiohttp

from ..models import GaugeStation
from .base import BaseProvider
from .wiski import async_get_json, parse_wiski_data

BASE_URL = "https://www.hlnug.de/static/pegel/wiskiweb3/data"
OBJECT_TYPE_PEGEL = "Allgemein;Oberflächengewässer"


class Provider(BaseProvider):
    code = "he"
    name = "Hessen"

    async def _async_get_payload(self, session: aiohttp.ClientSession) -> list[dict]:
        return await async_get_json(session, f"{BASE_URL}/internet/stations/stations.json")

    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        payload = await self._async_get_payload(session)
        stationen: list[GaugeStation] = []
        for station in payload:
            if station.get("object_type") != OBJECT_TYPE_PEGEL:
                continue
            stationen.append(
                GaugeStation(
                    id=str(station.get("station_no", "")),
                    name=station.get("station_name", ""),
                    wasser=station.get("catchment_name", ""),
                )
            )
        return stationen

    async def async_get_series(self, session: aiohttp.ClientSession, station_id: str):
        payload = await async_get_json(
            session, f"{BASE_URL}/internet/stations/0/{station_id}/W/AktuelleDaten48h.json"
        )
        return parse_wiski_data(payload)

    async def async_get_gauge_zero(self, session: aiohttp.ClientSession, station_id: str) -> float | None:
        payload = await self._async_get_payload(session)
        for station in payload:
            if str(station.get("station_no", "")) == station_id:
                gauge_datum = str(station.get("GAUGE_DATUM", "")).replace(",", ".")
                if gauge_datum:
                    try:
                        return float(gauge_datum)
                    except ValueError:
                        return None
        return None
