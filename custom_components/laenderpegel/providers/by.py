from __future__ import annotations

from datetime import datetime
import re
from zoneinfo import ZoneInfo

import aiohttp

from ..const import HTTP_TIMEOUT
from ..models import GaugeStation
from .base import BaseProvider

BASE_URL = "https://www.gkd.bayern.de"
DETAIL_LINK_PATTERN = re.compile(
    r"href=\"(https://www\.gkd\.bayern\.de/de/fluesse/wasserstand/[^\"]+/messwerte\?method=tabellen)\""
)
PKZ_PATTERN = re.compile(r"-(\d{8})/")
ROW_PATTERN = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
CELL_PATTERN = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")


def _cell(raw: str) -> str:
    return re.sub(r"\s+", " ", TAG_PATTERN.sub("", raw)).strip()


class Provider(BaseProvider):
    code = "by"
    name = "Bayern"

    async def _async_get_list_html(self, session: aiohttp.ClientSession) -> str:
        async with session.get(
            f"{BASE_URL}/de/fluesse/wasserstand/tabellen",
            timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
        ) as response:
            response.raise_for_status()
            return (await response.read()).decode("utf-8", errors="replace")

    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        html = await self._async_get_list_html(session)
        stationen: list[GaugeStation] = []
        for row in ROW_PATTERN.findall(html):
            link_match = DETAIL_LINK_PATTERN.search(row)
            if not link_match:
                continue
            cells = [_cell(cell) for cell in CELL_PATTERN.findall(row)]
            if len(cells) < 5:
                continue
            pkz_match = PKZ_PATTERN.search(link_match.group(1))
            if not pkz_match:
                continue
            datum = cells[3]
            zeit = datum.split(" ")[1].replace(" Uhr", "") if " " in datum else ""
            stationen.append(
                GaugeStation(
                    id=pkz_match.group(1),
                    name=cells[0],
                    wasser=cells[1],
                    stand=zeit,
                    wert=cells[4],
                )
            )
        return stationen

    async def _async_get_detail_url(self, session: aiohttp.ClientSession, station_id: str) -> str | None:
        html = await self._async_get_list_html(session)
        for row in ROW_PATTERN.findall(html):
            link_match = DETAIL_LINK_PATTERN.search(row)
            if link_match and f"-{station_id}/" in link_match.group(1):
                return link_match.group(1).replace("messwerte?method=tabellen", "messwerte/tabelle")
        return None

    async def async_get_series(self, session: aiohttp.ClientSession, station_id: str):
        detail_url = await self._async_get_detail_url(session, station_id)
        if detail_url is None:
            return []
        async with session.get(
            detail_url, timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        ) as response:
            response.raise_for_status()
            html = (await response.read()).decode("utf-8", errors="replace")
        punkte: list[tuple[datetime, float]] = []
        for row in ROW_PATTERN.findall(html):
            cells = [_cell(cell) for cell in CELL_PATTERN.findall(row)]
            if len(cells) < 2:
                continue
            datum, wert = cells[0], cells[1]
            if not datum or "." not in datum:
                continue
            try:
                zeitpunkt = datetime.strptime(datum.replace(" Uhr", ""), "%d.%m.%Y %H:%M").replace(
                    tzinfo=ZoneInfo("Europe/Berlin")
                )
                punkte.append((zeitpunkt, float(wert.replace(",", "."))))
            except ValueError:
                continue
        punkte.sort(key=lambda punkt: punkt[0])
        return punkte
