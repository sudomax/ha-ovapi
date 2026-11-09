"""The Dutch Public Transport (OVapi) Home Assistant integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ALL_LINES_VALUE, CONF_LINE_NUMBER, CONF_STOP_CODE, DOMAIN
from .coordinator import OvapiDataUpdateCoordinator
from .ovapi_client import OvapiClient

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OVapi Dutch Public Transport from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    stop_code = entry.data[CONF_STOP_CODE]
    line_number = entry.data.get(CONF_LINE_NUMBER, ALL_LINES_VALUE)

    session = async_get_clientsession(hass)
    client = OvapiClient(session=session)

    coordinator = OvapiDataUpdateCoordinator(
        hass=hass,
        client=client,
        tpc=stop_code,
        line_filter=line_number,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an OVapi config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: OvapiDataUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.close()

    return unload_ok
