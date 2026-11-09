"""Tests for OvapiDataUpdateCoordinator."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.ovapi.const import (
    BACKOFF_INTERVALS,
    POLL_INTERVAL_ACTIVE,
    POLL_INTERVAL_DORMANT,
    POLL_INTERVAL_FAR,
)
from custom_components.ovapi.coordinator import OvapiDataUpdateCoordinator
from custom_components.ovapi.ovapi_client.exceptions import OvapiConnectionError
from custom_components.ovapi.ovapi_client.models import (
    AMSTERDAM_TZ,
    OvapiDeparture,
    OvapiStop,
    OvapiStopDepartures,
)


@pytest.mark.asyncio
async def test_coordinator_successful_update():
    """Test coordinator updates data successfully."""
    hass = HomeAssistant()
    mock_client = AsyncMock()

    mock_stop = OvapiStop(tpc="30005029", name="Centraal Station", town="Amsterdam")
    expected_data = OvapiStopDepartures(stop=mock_stop, departures=[])
    mock_client.get_stop_departures.return_value = expected_data

    coordinator = OvapiDataUpdateCoordinator(
        hass=hass,
        client=mock_client,
        tpc="30005029",
    )

    await coordinator.async_config_entry_first_refresh()

    assert coordinator.data == expected_data
    assert coordinator.stop_name == "Centraal Station"
    assert coordinator.tpc == "30005029"
    assert coordinator.is_stale is False
    mock_client.get_stop_departures.assert_awaited_once_with("30005029")


@pytest.mark.asyncio
async def test_coordinator_adaptive_polling_intervals():
    """Test coordinator adjusts interval based on departure proximity."""
    hass = HomeAssistant()
    mock_client = AsyncMock()
    mock_stop = OvapiStop(tpc="30005029", name="Centraal Station", town="Amsterdam")
    now = datetime.now(AMSTERDAM_TZ)

    # 1. Imminent departure in 10 minutes -> ACTIVE (30s)
    dep_soon = OvapiDeparture(
        journey_id="1",
        line_number="26",
        destination="IJburg",
        target_departure=now + timedelta(minutes=10),
    )
    mock_client.get_stop_departures.return_value = OvapiStopDepartures(
        stop=mock_stop, departures=[dep_soon]
    )

    coordinator = OvapiDataUpdateCoordinator(
        hass=hass,
        client=mock_client,
        tpc="30005029",
    )
    await coordinator.async_config_entry_first_refresh()
    assert coordinator.update_interval.total_seconds() == POLL_INTERVAL_ACTIVE

    # 2. Sub-30s departure in 12 seconds -> schedules prompt rollover refresh
    dep_very_soon = OvapiDeparture(
        journey_id="1b",
        line_number="26",
        destination="IJburg",
        target_departure=datetime.now(AMSTERDAM_TZ) + timedelta(seconds=12),
    )
    mock_client.get_stop_departures.return_value = OvapiStopDepartures(
        stop=mock_stop, departures=[dep_very_soon]
    )
    await coordinator._async_update_data()
    assert 5 <= coordinator.update_interval.total_seconds() <= 14

    # 3. Far departure in 90 minutes -> FAR (300s)
    dep_far = OvapiDeparture(
        journey_id="2",
        line_number="26",
        destination="IJburg",
        target_departure=now + timedelta(minutes=90),
    )
    mock_client.get_stop_departures.return_value = OvapiStopDepartures(
        stop=mock_stop, departures=[dep_far]
    )
    await coordinator._async_update_data()
    assert coordinator.update_interval.total_seconds() == POLL_INTERVAL_FAR

    # 4. No upcoming departures -> DORMANT (900s)
    mock_client.get_stop_departures.return_value = OvapiStopDepartures(
        stop=mock_stop, departures=[]
    )
    await coordinator._async_update_data()
    assert coordinator.update_interval.total_seconds() == POLL_INTERVAL_DORMANT


@pytest.mark.asyncio
async def test_coordinator_grace_period_and_backoff():
    """Test coordinator tolerates up to 5 failures with backoff before raising UpdateFailed."""
    hass = HomeAssistant()
    mock_client = AsyncMock()
    mock_stop = OvapiStop(tpc="30005029", name="Centraal Station", town="Amsterdam")
    valid_data = OvapiStopDepartures(stop=mock_stop, departures=[])

    mock_client.get_stop_departures.return_value = valid_data
    coordinator = OvapiDataUpdateCoordinator(
        hass=hass,
        client=mock_client,
        tpc="30005029",
    )
    await coordinator.async_config_entry_first_refresh()
    assert coordinator.is_stale is False

    mock_client.get_stop_departures.side_effect = OvapiConnectionError("Server 500")

    for attempt, expected_backoff in enumerate(BACKOFF_INTERVALS, start=1):
        data = await coordinator._async_update_data()
        assert data == valid_data
        assert coordinator.is_stale is True
        assert coordinator.consecutive_failures == attempt
        assert coordinator.update_interval.total_seconds() == expected_backoff

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.consecutive_failures == 6


@pytest.mark.asyncio
async def test_coordinator_initial_failure():
    """Test coordinator raises UpdateFailed immediately on first refresh when no data exists."""
    hass = HomeAssistant()
    mock_client = AsyncMock()
    mock_client.get_stop_departures.side_effect = OvapiConnectionError("Network down")

    coordinator = OvapiDataUpdateCoordinator(
        hass=hass,
        client=mock_client,
        tpc="30005029",
    )

    with pytest.raises(UpdateFailed):
        await coordinator.async_config_entry_first_refresh()
    assert coordinator.is_stale is True
