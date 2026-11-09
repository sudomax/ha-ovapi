"""Sensor platform for the Dutch Public Transport (OVapi) integration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ALL_LINES_VALUE,
    ATTR_DELAY_MINUTES,
    ATTR_DESTINATION,
    ATTR_EXPECTED_DEPARTURE,
    ATTR_LINE_NUMBER,
    ATTR_OPERATOR,
    ATTR_PLATFORM,
    ATTR_SCHEDULED_DEPARTURE,
    ATTR_STALE,
    ATTR_STATUS,
    ATTR_STOP_NAME,
    ATTR_STOP_TPC,
    ATTR_SUMMARY,
    ATTR_TRANSPORT_TYPE,
    CONF_LINE_NUMBER,
    CONF_STOP_CODE,
    DEPARTURES_COUNT,
    DOMAIN,
)
from .coordinator import OvapiDataUpdateCoordinator
from .ovapi_client import OvapiDeparture


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the 3 OVapi departure sensor entities for a config entry."""
    coordinator: OvapiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    stop_code = entry.data[CONF_STOP_CODE]
    line_number = entry.data.get(CONF_LINE_NUMBER, ALL_LINES_VALUE)

    async_add_entities(
        [
            OvapiDepartureSensor(
                coordinator=coordinator,
                entry=entry,
                stop_code=stop_code,
                line_number=line_number,
                departure_index=i,
            )
            for i in range(DEPARTURES_COUNT)
        ]
    )


def _get_icon_for_transport(transport_type: str | None) -> str:
    """Return an appropriate MDI icon based on public transport type."""
    if not transport_type:
        return "mdi:transit-connection-variant"
    tt = transport_type.upper()
    if "TRAM" in tt:
        return "mdi:tram"
    if "METRO" in tt or "SUBWAY" in tt:
        return "mdi:subway-variant"
    if "FERRY" in tt or "BOAT" in tt:
        return "mdi:ferry"
    if "TRAIN" in tt or "RAIL" in tt:
        return "mdi:train"
    if "BUS" in tt:
        return "mdi:bus"
    return "mdi:transit-connection-variant"


class OvapiDepartureSensor(CoordinatorEntity[OvapiDataUpdateCoordinator], SensorEntity):
    """Sensor reporting the timestamp and details of an upcoming transit departure."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: OvapiDataUpdateCoordinator,
        entry: ConfigEntry,
        stop_code: str,
        line_number: str | list[str],
        departure_index: int = 0,
    ) -> None:
        """Initialize the departure sensor."""
        super().__init__(coordinator)
        self._stop_code = stop_code
        self._line_number = line_number
        self._departure_index = departure_index

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, stop_code)},
            name=coordinator.stop_name,
            manufacturer="OVapi",
            model="Transit Stop (TimingPoint)",
            entry_type=DeviceEntryType.SERVICE,
        )

        is_all_lines = not line_number or line_number == ALL_LINES_VALUE
        idx = departure_index + 1

        if departure_index == 0:
            self._attr_unique_id = f"{entry.entry_id}_departure"
            if is_all_lines:
                self._attr_translation_key = "next_departure"
            elif isinstance(line_number, list):
                self._attr_translation_key = "lines_next_departure"
                self._attr_translation_placeholders = {"lines": ", ".join(line_number)}
            else:
                self._attr_translation_key = "line_next_departure"
                self._attr_translation_placeholders = {"line": str(line_number)}
        else:
            self._attr_unique_id = f"{entry.entry_id}_departure_{idx}"
            if is_all_lines:
                self._attr_translation_key = "departure"
                self._attr_translation_placeholders = {"index": str(idx)}
            elif isinstance(line_number, list):
                self._attr_translation_key = "lines_departure"
                self._attr_translation_placeholders = {
                    "lines": ", ".join(line_number),
                    "index": str(idx),
                }
            else:
                self._attr_translation_key = "line_departure"
                self._attr_translation_placeholders = {
                    "line": str(line_number),
                    "index": str(idx),
                }

    def _get_matching_departures(self) -> list[OvapiDeparture]:
        """Return departures matching this sensor's line configuration."""
        if not self.coordinator.data:
            return []

        if not self._line_number or self._line_number == ALL_LINES_VALUE:
            line_filter: str | list[str] | None = None
        elif isinstance(self._line_number, str):
            line_filter = self._line_number
        else:
            lines = [item for item in self._line_number if item != ALL_LINES_VALUE]
            line_filter = lines if lines else None

        return self.coordinator.data.get_departures(
            line_number=line_filter,
            exclude_passed=True,
        )

    def _get_current_departure(self) -> OvapiDeparture | None:
        """Return the specific departure for this sensor's index, if available."""
        departures = self._get_matching_departures()
        if len(departures) > self._departure_index:
            return departures[self._departure_index]
        return None

    def _infer_stop_transport_type(self) -> str | None:
        """Infer transport type from other passes at this stop when current slot is empty."""
        if not self.coordinator.data:
            return None
        for dep in self._get_matching_departures():
            if dep.transport_type:
                return dep.transport_type
        for dep in self.coordinator.data.departures:
            if dep.transport_type:
                return dep.transport_type
        return None

    @property
    def icon(self) -> str:
        """Dynamic icon based on the departing vehicle type, with mode-neutral fallback."""
        dep = self._get_current_departure()
        transport_type = (dep.transport_type if dep else None) or self._infer_stop_transport_type()
        return _get_icon_for_transport(transport_type)

    @property
    def native_value(self) -> datetime | None:
        """Return the expected departure as a UTC datetime rounded to whole minute."""
        dep = self._get_current_departure()
        if not dep or not dep.best_departure_time:
            return None

        # Round down to whole minute to prevent sub-minute GPS jitter writes every 30s
        rounded_time = dep.best_departure_time.replace(second=0, microsecond=0)
        return rounded_time.astimezone(UTC)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed departure information as attributes."""
        dep = self._get_current_departure()
        stop_info = self.coordinator.data.stop if self.coordinator.data else None

        attrs: dict[str, Any] = {
            ATTR_STOP_TPC: self._stop_code,
            ATTR_STOP_NAME: stop_info.name if stop_info else self.coordinator.stop_name,
            ATTR_STALE: self.coordinator.is_stale,
        }

        if not dep:
            attrs[ATTR_STATUS] = "No Upcoming Departures"
            return attrs

        attrs[ATTR_SUMMARY] = dep.summary
        attrs[ATTR_LINE_NUMBER] = dep.line_number
        attrs[ATTR_DESTINATION] = dep.destination
        attrs[ATTR_DELAY_MINUTES] = dep.delay_minutes
        attrs[ATTR_PLATFORM] = dep.side_code
        attrs[ATTR_STATUS] = dep.trip_status
        attrs[ATTR_OPERATOR] = dep.operator_code
        attrs[ATTR_TRANSPORT_TYPE] = dep.transport_type

        if dep.target_departure:
            attrs[ATTR_SCHEDULED_DEPARTURE] = dep.target_departure.isoformat()
        if dep.expected_departure:
            attrs[ATTR_EXPECTED_DEPARTURE] = dep.expected_departure.isoformat()

        return attrs
