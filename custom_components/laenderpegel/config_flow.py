from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_GAUGE_ZERO,
    CONF_PROVIDER,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_WASSER,
    DOMAIN,
)
from .models import GaugeStation
from .providers import get_provider, provider_names

_LOGGER = logging.getLogger(__name__)


def _station_option_label(station: GaugeStation) -> str:
    wert = station.wert or ""
    wert_text = f" – {wert}" if wert else ""
    return f"{station.name} [{station.id}]{wert_text}"


class LaenderpegelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    _provider: Any = None
    _stationen: list[GaugeStation] | None = None

    def _async_show_form(self, step_id: str, schema: vol.Schema, errors: dict[str, str] | None = None, placeholders: dict[str, str] | None = None) -> FlowResult:
        return self.async_show_form(
            step_id=step_id, data_schema=schema, errors=errors or {}, description_placeholders=placeholders or {}
        )

    @staticmethod
    def _select(key: str, options: list[str]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(key): SelectSelector(
                    SelectSelectorConfig(
                        options=[{"value": option, "label": option} for option in options],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

    @staticmethod
    def _bundesland_select() -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("bundesland"): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": code, "label": name} for code, name in provider_names()
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

    @staticmethod
    def _station_select(options: list[GaugeStation]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("station"): SelectSelector(
                    SelectSelectorConfig(
                        options=[{"value": s.id, "label": _station_option_label(s)} for s in options],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

    async def _async_finish(self, station: GaugeStation) -> FlowResult:
        for entry in self._async_current_entries():
            if (
                entry.data.get(CONF_PROVIDER) == self._provider.code
                and entry.data.get(CONF_STATION_ID) == station.id
            ):
                return self.async_abort(reason="already_configured")
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            punkte = await self._provider.async_get_series(session, station.id)
        except aiohttp.ClientError:
            _LOGGER.warning("Could not fetch data for %s:%s", self._provider.code, station.id, exc_info=True)
            return self.async_abort(reason="no_data")
        if not punkte:
            return self.async_abort(reason="no_data")
        gauge_zero = None
        try:
            gauge_zero = await self._provider.async_get_gauge_zero(session, station.id)
        except aiohttp.ClientError:
            _LOGGER.debug("Gauge zero not available for %s:%s", self._provider.code, station.id, exc_info=True)
        data: dict[str, Any] = {
            CONF_PROVIDER: self._provider.code,
            CONF_STATION_ID: station.id,
            CONF_STATION_NAME: station.name,
            CONF_WASSER: station.wasser,
            CONF_GAUGE_ZERO: gauge_zero,
        }
        return self.async_create_entry(title=f"{station.name} ({station.wasser})", data=data)

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._provider = get_provider(user_input["bundesland"])
            try:
                session = aiohttp_client.async_get_clientsession(self.hass)
                self._stationen = await self._provider.async_get_stations(session)
            except aiohttp.ClientError as err:
                _LOGGER.warning("%s not reachable: %s", self._provider.name, err)
                return self._async_show_form(
                    "user", self._bundesland_select(), {"base": "cannot_connect"}
                )
            if not self._stationen:
                return self._async_show_form(
                    "user", self._bundesland_select(), {"base": "no_stations"}
                )
            waesser = sorted({s.wasser for s in self._stationen if s.wasser})
            if len(waesser) == 1 and len(self._stationen) == 1:
                return await self._async_finish(self._stationen[0])
            self.context["bundesland"] = self._provider.code
            return self._async_show_form(
                "wasser", self._select("wasser", waesser), placeholders={"bundesland": self._provider.name}
            )
        return self._async_show_form("user", self._bundesland_select(), errors)

    async def async_step_wasser(self, user_input: dict | None = None) -> FlowResult:
        assert self._provider is not None and self._stationen is not None
        if user_input is not None:
            stationen = [s for s in self._stationen if s.wasser == user_input["wasser"]]
            if not stationen:
                return self._async_show_form(
                    "wasser",
                    self._select("wasser", sorted({s.wasser for s in self._stationen})),
                    {"base": "unknown"},
                    {"bundesland": self._provider.name},
                )
            if len(stationen) == 1:
                return await self._async_finish(stationen[0])
            self.context["wasser"] = user_input["wasser"]
            return self._async_show_form(
                "station",
                self._station_select(stationen),
                placeholders={"bundesland": self._provider.name, "wasser": user_input["wasser"]},
            )
        waesser = sorted({s.wasser for s in self._stationen})
        return self._async_show_form(
            "wasser", self._select("wasser", waesser), placeholders={"bundesland": self._provider.name}
        )

    async def async_step_station(self, user_input: dict | None = None) -> FlowResult:
        assert self._provider is not None and self._stationen is not None
        if user_input is not None:
            station = next((s for s in self._stationen if s.id == user_input["station"]), None)
            if station is not None:
                return await self._async_finish(station)
        waesser = self.context.get("wasser")
        stationen = [s for s in self._stationen if s.wasser == waesser]
        return self._async_show_form(
            "station",
            self._station_select(stationen),
            placeholders={"bundesland": self._provider.name, "wasser": waesser},
        )
