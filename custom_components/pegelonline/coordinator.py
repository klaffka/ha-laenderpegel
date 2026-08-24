from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import api
from .const import (
    CONF_HAS_FORECAST,
    CONF_STATION_NAME,
    CONF_STATION_UUID,
    DOMAIN,
    FORECAST_HORIZON_HOURS,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type PegelonlineData = dict[str, Any]


def summarize_forecast(points: list[dict]) -> dict[str, Any] | None:
    now = dt_util.now()
    horizon = now + timedelta(hours=FORECAST_HORIZON_HOURS)
    punkte = [
        punkt
        for punkt in points
        if dt_util.parse_datetime(punkt["timestamp"]) <= horizon
    ]
    if not punkte:
        return None
    werte = [punkt["value"] for punkt in punkte]
    return {
        "initialisiert": punkte[0].get("initialized"),
        "ende": max(punkt["timestamp"] for punkt in points),
        "min_24h": min(werte),
        "max_24h": max(werte),
        "anzahl_punkte": len(punkte),
    }


class PegelonlineCoordinator(DataUpdateCoordinator[PegelonlineData]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.data[CONF_STATION_NAME]}",
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> PegelonlineData:
        session = async_get_clientsession(self.hass)
        station_uuid = self.config_entry.data[CONF_STATION_UUID]
        data: PegelonlineData = {}
        try:
            data["messwert"] = await api.async_get_current_measurement(session, station_uuid)
        except aiohttp.ClientResponseError as err:
            if err.status == 404:
                data["messwert"] = None
            else:
                raise UpdateFailed(f"Current measurement not available: {err}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Could not fetch current measurement: {err}") from err
        if self.config_entry.data.get(CONF_HAS_FORECAST):
            try:
                rohdaten = await api.async_get_forecast(session, station_uuid)
            except aiohttp.ClientResponseError as err:
                if err.status == 404:
                    rohdaten = []
                else:
                    raise UpdateFailed(f"Forecast not available: {err}") from err
            except aiohttp.ClientError as err:
                raise UpdateFailed(f"Could not fetch forecast: {err}") from err
            data["vorhersage"] = summarize_forecast(rohdaten)
        return data
