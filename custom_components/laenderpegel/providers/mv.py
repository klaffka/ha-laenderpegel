from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp

from ..const import HTTP_TIMEOUT
from ..models import GaugeStation
from .base import BaseProvider

BASE_URL = "https://fis-wasser-mv.de/pegel-mv"
BERLIN = ZoneInfo("Europe/Berlin")

ROW_PATTERN = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
TD_PATTERN = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")
ID_PATTERN = re.compile(r"""href=['"](\d+\.\d+)\.html['"]""")
POINT_PATTERN = re.compile(r"new Date\('(\d{4}/\d{2}/\d{2} \d{2}:\d{2})'\),\s*(-?\d+(?:\.\d+)?)")
GAUGE_ZERO_PATTERN = re.compile(r"PNP\s*=\s*(-?\d+(?:\.\d+)?)\s*m")


def _strip_tags(fragment: str) -> str:
    return TAG_PATTERN.sub("", fragment).replace("&nbsp;", " ").strip()


async def _async_get(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)) as response:
        response.raise_for_status()
        return await response.text()


class Provider(BaseProvider):
    code = "mv"
    name = "Mecklenburg-Vorpommern"

    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        html = await _async_get(session, f"{BASE_URL}/pegel_list.html")
        stationen: list[GaugeStation] = []
        for row in ROW_PATTERN.findall(html):
            match = ID_PATTERN.search(row)
            if not match:
                continue
            zellen = TD_PATTERN.findall(row)
            if len(zellen) < 4:
                continue
            stationen.append(
                GaugeStation(
                    id=match.group(1),
                    name=_strip_tags(zellen[0]),
                    wasser=_strip_tags(zellen[1]),
                    stand=_strip_tags(zellen[2]),
                    wert=_strip_tags(zellen[3]),
                )
            )
        return stationen

    async def async_get_series(
        self, session: aiohttp.ClientSession, station_id: str
    ) -> list[tuple[datetime, float]]:
        payload = await _async_get(session, f"{BASE_URL}/data/{station_id}.js")
        punkte: list[tuple[datetime, float]] = []
        for zeit, wert in POINT_PATTERN.findall(payload):
            zeitpunkt = datetime.strptime(zeit, "%Y/%m/%d %H:%M").replace(tzinfo=BERLIN)
            punkte.append((zeitpunkt, float(wert)))
        return punkte

    async def async_get_gauge_zero(
        self, session: aiohttp.ClientSession, station_id: str
    ) -> float | None:
        html = await _async_get(session, f"{BASE_URL}/{station_id}.html")
        match = GAUGE_ZERO_PATTERN.search(html)
        return float(match.group(1)) if match else None
