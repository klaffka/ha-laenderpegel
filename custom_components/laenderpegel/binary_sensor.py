from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PROVIDER, CONF_STATION_ID, DOMAIN
from .coordinator import LaenderpegelCoordinator

type LaenderpegelConfigEntry = ConfigEntry[LaenderpegelCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaenderpegelConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.provider.status_enabled:
        return
    async_add_entities([LaenderpegelWarnstufeSensor(entry, coordinator)])


class LaenderpegelWarnstufeSensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:alert-circle"

    def __init__(self, entry: LaenderpegelConfigEntry, coordinator: LaenderpegelCoordinator) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Warnstufe"
        self._attr_unique_id = f"{entry.data[CONF_PROVIDER]}:{entry.data[CONF_STATION_ID]}_warnstufe"
        self._attr_device_info = coordinator.provider_device_info

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if not data or "warnstufe" not in data:
            return None
        return data.get("warnstufe_aktiv", False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        attributes: dict[str, Any] = {
            "bundesland": self.coordinator.provider.name,
            "pegel_id": self._entry.data[CONF_STATION_ID],
        }
        warnstufe = data.get("warnstufe")
        if warnstufe:
            attributes["warnstufe"] = warnstufe
        return attributes
