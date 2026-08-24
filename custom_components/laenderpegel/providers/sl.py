from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp

from ..const import HTTP_TIMEOUT
from ..models import GaugeStation
from .base import BaseProvider

BASE_URL = "https://iframe01.saarland.de/extern/wasser"
BERLIN = ZoneInfo("Europe/Berlin")

PEGEL_PATTERN = re.compile(
    r"Pegel\(\s*[\d.]+,\s*[\d.]+,\s*'([^']*)',\s*'[^']*',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)'"
)
ZEIT_PATTERN = re.compile(r"(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2})")


class Provider(BaseProvider):
    code = "sl"
    name = "Saarland"
    has_history = False

    async def _async_fetch_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        async with session.get(
            f"{BASE_URL}/Daten.js", timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        ) as response:
            response.raise_for_status()
            payload = (await response.read()).decode("iso-8859-1")
        stationen: list[GaugeStation] = []
        for station_id, name, wasser, wert, zeit in PEGEL_PATTERN.findall(payload):
            if not station_id:
                continue
            wert_text = wert.strip()
            if wert_text in ("", "****"):
                wert_text = ""
            zeit_match = ZEIT_PATTERN.search(zeit)
            stand = zeit_match.group(1) if zeit_match else ""
            stationen.append(
                GaugeStation(id=station_id, name=name, wasser=wasser, stand=stand, wert=wert_text)
            )
        return stationen

    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        return await self._async_fetch_stations(session)

    async def async_get_series(
        self, session: aiohttp.ClientSession, station_id: str
    ) -> list[tuple[datetime, float]]:
        stationen = await self._async_fetch_stations(session)
        for station in stationen:
            if station.id == station_id and station.wert:
                zeit = datetime.strptime(station.stand, "%d.%m.%Y %H:%M").replace(tzinfo=BERLIN)
                return [(zeit, float(station.wert))]
        return []
