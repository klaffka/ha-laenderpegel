from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pegelonline.const import DOMAIN

STATION_UUID = "a26e57c9-1cb8-4fca-ba80-9e02abc81df8"

ENTRY_DATA = {
    "station_uuid": STATION_UUID,
    "station_number": "5920010",
    "station_name": "HITZACKER",
    "wasser": "ELBE",
    "fluss_km": 522.639,
    "unit": "cm",
    "forecast_unit": "cm",
    "pegelnullpunkt": {"unit": "m. ü. NN", "value": 31.82, "validFrom": "1936-11-01"},
    "has_forecast": True,
}

CURRENT_MEASUREMENT = {
    "timestamp": "2026-08-22T20:41:00+02:00",
    "value": 63.0,
    "stateMnwMhw": "normal",
    "stateNswHsw": "normal",
}


def _forecast_points() -> list[dict]:
    now = dt_util.now()
    return [
        {
            "initialized": now.isoformat(),
            "timestamp": (now + timedelta(hours=2 * i)).isoformat(),
            "value": 290.0 + i,
            "type": "forecast",
        }
        for i in range(12)
    ]


async def test_sensor_states_with_forecast(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=STATION_UUID, data=ENTRY_DATA
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.pegelonline.api.async_get_current_measurement",
            return_value=CURRENT_MEASUREMENT,
        ),
        patch(
            "custom_components.pegelonline.api.async_get_forecast",
            return_value=_forecast_points(),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    assert len(states) == 2

    wasserstand = next(state for state in states if state.name.endswith("Wasserstand"))
    assert wasserstand.state == "63.0"
    assert wasserstand.attributes["unit_of_measurement"] == "cm"
    assert wasserstand.attributes["pegelnummer"] == "5920010"
    assert wasserstand.attributes["gewaesser"] == "ELBE"
    assert wasserstand.attributes["fluss_km"] == 522.639
    assert wasserstand.attributes["status_mnw_mhw"] == "normal"
    assert wasserstand.attributes["pegelnullpunkt_m_ue_nn"] == 31.82

    vorhersage = next(state for state in states if "Vorhersage" in state.name)
    assert vorhersage.state == "301.0"
    assert vorhersage.attributes["min_24h"] == 290.0
    assert vorhersage.attributes["max_24h"] == 301.0
    assert vorhersage.attributes["anzahl_punkte_24h"] == 12


async def test_sensor_states_without_forecast(hass: HomeAssistant) -> None:
    data_without_forecast = {**ENTRY_DATA, "has_forecast": False}
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=STATION_UUID, data=data_without_forecast
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.pegelonline.api.async_get_current_measurement",
        return_value=CURRENT_MEASUREMENT,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    assert len(states) == 1
    assert states[0].state == "63.0"