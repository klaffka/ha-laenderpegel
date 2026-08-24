from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import LaenderpegelCoordinator

type LaenderpegelConfigEntry = ConfigEntry[LaenderpegelCoordinator]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: LaenderpegelConfigEntry
) -> dict[str, Any]:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entity_registry = er.async_get(hass)
    entitaeten = [
        {
            "entity_id": entity.entity_id,
            "unique_id": entity.unique_id,
            "original_name": entity.original_name,
            "disabled_by": entity.disabled_by,
        }
        for entity in er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    ]
    return {
        "entry": dict(config_entry.data),
        "provider": {
            "code": coordinator.provider.code,
            "name": coordinator.provider.name,
            "unit": coordinator.provider.unit,
            "has_history": coordinator.provider.has_history,
            "status_enabled": coordinator.provider.status_enabled,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
            "data": coordinator.data,
        },
        "entities": entitaeten,
    }
