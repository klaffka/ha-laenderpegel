from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import aiohttp

from ..models import GaugeStation
from .base import BaseProvider
from .wiski import async_get_json

BASE_URL = "https://bis.azure-api.net/PegelonlineNeu/REST"
SUBSCRIPTION_KEY = "19094e54510d4e89b140ff2d3abf715f"


def _datum_to_dt(datum_utc: str) -> datetime:
    milliseconds = int(datum_utc[len("/Date(") : -len(")/")])
    return datetime.fromtimestamp(milliseconds / 1000, tz=UTC).astimezone(ZoneInfo("Europe/Berlin"))


class Provider(BaseProvider):
    code = "ni"
    name = "Niedersachsen"

    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        payload = await async_get_json(
            session, f"{BASE_URL}/stammdaten/stationen/All?subscription-key={SUBSCRIPTION_KEY}"
        )
        stationen: list[GaugeStation] = []
        for entry in payload.get("getStammdatenResult", []):
            name = entry.get("Name", "")
            ort = entry.get("Ort", "")
            if ort and ort != "Keine Daten":
                name = f"{name} ({ort})" if name else ort
            stationen.append(
                GaugeStation(
                    id=str(entry.get("STA_ID", "")),
                    name=name,
                    wasser=entry.get("GewaesserName", ""),
                )
            )
        return stationen

    async def async_get_series(self, session: aiohttp.ClientSession, station_id: str):
        payload = await async_get_json(
            session,
            f"{BASE_URL}/chart/station/{station_id}/datenspuren/parameter/1/tage/-30/forecast/true"
            f"?subscription-key={SUBSCRIPTION_KEY}",
        )
        punkte: list[tuple[datetime, float]] = []
        for spur in payload.get("getPegelDatenspurenChartResult", []):
            if spur.get("IstVorhersage"):
                continue
            for messung in spur.get("Pegelstaende", []):
                if messung.get("Wert") is None or not messung.get("DatumUTC"):
                    continue
                punkte.append((_datum_to_dt(messung["DatumUTC"]), float(messung["Wert"])))
        punkte.sort(key=lambda punkt: punkt[0])
        return punkte

    async def async_get_gauge_zero(self, session: aiohttp.ClientSession, station_id: str) -> float | None:
        payload = await async_get_json(
            session,
            f"{BASE_URL}/chart/station/{station_id}/datenspuren/parameter/1/tage/-1/forecast/true"
            f"?subscription-key={SUBSCRIPTION_KEY}",
        )
        for spur in payload.get("getPegelDatenspurenChartResult", []):
            pegel_hoehe = spur.get("PegelHoehe")
            if pegel_hoehe is not None:
                try:
                    return float(pegel_hoehe)
                except (TypeError, ValueError):
                    return None
        return None
