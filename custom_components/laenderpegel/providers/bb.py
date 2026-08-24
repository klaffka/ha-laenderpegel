from __future__ import annotations

from datetime import datetime
import re
from zoneinfo import ZoneInfo

import aiohttp

from ..const import HTTP_TIMEOUT
from ..models import GaugeStation
from .base import BaseProvider

BASE_URL = "https://pegelportal.brandenburg.de"
BERLIN = ZoneInfo("Europe/Berlin")

FEATURE_PATTERN = re.compile(r"pkz:\s*'(\d+)'")
FIELD_PATTERN = re.compile(r"^\s*(name|gewaesser|datum|zeit|wert|klasse):\s*'([^']*)'", re.MULTILINE)
CSV_ROW_PATTERN = re.compile(r"^\"(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2})\";(-?\d+(?:\.\d+)?)\s*$", re.MULTILINE)
MISSING_VALUE = -777


class Provider(BaseProvider):
    code = "bb"
    name = "Brandenburg"
    status_enabled = True

    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        async with session.get(BASE_URL + "/start.php", timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)) as response:
            response.raise_for_status()
            payload = (await response.read()).decode("iso-8859-1")
        stationen: list[GaugeStation] = []
        seen: set[str] = set()
        for match in FEATURE_PATTERN.finditer(payload):
            pkz = match.group(1)
            if pkz in seen:
                continue
            seen.add(pkz)
            fenster = payload[max(0, match.start() - 400): match.end() + 800]
            felder = dict(FIELD_PATTERN.findall(fenster))
            if not felder.get("name"):
                continue
            datum = felder.get("datum", "")
            zeit = felder.get("zeit", "")
            stand = f"{datum} {zeit}".strip()
            warnstufe = ""
            warnstufe_aktiv = False
            try:
                klasse = int(felder.get("klasse", ""))
            except ValueError:
                klasse = 0
            if klasse >= 2:
                warnstufe = f"Meldestufe {klasse - 1}"
                warnstufe_aktiv = True
            stationen.append(
                GaugeStation(
                    id=pkz,
                    name=felder["name"],
                    wasser=felder.get("gewaesser", ""),
                    stand=stand,
                    wert=felder.get("wert", ""),
                    warnstufe=warnstufe,
                    warnstufe_aktiv=warnstufe_aktiv,
                )
            )
        return stationen

    async def async_get_series(
        self, session: aiohttp.ClientSession, station_id: str
    ) -> list[tuple[datetime, float]]:
        async with session.get(
            f"{BASE_URL}/source/download/{station_id}_wasserstand.csv",
            timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
        ) as response:
            response.raise_for_status()
            payload = (await response.read()).decode("iso-8859-1")
        punkte: list[tuple[datetime, float]] = []
        for zeit, wert in CSV_ROW_PATTERN.findall(payload):
            if float(wert) == MISSING_VALUE:
                continue
            zeitpunkt = datetime.strptime(zeit, "%d.%m.%Y %H:%M").replace(tzinfo=BERLIN)
            punkte.append((zeitpunkt, float(wert)))
        return punkte
