from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pegelonline.const import DOMAIN

STATIONS = [
    {
        "uuid": "uuid-trier-up",
        "number": "26500100",
        "shortname": "TRIER UP",
        "longname": "TRIER UP",
        "km": 195.3,
        "water": {"shortname": "MOSEL", "longname": "MOSEL"},
    },
    {
        "uuid": "uuid-trier-op",
        "number": "26500080",
        "shortname": "TRIER OP",
        "longname": "TRIER OP",
        "km": 196.2,
        "water": {"shortname": "MOSEL", "longname": "MOSEL"},
    },
    {
        "uuid": "uuid-koblenz",
        "number": "25900700",
        "shortname": "KOBLENZ",
        "longname": "KOBLENZ",
        "km": 591.49,
        "water": {"shortname": "RHEIN", "longname": "RHEIN"},
    },
]

STATION_DETAILS = {
    "uuid": "uuid-trier-up",
    "longname": "TRIER UP",
    "timeseries": [
        {
            "shortname": "W",
            "unit": "cm",
            "gaugeZero": {"unit": "m. ü. NN", "value": 81.23, "validFrom": "1992-01-01"},
        },
        {"shortname": "WV", "unit": "cm"},
    ],
}


async def test_full_flow(hass: HomeAssistant) -> None:
    with (
        patch(
            "custom_components.pegelonline.api.async_get_stations",
            return_value=STATIONS,
        ),
        patch(
            "custom_components.pegelonline.api.async_get_station",
            return_value=STATION_DETAILS,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"wasser": "MOSEL"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "station"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"station": "uuid-trier-up"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entry = result["result"]
        assert entry.title == "TRIER UP (MOSEL)"
        assert entry.data["station_uuid"] == "uuid-trier-up"
        assert entry.data["station_number"] == "26500100"
        assert entry.data["wasser"] == "MOSEL"
        assert entry.data["fluss_km"] == 195.3
        assert entry.data["unit"] == "cm"
        assert entry.data["forecast_unit"] == "cm"
        assert entry.data["has_forecast"] is True
        assert entry.data["pegelnullpunkt"]["value"] == 81.23


async def test_single_station_wasser_skips_station_step(hass: HomeAssistant) -> None:
    with (
        patch(
            "custom_components.pegelonline.api.async_get_stations",
            return_value=STATIONS,
        ),
        patch(
            "custom_components.pegelonline.api.async_get_station",
            return_value=STATION_DETAILS,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"wasser": "RHEIN"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].data["station_uuid"] == "uuid-koblenz"


async def test_duplicate_station_aborts(hass: HomeAssistant) -> None:
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            "station_uuid": "uuid-trier-up",
            "station_name": "TRIER UP",
            "wasser": "MOSEL",
        },
    )
    existing.add_to_hass(hass)
    with patch(
        "custom_components.pegelonline.api.async_get_stations",
        return_value=STATIONS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"wasser": "MOSEL"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"station": "uuid-trier-up"}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"