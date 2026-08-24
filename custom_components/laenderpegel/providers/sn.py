from __future__ import annotations

from datetime import datetime
import re
from zoneinfo import ZoneInfo

import aiohttp

from ..const import HTTP_TIMEOUT
from ..models import GaugeStation
from .base import BaseProvider

BASE_URL = "https://www.umwelt.sachsen.de/umwelt/infosysteme/hwims/portal/web"
POPUP_PATTERN = re.compile(r'<div class="popUp popUpMs">.*?</div>\s*</div>\s*</div>', re.DOTALL)
DIAGRAMM_PATTERN = re.compile(r"diagrammimage_(\d+)_INFOBOXWEB_W")
TITLE_PATTERN = re.compile(r'popUpTitleBold">([^<]+)</span>')
STATUS_PATTERN = re.compile(r'popUpStatus[^>]*>\s*<div>([^<]+)</div>')
LABEL_VALUE_PATTERN = re.compile(
    r'popUpLabel">([^<]+):</span>\s*<span class="popUpValue">(.*?)</span>', re.DOTALL
)
ROW_PATTERN = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
CELL_PATTERN = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")


def _cell(raw: str) -> str:
    return re.sub(r"\s+", " ", TAG_PATTERN.sub(" ", raw)).strip()


def _parse_wert(raw: str) -> float | None:
    value = _cell(raw)
    if not value:
        return None
    try:
        return float(value.replace(" cm", "").replace(",", "."))
    except ValueError:
        return None


def _parse_status(raw: str) -> tuple[str, bool]:
    status = _cell(raw)
    if status in ("Kein Hochwasser", "Kein Hochwassermeldepegel"):
        return "keine", False
    if status == "Niedrigwasser":
        return "niedrigwasser", False
    if status.startswith("Keine aktuellen Daten"):
        return "", False
    return status, True


class Provider(BaseProvider):
    code = "sn"
    name = "Sachsen"
    status_enabled = True

    async def _async_get_list_html(self, session: aiohttp.ClientSession) -> str:
        async with session.get(
            f"{BASE_URL}/wasserstand-uebersicht",
            timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
        ) as response:
            response.raise_for_status()
            return (await response.read()).decode("utf-8", errors="replace")

    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        html = await self._async_get_list_html(session)
        stationen: list[GaugeStation] = []
        for popup in POPUP_PATTERN.findall(html):
            id_match = DIAGRAMM_PATTERN.search(popup)
            title_match = TITLE_PATTERN.search(popup)
            if not id_match or not title_match:
                continue
            titel = title_match.group(1).strip()
            if "/" in titel:
                name, wasser = (teil.strip() for teil in titel.split("/", 1))
            else:
                name, wasser = titel, ""
            datum = ""
            wert_raw = ""
            warnstufe = ""
            warnstufe_aktiv = False
            status_match = STATUS_PATTERN.search(popup)
            if status_match:
                warnstufe, warnstufe_aktiv = _parse_status(status_match.group(1))
            for label, wert in LABEL_VALUE_PATTERN.findall(popup):
                if label == "Datum":
                    datum = _cell(wert).replace(" Uhr", "")
                elif label == "Wasserstand":
                    wert_raw = wert
            stationen.append(
                GaugeStation(
                    id=id_match.group(1),
                    name=name,
                    wasser=wasser,
                    stand=datum.split(" ")[-1] if " " in datum else "",
                    wert=_cell(wert_raw).replace(" cm", ""),
                    warnstufe=warnstufe,
                    warnstufe_aktiv=warnstufe_aktiv,
                )
            )
        return stationen

    async def async_get_series(self, session: aiohttp.ClientSession, station_id: str):
        async with session.get(
            f"{BASE_URL}/wasserstand-pegel-{station_id}",
            timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
        ) as response:
            response.raise_for_status()
            html = (await response.read()).decode("utf-8", errors="replace")
        now = datetime.now(ZoneInfo("Europe/Berlin"))
        punkte: list[tuple[datetime, float]] = []
        for row in ROW_PATTERN.findall(html):
            cells = [_cell(cell) for cell in CELL_PATTERN.findall(row)]
            if len(cells) < 2 or cells[0] in ("Zeitpunkt", ""):
                continue
            datum, w_wert = cells[0], cells[1]
            if not datum or "20" not in datum:
                continue
            try:
                zeitpunkt = datetime.strptime(datum, "%d.%m.%Y %H:%M").replace(
                    tzinfo=ZoneInfo("Europe/Berlin")
                )
                wert = _parse_wert(w_wert)
            except ValueError:
                continue
            if wert is not None and zeitpunkt <= now:
                punkte.append((zeitpunkt, wert))
        punkte.sort(key=lambda punkt: punkt[0])
        return punkte
