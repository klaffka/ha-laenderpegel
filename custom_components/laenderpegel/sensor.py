from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_GAUGE_ZERO, CONF_PROVIDER, CONF_STATION_ID, CONF_WASSER, DOMAIN
from .coordinator import LaenderpegelCoordinator

type LaenderpegelConfigEntry = ConfigEntry[LaenderpegelCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaenderpegelConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LaenderpegelWasserstandSensor(entry, coordinator)])


class LaenderpegelWasserstandSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:watersource"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: LaenderpegelConfigEntry, coordinator: LaenderpegelCoordinator) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Wasserstand"
        self._attr_unique_id = f"{entry.data[CONF_PROVIDER]}:{entry.data[CONF_STATION_ID]}"
        self._attr_native_unit_of_measurement = coordinator.provider.unit
        self._attr_device_info = coordinator.provider_device_info

    @property
    def native_value(self) -> float | int | None:
        data = self.coordinator.data
        return data.get("wert") if data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        attributes: dict[str, Any] = {
            "bundesland": self.coordinator.provider.name,
            "pegel_id": self._entry.data[CONF_STATION_ID],
            "gewaesser": self._entry.data[CONF_WASSER],
            "messzeitpunkt": data.get("zeitpunkt"),
            "min_24h": data.get("min_24h"),
            "max_24h": data.get("max_24h"),
        }
        if self._entry.data.get(CONF_GAUGE_ZERO) is not None:
            attributes["pegelnullpunkt"] = self._entry.data[CONF_GAUGE_ZERO]
        return {key: value for key, value in attributes.items() if value is not None}
