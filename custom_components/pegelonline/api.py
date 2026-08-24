from __future__ import annotations

import aiohttp

from .const import API_BASE, HTTP_TIMEOUT


async def _async_get_json(session: aiohttp.ClientSession, url: str) -> object:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)) as response:
        response.raise_for_status()
        return await response.json()


async def async_get_stations(session: aiohttp.ClientSession) -> list[dict]:
    return await _async_get_json(session, f"{API_BASE}/stations.json")


async def async_get_station(session: aiohttp.ClientSession, station_uuid: str) -> dict:
    return await _async_get_json(
        session, f"{API_BASE}/stations/{station_uuid}.json?includeTimeseries=true"
    )


async def async_get_current_measurement(session: aiohttp.ClientSession, station_uuid: str) -> dict:
    return await _async_get_json(
        session, f"{API_BASE}/stations/{station_uuid}/W/currentmeasurement.json"
    )


async def async_get_forecast(session: aiohttp.ClientSession, station_uuid: str) -> list[dict]:
    return await _async_get_json(
        session, f"{API_BASE}/stations/{station_uuid}/WV/measurements.json?start=P0D"
    )
