from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components import laenderpegel, pegelonline


@pytest.mark.parametrize("integration", [laenderpegel, pegelonline])
async def test_successful_unload_removes_runtime_data(
    hass: HomeAssistant, integration
) -> None:
    entry = MockConfigEntry(domain=integration.DOMAIN)
    coordinator = object()
    hass.data[integration.DOMAIN] = {entry.entry_id: coordinator}

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=True),
    ):
        assert await integration.async_unload_entry(hass, entry)

    assert entry.entry_id not in hass.data[integration.DOMAIN]


@pytest.mark.parametrize("integration", [laenderpegel, pegelonline])
async def test_failed_unload_keeps_runtime_data(
    hass: HomeAssistant, integration
) -> None:
    entry = MockConfigEntry(domain=integration.DOMAIN)
    coordinator = object()
    hass.data[integration.DOMAIN] = {entry.entry_id: coordinator}

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=False),
    ):
        assert not await integration.async_unload_entry(hass, entry)

    assert hass.data[integration.DOMAIN][entry.entry_id] is coordinator
