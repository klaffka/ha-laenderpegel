from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.laenderpegel import diagnostics
from custom_components.laenderpegel.const import DOMAIN
from custom_components.laenderpegel.models import GaugeStation
from custom_components.laenderpegel.providers import mv, rp, th

MV_ENTRY_DATA = {
    "provider": "mv",
    "station_id": "04416.1",
    "station_name": "Kladrum",
    "wasser": "Warnow",
    "pegelnullpunkt": 0.0,
}

RP_ENTRY_DATA = {
    "provider": "rp",
    "station_id": "26600128",
    "station_name": "Kronenburger See",
    "wasser": "Kyll",
    "pegelnullpunkt": 489.8,
}

TH_ENTRY_DATA = {
    "provider": "th",
    "station_id": "251680",
    "station_name": "Autenhausen",
    "wasser": "Kreck",
    "pegelnullpunkt": None,
}


def _mv_points() -> list:
    now = dt_util.now()
    return [
        (now - timedelta(hours=48), 12.0),
        (now - timedelta(hours=12), 14.0),
        (now - timedelta(hours=6), 16.0),
        (now - timedelta(minutes=15), 15.0),
    ]


def _rp_single_point() -> list:
    return [(dt_util.now(), 483.54)]


def _fake_series(series: list):
    async def _get(self, session, station_id):
        return series

    return _get


def _fake_station(station: GaugeStation | None):
    async def _get(self, session, station_id):
        return station

    return _get


async def test_sensor_cm_provider_with_24h_range(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="mv:04416.1", data=MV_ENTRY_DATA)
    entry.add_to_hass(hass)
    with patch.object(mv.Provider, "async_get_series", new=_fake_series(_mv_points())):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    assert len(states) == 1
    state = states[0]
    assert state.state == "15.0"
    assert state.attributes["unit_of_measurement"] == "cm"
    assert state.attributes["bundesland"] == "Mecklenburg-Vorpommern"
    assert state.attributes["pegel_id"] == "04416.1"
    assert state.attributes["gewaesser"] == "Warnow"
    assert state.attributes["min_24h"] == 14.0
    assert state.attributes["max_24h"] == 16.0
    assert state.attributes["pegelnullpunkt"] == 0.0


async def test_sensor_m_provider_single_point(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="rp:26600128", data=RP_ENTRY_DATA)
    entry.add_to_hass(hass)
    with patch.object(rp.Provider, "async_get_series", new=_fake_series(_rp_single_point())):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    assert len(states) == 1
    state = states[0]
    assert state.state == "483.54"
    assert state.attributes["unit_of_measurement"] == "m"
    assert "min_24h" not in state.attributes
    assert "max_24h" not in state.attributes


async def test_binary_sensor_warnstufe_active(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="th:251680", data=TH_ENTRY_DATA)
    entry.add_to_hass(hass)
    station = GaugeStation(
        id="251680",
        name="Autenhausen",
        wasser="Kreck",
        stand="23:45",
        wert="119",
        warnstufe="Meldestufe 1",
        warnstufe_aktiv=True,
    )
    with (
        patch.object(th.Provider, "async_get_series", new=_fake_series([(dt_util.now(), 119.0)])),
        patch.object(th.Provider, "async_get_station", new=_fake_station(station)),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    sensor_states = hass.states.async_all("sensor")
    assert len(sensor_states) == 1
    assert sensor_states[0].state == "119.0"

    binary_states = hass.states.async_all("binary_sensor")
    assert len(binary_states) == 1
    assert binary_states[0].state == "on"
    assert binary_states[0].attributes["warnstufe"] == "Meldestufe 1"
    assert binary_states[0].attributes["bundesland"] == "Thüringen"


async def test_binary_sensor_warnstufe_normal(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="th:251680", data=TH_ENTRY_DATA)
    entry.add_to_hass(hass)
    station = GaugeStation(
        id="251680", name="Autenhausen", wasser="Kreck", stand="23:45", wert="119"
    )
    with (
        patch.object(th.Provider, "async_get_series", new=_fake_series([(dt_util.now(), 119.0)])),
        patch.object(th.Provider, "async_get_station", new=_fake_station(station)),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    binary_states = hass.states.async_all("binary_sensor")
    assert len(binary_states) == 1
    assert binary_states[0].state == "off"


async def test_diagnostics(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="mv:04416.1", data=MV_ENTRY_DATA)
    entry.add_to_hass(hass)
    with patch.object(mv.Provider, "async_get_series", new=_fake_series(_mv_points())):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await diagnostics.async_get_config_entry_diagnostics(hass, entry)
    assert result["entry"]["provider"] == "mv"
    assert result["entry"]["station_id"] == "04416.1"
    assert result["provider"]["code"] == "mv"
    assert result["provider"]["name"] == "Mecklenburg-Vorpommern"
    assert result["coordinator"]["last_update_success"] is True
    assert result["coordinator"]["data"]["wert"] == 15.0
    assert result["coordinator"]["data"]["min_24h"] == 14.0
    entity_ids = [e["entity_id"] for e in result["entities"]]
    assert any(e.startswith("sensor.") for e in entity_ids)