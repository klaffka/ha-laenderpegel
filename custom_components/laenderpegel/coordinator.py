from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_PROVIDER,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    SCAN_INTERVAL,
    get_device_info,
)
from .providers import get_provider

_LOGGER = logging.getLogger(__name__)

type LaenderpegelData = dict[str, Any]


class LaenderpegelCoordinator(DataUpdateCoordinator[LaenderpegelData]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.data[CONF_STATION_NAME]}",
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )
        self.provider = get_provider(entry.data[CONF_PROVIDER])

    @property
    def provider_device_info(self) -> dict[str, Any]:
        return get_device_info(self.config_entry, self.provider.name)

    async def _async_update_data(self) -> LaenderpegelData:
        session = async_get_clientsession(self.hass)
        station_id = self.config_entry.data[CONF_STATION_ID]
        try:
            punkte = await self.provider.async_get_series(session, station_id)
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Could not fetch series: {err}") from err
        if not punkte:
            raise UpdateFailed("No data points returned")
        zeitpunkt, wert = punkte[-1]
        grenze = zeitpunkt - timedelta(hours=24)
        tages_werte = [w for zeit, w in punkte if zeit >= grenze]
        data: LaenderpegelData = {
            "wert": wert,
            "zeitpunkt": zeitpunkt.isoformat(),
            "min_24h": min(tages_werte) if len(tages_werte) > 1 else None,
            "max_24h": max(tages_werte) if len(tages_werte) > 1 else None,
        }
        if self.provider.status_enabled:
            data["warnstufe"] = ""
            data["warnstufe_aktiv"] = False
            try:
                station = await self.provider.async_get_station(session, station_id)
            except aiohttp.ClientError:
                _LOGGER.debug(
                    "Status of %s:%s not available", self.provider.code, station_id, exc_info=True
                )
            else:
                if station is not None:
                    data["warnstufe"] = station.warnstufe
                    data["warnstufe_aktiv"] = station.warnstufe_aktiv
        return data
