from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp

from ..const import HTTP_TIMEOUT
from ..models import GaugeStation
from .base import BaseProvider

BASE_URL = "https://www.wabiha.de/pegel.html"
ROW_PATTERN = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
CELL_PATTERN = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")
ID_PATTERN = re.compile(r"pegelbuttonlink\s+p(\d+)")
TITEL_PATTERN = re.compile(r"data-modalTitle='Details zum Pegel ([^']+? - \d+)'")
WERTE_PATTERN = re.compile(r"itemprop='value'>(-?[\d.]+)</span>")
DATUM_PATTERN = re.compile(r"(\d{2}\.\d{2}\.\d{2} \d{2}:\d{2})")
WARNSTUFEN_PATTERN = re.compile(r"Warnstufe</b>(?:<span[^>]*></span>)?([^<]*)")


def _cell(raw: str) -> str:
    text = TAG_PATTERN.sub(" ", raw)
    text = text.replace("&nbsp;", " ").replace("&plusmn;", "±")
    return re.sub(r"\s+", " ", text).strip()


class Provider(BaseProvider):
    code = "hb"
    name = "Hamburg"
    unit = "m"
    has_history = False
    status_enabled = True

    async def _async_get_rows(self, session: aiohttp.ClientSession) -> list[str]:
        async with session.get(
            BASE_URL, timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        ) as response:
            response.raise_for_status()
            html = (await response.read()).decode("utf-8", errors="replace")
        return ROW_PATTERN.findall(html)

    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        stationen: list[GaugeStation] = []
        for row in await self._async_get_rows(session):
            id_match = ID_PATTERN.search(row)
            titel_match = TITEL_PATTERN.search(row)
            if not id_match or not titel_match:
                continue
            wasser_match = re.search(r"<span itemprop='name'>([^<]+)</span>", row)
            werte_match = WERTE_PATTERN.search(row)
            datum_match = DATUM_PATTERN.search(row)
            name = titel_match.group(1).rsplit(" - ", 1)[0].strip()
            wasser = _cell(wasser_match.group(1)) if wasser_match else ""
            datum = datum_match.group(1) if datum_match else ""
            warnstufe = ""
            warnstufe_aktiv = False
            warn_match = WARNSTUFEN_PATTERN.search(row)
            if warn_match:
                warn_text = _cell(warn_match.group(1))
                if warn_text and warn_text != "keine":
                    warnstufe = f"Meldestufe {warn_text}" if warn_text.isdigit() else warn_text
                    warnstufe_aktiv = warn_text.isdigit()
            stationen.append(
                GaugeStation(
                    id=id_match.group(1),
                    name=name,
                    wasser=wasser,
                    stand=datum.split(" ")[-1] if " " in datum else "",
                    wert=werte_match.group(1) if werte_match else "",
                    warnstufe=warnstufe,
                    warnstufe_aktiv=warnstufe_aktiv,
                )
            )
        return stationen

    async def async_get_series(self, session: aiohttp.ClientSession, station_id: str):
        for row in await self._async_get_rows(session):
            if not ID_PATTERN.search(row):
                continue
            if ID_PATTERN.search(row).group(1) != station_id:
                continue
            werte_match = WERTE_PATTERN.search(row)
            datum_match = DATUM_PATTERN.search(row)
            if not werte_match or not datum_match:
                return []
            try:
                zeitpunkt = datetime.strptime(datum_match.group(1), "%d.%m.%y %H:%M").replace(
                    tzinfo=ZoneInfo("Europe/Berlin")
                )
            except ValueError:
                return []
            try:
                wert = float(werte_match.group(1))
            except ValueError:
                return []
            return [(zeitpunkt, wert)]
        return []
