from __future__ import annotations

from datetime import datetime
import re
from zoneinfo import ZoneInfo

import aiohttp

from ..const import HTTP_TIMEOUT
from ..models import GaugeStation
from .base import BaseProvider

BASE_URL = "https://www.hvz.baden-wuerttemberg.de/map_peg.html"
ARRAY_PATTERN = re.compile(r"var SiteStations\s*=\s*(\[.*?\]);", re.DOTALL)
ROW_PATTERN = re.compile(r"\[[^\[\]]+\]")
FELD_PATTERN = re.compile(r"(-?\d+(?:\.\d+)?|'[^']*')")


def _feld_zahl(feld: list[str], index: int) -> float | None:
    if index >= len(feld):
        return None
    try:
        return float(feld[index].strip("'"))
    except ValueError:
        return None


def _feld_text(feld: list[str], index: int) -> str:
    if index >= len(feld):
        return ""
    return feld[index].strip("'")


def _parse_zeile(zeile: str) -> list[str]:
    return FELD_PATTERN.findall(zeile)


class Provider(BaseProvider):
    code = "bw"
    name = "Baden-Württemberg"
    has_history = False

    async def _async_get_eintraege(self, session: aiohttp.ClientSession) -> list[list[str]]:
        async with session.get(
            BASE_URL, timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        ) as response:
            response.raise_for_status()
            html = (await response.read()).decode("utf-8", errors="replace")
        array_match = ARRAY_PATTERN.search(html)
        if not array_match:
            return []
        return [_parse_zeile(zeile) for zeile in ROW_PATTERN.findall(array_match.group(1))]

    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        stationen: list[GaugeStation] = []
        for felder in await self._async_get_eintraege(session):
            if len(felder) < 10:
                continue
            wert = _feld_zahl(felder, 6)
            datum = _feld_text(felder, 9)
            stationen.append(
                GaugeStation(
                    id=_feld_text(felder, 0),
                    name=_feld_text(felder, 3),
                    wasser=_feld_text(felder, 4),
                    stand=datum.split(" ")[1] if " " in datum else "",
                    wert=str(wert) if wert is not None else "",
                )
            )
        return stationen

    async def async_get_series(self, session: aiohttp.ClientSession, station_id: str):
        for felder in await self._async_get_eintraege(session):
            if len(felder) < 10 or _feld_text(felder, 0) != station_id:
                continue
            wert = _feld_zahl(felder, 6)
            datum = _feld_text(felder, 9)
            if wert is None or not datum:
                return []
            try:
                zeitpunkt = datetime.strptime(datum.replace(" MESZ", ""), "%d.%m.%Y %H:%M").replace(
                    tzinfo=ZoneInfo("Europe/Berlin")
                )
            except ValueError:
                return []
            return [(zeitpunkt, wert)]
        return []
