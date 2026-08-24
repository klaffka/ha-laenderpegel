from __future__ import annotations

import aiohttp

from ..models import GaugeStation
from .base import BaseProvider
from .wiski import async_get_json, parse_wiski_data

BASE_URL = "https://www.hochwasserportal.nrw/data"


class Provider(BaseProvider):
    code = "nw"
    name = "Nordrhein-Westfalen"

    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        payload = await self._async_get_payload(session)
        stationen: list[GaugeStation] = []
        for entry in payload:
            wert = entry.get("ts_value")
            timestamp = entry.get("timestamp", "")
            zeit = timestamp[11:16] if len(timestamp) >= 16 else ""
            stationen.append(
                GaugeStation(
                    id=str(entry.get("station_no", "")),
                    name=entry.get("station_name", ""),
                    wasser=entry.get("catchment_name", ""),
                    stand=zeit,
                    wert=str(wert) if wert is not None else "",
                )
            )
        return stationen

    async def _async_get_payload(self, session: aiohttp.ClientSession) -> list[dict]:
        return await async_get_json(session, f"{BASE_URL}/internet/layers/10/index.json")

    async def async_get_series(self, session: aiohttp.ClientSession, station_id: str):
        payload = await self._async_get_payload(session)
        entry = next((e for e in payload if str(e.get("station_no", "")) == station_id), None)
        if entry is None:
            return []
        return await self._async_get_week(session, station_id, str(entry.get("site_no", "100")))

    async def _async_get_week(self, session: aiohttp.ClientSession, station_id: str, site_no: str):
        payload = await async_get_json(
            session, f"{BASE_URL}/internet/stations/{site_no}/{station_id}/S/week.json"
        )
        return parse_wiski_data(payload)
