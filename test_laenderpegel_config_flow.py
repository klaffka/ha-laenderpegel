from datetime import datetime
from unittest.mock import AsyncMock, patch

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.laenderpegel.const import DOMAIN
from custom_components.laenderpegel.models import GaugeStation
from custom_components.laenderpegel.providers import mv

STATIONEN = [
    GaugeStation(id="04416.1", name="Kladrum", wasser="Warnow", stand="07:00", wert="15"),
    GaugeStation(id="01012.1", name="Schwaan", wasser="Warnow", stand="07:00", wert="52"),
    GaugeStation(id="05011.1", name="Greifswald", wasser="Elbe", stand="07:00", wert="210"),
]


async def _start_flow(hass: HomeAssistant) -> dict:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"bundesland": "mv"}
    )


SERIE = [(datetime(2026, 8, 24, 7, 0), 15.0)]


async def test_full_flow(hass: HomeAssistant) -> None:
    with (
        patch.object(mv.Provider, "async_get_stations", new=AsyncMock(return_value=STATIONEN)),
        patch.object(mv.Provider, "async_get_series", new=AsyncMock(return_value=SERIE)),
        patch.object(mv.Provider, "async_get_gauge_zero", new=AsyncMock(return_value=0.0)),
    ):
        result = await _start_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "wasser"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"wasser": "Warnow"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"station": "04416.1"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entry = result["result"]
        assert entry.title == "Kladrum (Warnow)"
        assert entry.data["provider"] == "mv"
        assert entry.data["station_id"] == "04416.1"
        assert entry.data["station_name"] == "Kladrum"
        assert entry.data["wasser"] == "Warnow"
        assert entry.data["pegelnullpunkt"] == 0.0


async def test_single_station_wasser_skips_station_step(hass: HomeAssistant) -> None:
    with (
        patch.object(mv.Provider, "async_get_stations", new=AsyncMock(return_value=STATIONEN)),
        patch.object(mv.Provider, "async_get_series", new=AsyncMock(return_value=SERIE)),
        patch.object(mv.Provider, "async_get_gauge_zero", new=AsyncMock(return_value=None)),
    ):
        result = await _start_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"wasser": "Elbe"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].data["station_id"] == "05011.1"


async def test_duplicate_station_aborts(hass: HomeAssistant) -> None:
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            "provider": "mv",
            "station_id": "04416.1",
            "station_name": "Kladrum",
            "wasser": "Warnow",
        },
    )
    existing.add_to_hass(hass)
    with (
        patch.object(mv.Provider, "async_get_stations", new=AsyncMock(return_value=STATIONEN)),
        patch.object(mv.Provider, "async_get_gauge_zero", new=AsyncMock(return_value=0.0)),
    ):
        result = await _start_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"wasser": "Warnow"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"station": "04416.1"}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_provider_not_reachable_shows_error(hass: HomeAssistant) -> None:
    with patch.object(
        mv.Provider, "async_get_stations", new=AsyncMock(side_effect=aiohttp.ClientError("down"))
    ):
        result = await _start_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_station_without_data_aborts(hass: HomeAssistant) -> None:
    with (
        patch.object(mv.Provider, "async_get_stations", new=AsyncMock(return_value=STATIONEN)),
        patch.object(mv.Provider, "async_get_series", new=AsyncMock(return_value=[])),
    ):
        result = await _start_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"wasser": "Warnow"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"station": "04416.1"}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_data"