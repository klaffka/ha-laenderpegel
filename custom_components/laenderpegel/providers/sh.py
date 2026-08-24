from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp

from ..const import HTTP_TIMEOUT
from ..models import GaugeStation
from .base import BaseProvider

BASE_URL = "https://hsi-sh.de/pegel"
BERLIN = ZoneInfo("Europe/Berlin")

LIVE_ROW_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}),(-?\d+(?:\.\d+)?)\s*$", re.MULTILINE)


def _parse_stamm(payload: str) -> list[list[str]]:
    zeilen = payload.splitlines()
    return [zeile.split(";") for zeile in zeilen[1:] if zeile.strip()]


def _is_active(row: list[str]) -> bool:
    return not row[9].strip() or row[9].strip() == "---"


class Provider(BaseProvider):
    code = "sh"
    name = "Schleswig-Holstein"

    async def _async_get_stamm(self, session: aiohttp.ClientSession) -> list[list[str]]:
        async with session.get(
            f"{BASE_URL}/stamm_csv/pegel_stammdaten.csv", timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        ) as response:
            response.raise_for_status()
            payload = await response.text()
        return _parse_stamm(payload)

    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        rows = await self._async_get_stamm(session)
        stationen: list[GaugeStation] = []
        for row in rows:
            if len(row) < 10 or not _is_active(row):
                continue
            stationen.append(GaugeStation(id=row[1], name=row[0], wasser=row[2]))
        return stationen

    async def async_get_series(
        self, session: aiohttp.ClientSession, station_id: str
    ) -> list[tuple[datetime, float]]:
        async with session.get(
            f"{BASE_URL}/hsidata/{station_id}W.txt", timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        ) as response:
            response.raise_for_status()
            payload = await response.text()
        punkte: list[tuple[datetime, float]] = []
        for zeit, wert in LIVE_ROW_PATTERN.findall(payload):
            zeitpunkt = datetime.strptime(zeit, "%Y-%m-%d %H:%M").replace(tzinfo=BERLIN)
            punkte.append((zeitpunkt, float(wert)))
        return punkte

    async def async_get_gauge_zero(
        self, session: aiohttp.ClientSession, station_id: str
    ) -> float | None:
        rows = await self._async_get_stamm(session)
        for row in rows:
            if len(row) > 6 and row[1] == station_id:
                pnp = row[6].replace(",", ".").strip()
                if pnp and pnp != "---":
                    try:
                        return float(pnp)
                    except ValueError:
                        return None
        return None
