"""Tests for integration initialization and unloading."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.ovapi import async_setup_entry, async_unload_entry
from custom_components.ovapi.const import CONF_LINE_NUMBER, CONF_STOP_CODE, DOMAIN
from custom_components.ovapi.ovapi_client.models import OvapiStop, OvapiStopDepartures


@pytest.mark.asyncio
async def test_async_setup_and_unload_entry():
    """Test full setup and unload lifecycle."""
    hass = HomeAssistant()
    entry = ConfigEntry(
        entry_id="test_entry_1",
        data={CONF_STOP_CODE: "30005029", CONF_LINE_NUMBER: "26"},
    )

    mock_stop = OvapiStop(tpc="30005029", name="Centraal Station", town="Amsterdam")
    mock_data = OvapiStopDepartures(stop=mock_stop, departures=[])

    with (
        patch(
            "custom_components.ovapi.coordinator.OvapiClient.get_stop_departures",
            new=AsyncMock(return_value=mock_data),
        ),
        patch(
            "custom_components.ovapi.coordinator.OvapiClient.close",
            new=AsyncMock(),
        ) as mock_close,
    ):
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        setup_result = await async_setup_entry(hass, entry)
        assert setup_result is True
        assert entry.entry_id in hass.data[DOMAIN]

        coordinator = hass.data[DOMAIN][entry.entry_id]
        # Empty departures -> smart adaptive polling sets dormant interval (900s)
        assert coordinator.update_interval.total_seconds() == 900

        unload_result = await async_unload_entry(hass, entry)
        assert unload_result is True
        assert entry.entry_id not in hass.data[DOMAIN]
        mock_close.assert_awaited_once()
