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

from . import api
from .const import (
    CONF_FORECAST_UNIT,
    CONF_GAUGE_ZERO,
    CONF_HAS_FORECAST,
    CONF_KM,
    CONF_STATION_NAME,
    CONF_STATION_NUMBER,
    CONF_STATION_UUID,
    CONF_UNIT,
    CONF_WASSER,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _station_option_label(station: dict) -> str:
    km = station.get("km")
    km_text = f" (km {km})" if km is not None else ""
    return f"{station.get('number', '')} {station['longname']}{km_text}".strip()


class PegelonlineConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    _stations: list[dict] | None = None

    async def _async_get_all_stations(self) -> list[dict]:
        session = aiohttp_client.async_get_clientsession(self.hass)
        return await api.async_get_stations(session)

    async def _async_fetch_all_stations(self) -> bool:
        try:
            self._stations = await self._async_get_all_stations()
        except aiohttp.ClientError as err:
            _LOGGER.warning("PEGELONLINE API not reachable: %s", err)
            return False
        return True

    def _async_show_user_form(self, errors: dict[str, str]) -> FlowResult:
        waesser = sorted({s["water"]["longname"] for s in self._stations})
        schema = vol.Schema(
            {
                vol.Required("wasser"): SelectSelector(
                        SelectSelectorConfig(
                        options=[{"value": w, "label": w} for w in waesser],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def _async_finish(self, station: dict) -> FlowResult:
        for entry in self._async_current_entries():
            if entry.data.get(CONF_STATION_UUID) == station["uuid"]:
                return self.async_abort(reason="already_configured")
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            details = await api.async_get_station(session, station["uuid"])
        except aiohttp.ClientError as err:
            _LOGGER.warning("PEGELONLINE API not reachable: %s", err)
            return self.async_abort(reason="cannot_connect")
        zeitreihen = details.get("timeseries", [])
        w_ts = next((ts for ts in zeitreihen if ts.get("shortname") == "W"), None)
        wv_ts = next((ts for ts in zeitreihen if ts.get("shortname") == "WV"), None)
        gauge_zero = w_ts.get("gaugeZero") if w_ts else None
        unit_w = w_ts.get("unit", "cm") if w_ts else "cm"
        data: dict[str, Any] = {
            CONF_STATION_UUID: station["uuid"],
            CONF_STATION_NUMBER: station.get("number", ""),
            CONF_STATION_NAME: station["longname"],
            CONF_WASSER: station["water"]["longname"],
            CONF_KM: station.get("km"),
            CONF_UNIT: unit_w,
            CONF_FORECAST_UNIT: (wv_ts.get("unit", unit_w) if wv_ts else unit_w),
            CONF_GAUGE_ZERO: gauge_zero,
            CONF_HAS_FORECAST: wv_ts is not None,
        }
        return self.async_create_entry(
            title=f"{station['longname']} ({station['water']['longname']})", data=data
        )

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if self._stations is None and not await self._async_fetch_all_stations():
                return self._async_show_user_form({"base": "cannot_connect"})
            assert self._stations is not None
            waesser = user_input["wasser"]
            stationen = [s for s in self._stations if s["water"]["longname"] == waesser]
            if not stationen:
                return self._async_show_user_form({"base": "unknown"})
            if len(stationen) == 1:
                return await self._async_finish(stationen[0])
            self.context["wasser"] = waesser
            stationen = sorted(stationen, key=lambda s: (s.get("km") is None, s.get("km") or 0))
            schema = vol.Schema(
                {
                    vol.Required("station"): SelectSelector(
                            SelectSelectorConfig(
                            options=[
                                {"value": s["uuid"], "label": _station_option_label(s)}
                                for s in stationen
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            )
            return self.async_show_form(
                step_id="station",
                data_schema=schema,
                description_placeholders={"wasser": waesser},
            )
        if not await self._async_fetch_all_stations():
            errors["base"] = "cannot_connect"
        return self._async_show_user_form(errors)

    async def async_step_station(self, user_input: dict | None = None) -> FlowResult:
        assert self._stations is not None
        if user_input is not None:
            station = next(
                (s for s in self._stations if s["uuid"] == user_input["station"]), None
            )
            if station is not None:
                return await self._async_finish(station)
        waesser = self.context.get("wasser")
        stationen = [s for s in self._stations if s["water"]["longname"] == waesser]
        stationen = sorted(stationen, key=lambda s: (s.get("km") is None, s.get("km") or 0))
        schema = vol.Schema(
            {
                vol.Required("station"): SelectSelector(
                        SelectSelectorConfig(
                        options=[
                            {"value": s["uuid"], "label": _station_option_label(s)}
                            for s in stationen
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="station",
            data_schema=schema,
            description_placeholders={"wasser": waesser},
        )
