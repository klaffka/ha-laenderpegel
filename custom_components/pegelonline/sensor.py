from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_FORECAST_UNIT,
    CONF_GAUGE_ZERO,
    CONF_HAS_FORECAST,
    CONF_KM,
    CONF_STATION_NUMBER,
    CONF_STATION_UUID,
    CONF_UNIT,
    CONF_WASSER,
    DOMAIN,
    get_device_info,
)
from .coordinator import PegelonlineCoordinator

type PegelonlineConfigEntry = ConfigEntry[PegelonlineCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PegelonlineConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [PegelonlineWasserstandSensor(entry, coordinator)]
    if entry.data.get(CONF_HAS_FORECAST):
        entities.append(PegelonlineVorhersageSensor(entry, coordinator))
    async_add_entities(entities)


class PegelonlineWasserstandSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:watersource"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: PegelonlineConfigEntry, coordinator: PegelonlineCoordinator) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Wasserstand"
        self._attr_unique_id = f"{entry.data[CONF_STATION_UUID]}-w"
        self._attr_native_unit_of_measurement = entry.data.get(CONF_UNIT)
        self._attr_device_info = get_device_info(entry)

    @property
    def native_value(self) -> float | int | None:
        messwert = (self.coordinator.data or {}).get("messwert")
        return messwert.get("value") if messwert else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        messwert = (self.coordinator.data or {}).get("messwert") or {}
        attributes: dict[str, Any] = {
            "pegelnummer": self._entry.data[CONF_STATION_NUMBER],
            "gewaesser": self._entry.data[CONF_WASSER],
            "fluss_km": self._entry.data[CONF_KM],
            "status_mnw_mhw": messwert.get("stateMnwMhw"),
            "status_nsw_hsw": messwert.get("stateNswHsw"),
            "messzeitpunkt": messwert.get("timestamp"),
        }
        gauge_zero = self._entry.data.get(CONF_GAUGE_ZERO)
        if gauge_zero:
            attributes["pegelnullpunkt_m_ue_nn"] = gauge_zero.get("value")
            attributes["pegelnullpunkt_gueltig_ab"] = gauge_zero.get("validFrom")
        return {key: value for key, value in attributes.items() if value is not None}


class PegelonlineVorhersageSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:water"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: PegelonlineConfigEntry, coordinator: PegelonlineCoordinator) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Vorhersage max 24 h"
        self._attr_unique_id = f"{entry.data[CONF_STATION_UUID]}-wv"
        self._attr_native_unit_of_measurement = entry.data.get(CONF_FORECAST_UNIT)
        self._attr_device_info = get_device_info(entry)

    @property
    def native_value(self) -> float | int | None:
        vorhersage = (self.coordinator.data or {}).get("vorhersage")
        return vorhersage.get("max_24h") if vorhersage else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        vorhersage = (self.coordinator.data or {}).get("vorhersage")
        if not vorhersage:
            return {}
        return {
            "initialisiert": vorhersage.get("initialisiert"),
            "horizont_ende": vorhersage.get("ende"),
            "min_24h": vorhersage.get("min_24h"),
            "max_24h": vorhersage.get("max_24h"),
            "anzahl_punkte_24h": vorhersage.get("anzahl_punkte"),
        }
