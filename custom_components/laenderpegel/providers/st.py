from __future__ import annotations

import re

import aiohttp

from ..models import GaugeStation
from .base import BaseProvider
from .wiski import async_get_json, parse_wiski_data

BASE_URL = "https://hvz.lsaurl.de/fileadmin/Bibliothek/Politik_und_Verwaltung/MLU/HVZ/KISTERS/data"
FLUSS_PATTERN = re.compile(r"\(([^)]+)\)")
SITES = ("LHW", "SN")


def _fluss(catchment_name: str) -> str:
    match = FLUSS_PATTERN.search(catchment_name or "")
    if match:
        return match.group(1).split(",")[0].strip()
    return catchment_name or ""


class Provider(BaseProvider):
    code = "st"
    name = "Sachsen-Anhalt"

    async def async_get_stations(self, session: aiohttp.ClientSession) -> list[GaugeStation]:
        payload = await async_get_json(session, f"{BASE_URL}/internet/stations/stations.json")
        return [
            GaugeStation(
                id=str(station.get("station_no", "")),
                name=station.get("station_name", ""),
                wasser=_fluss(str(station.get("catchment_name", ""))),
            )
            for station in payload
        ]

    async def async_get_series(self, session: aiohttp.ClientSession, station_id: str):
        for site_no in SITES:
            try:
                payload = await async_get_json(
                    session, f"{BASE_URL}/internet/stations/{site_no}/{station_id}/W/week.json"
                )
            except aiohttp.ClientResponseError as err:
                if err.status == 404:
                    continue
                raise
            punkte = parse_wiski_data(payload)
            if punkte:
                return punkte
        return []

    async def async_get_gauge_zero(self, session: aiohttp.ClientSession, station_id: str) -> float | None:
        payload = await async_get_json(session, f"{BASE_URL}/internet/stations/stations.json")
        for station in payload:
            if str(station.get("station_no", "")) == station_id:
                gauge_datum = str(station.get("GAUGE_DATUM", "")).replace(",", ".")
                if gauge_datum:
                    try:
                        return float(gauge_datum)
                    except ValueError:
                        return None
        return None
