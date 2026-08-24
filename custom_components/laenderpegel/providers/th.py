from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp

from ..const import HTTP_TIMEOUT
from ..models import GaugeStation
from .base import BaseProvider

BASE_URL = "https://hnz.thueringen.de/hw-portal/thueringen.html"
ROW_PATTERN = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
CELL_PATTERN = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")


def _cell(raw: str) -> str:
    return re.sub(r"\s+", " ", TAG_PATTERN.sub("", raw)).strip()


class Provider(BaseProvider):
    code = "th"
    name = "Thüringen"
    has_history = False
    status_enabled = True

    async def _async_get_rows(self, session: aiohttp.ClientSession) -> list[list[str]]:
        async with session.get(
            BASE_URL, timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        ) as response:
            response.raise_for_status()
            html = (await response.read()).decode("utf-8", errors="replace")
        rows: list[list[str]] = []
        for row in ROW_PATTERN.findall(html):
            cells = [_cell(cell) for cell in CELL_PATTERN.findall(row)]
            if len(cells) >= 10 and cells[2] and cells[8]:
                rows.append(cells)
        return rows

    @staticmethod
    def _warnstufe(cells: list[str]) -> tuple[str, bool]:
        hwmp = cells[7] if len(cells) > 7 else ""
        if hwmp in ("", "-", "0"):
            return "", False
        return f"Meldestufe {hwmp}", True

    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        stationen: list[GaugeStation] = []
        for cells in await self._async_get_rows(session):
            pegel_kennzahl = cells[1].replace(".", "")
            if not pegel_kennzahl.isdigit():
                continue
            datum = cells[8]
            warnstufe, warnstufe_aktiv = self._warnstufe(cells)
            stationen.append(
                GaugeStation(
                    id=pegel_kennzahl,
                    name=cells[2],
                    wasser=cells[3],
                    stand=datum.split(" ")[-1] if " " in datum else "",
                    wert=cells[9],
                    warnstufe=warnstufe,
                    warnstufe_aktiv=warnstufe_aktiv,
                )
            )
        return stationen

    async def async_get_series(self, session: aiohttp.ClientSession, station_id: str):
        for cells in await self._async_get_rows(session):
            if cells[1].replace(".", "") == station_id:
                try:
                    zeitpunkt = datetime.strptime(cells[8], "%d.%m.%Y %H:%M").replace(
                        tzinfo=ZoneInfo("Europe/Berlin")
                    )
                except ValueError:
                    return []
                try:
                    wert = float(cells[9].replace(",", "."))
                except ValueError:
                    return []
                return [(zeitpunkt, wert)]
        return []
