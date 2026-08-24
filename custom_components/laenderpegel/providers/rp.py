from __future__ import annotations

from datetime import datetime

import aiohttp

from ..models import GaugeStation
from .base import BaseProvider
from .wiski import async_get_json

BASE_URL = "https://hochwasser.rlp.de/api/v1"


class Provider(BaseProvider):
    code = "rp"
    name = "Rheinland-Pfalz"
    unit = "m"

    async def _async_get_config(self, session: aiohttp.ClientSession) -> dict:
        return await async_get_json(session, f"{BASE_URL}/config")

    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        config = await self._async_get_config(session)
        index = await async_get_json(session, f"{BASE_URL}/index")
        rivers = config.get("rivers", {})
        sites = index.get("measurementSites", {})
        stationen: list[GaugeStation] = []
        for hkn, site in config.get("measurementsite", {}).items():
            werte = sites.get(str(hkn), {})
            y_last = werte.get("yLast")
            x_last = werte.get("xLast", "")
            zeit = x_last[11:16] if len(x_last) >= 16 else ""
            river_ids = site.get("rivers") or []
            wasser = rivers.get(str(river_ids[0]), {}).get("name", "") if river_ids else ""
            stationen.append(
                GaugeStation(
                    id=str(hkn),
                    name=site.get("name", ""),
                    wasser=wasser,
                    stand=zeit,
                    wert=str(y_last) if y_last is not None else "",
                )
            )
        return stationen

    async def async_get_series(self, session: aiohttp.ClientSession, station_id: str):
        payload = await async_get_json(session, f"{BASE_URL}/measurement-site/{station_id}")
        punkte = []
        for messung in payload.get("W", {}).get("measurements", []):
            if messung.get("y") is None:
                continue
            zeitpunkt = datetime.fromisoformat(messung["x"])
            punkte.append((zeitpunkt, float(messung["y"])))
        return punkte

    async def async_get_gauge_zero(self, session: aiohttp.ClientSession, station_id: str) -> float | None:
        config = await self._async_get_config(session)
        site = config.get("measurementsite", {}).get(station_id)
        if site is None:
            return None
        elevation = site.get("elevation")
        try:
            return float(elevation) if elevation is not None else None
        except (TypeError, ValueError):
            return None
