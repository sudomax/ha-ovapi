"""Data models for OVapi client."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

AMSTERDAM_TZ = ZoneInfo("Europe/Amsterdam")


def parse_datetime(dt_str: str | None) -> datetime | None:
    """Parse OVapi datetime string into timezone-aware Europe/Amsterdam datetime."""
    if not dt_str:
        return None
    try:
        # Expected formats: 2026-10-10T17:28:44 or with timezone offset
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=AMSTERDAM_TZ)
        return dt
    except (ValueError, TypeError):
        return None


@dataclass(slots=True)
class OvapiStop:
    """Represents a public transport stop or platform."""

    tpc: str
    name: str
    town: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    stop_area_code: str | None = None
    wheelchair_accessible: str | None = None
    visual_accessible: str | None = None

    @classmethod
    def from_dict(cls, tpc: str, data: dict[str, Any]) -> OvapiStop:
        """Create an OvapiStop instance from API dictionary."""
        return cls(
            tpc=tpc,
            name=data.get("TimingPointName") or f"Stop {tpc}",
            town=data.get("TimingPointTown") if data.get("TimingPointTown") != "unknown" else None,
            latitude=data.get("Latitude"),
            longitude=data.get("Longitude"),
            stop_area_code=data.get("StopAreaCode"),
            wheelchair_accessible=data.get("TimingPointWheelChairAccessible"),
            visual_accessible=data.get("TimingPointVisualAccessible"),
        )


@dataclass(slots=True)
class OvapiDeparture:
    """Represents a single transit departure/pass at a stop."""

    journey_id: str
    line_number: str
    line_name: str = ""
    line_planning_number: str = ""
    destination: str = ""
    destination_code: str | None = None
    target_departure: datetime | None = None
    expected_departure: datetime | None = None
    target_arrival: datetime | None = None
    expected_arrival: datetime | None = None
    trip_status: str = "UNKNOWN"
    operator_code: str | None = None
    transport_type: str | None = None
    side_code: str | None = None
    journey_number: int | None = None
    wheelchair_accessible: str | None = None
    journey_stop_type: str | None = None
    get_in: bool | None = None

    @property
    def best_departure_time(self) -> datetime | None:
        """Return the most accurate departure time (expected real-time or scheduled target)."""
        return self.expected_departure or self.target_departure

    @property
    def is_terminating(self) -> bool:
        """Return True if this trip terminates here or does not allow boarding."""
        if self.journey_stop_type == "LAST":
            return True
        if self.get_in is False:
            return True
        return self.target_arrival is not None and self.best_departure_time is None

    @property
    def delay_seconds(self) -> int:
        """Calculate the real-time delay in seconds (positive = delay, negative = early)."""
        if self.expected_departure and self.target_departure:
            return int((self.expected_departure - self.target_departure).total_seconds())
        return 0

    @property
    def delay_minutes(self) -> int:
        """Calculate delay in whole minutes."""
        return round(self.delay_seconds / 60)

    @property
    def summary(self) -> str:
        """Return a concise human-readable summary for dashboard cards."""
        if self.line_number and self.destination:
            base = f"{self.line_number} → {self.destination}"
        else:
            base = self.line_number or self.destination or "Unknown"

        if self.trip_status == "CANCELLED":
            return f"{base} (Cancelled)"
        delay = self.delay_minutes
        if delay > 0:
            return f"{base} (+{delay} min)"
        if delay < 0:
            return f"{base} ({delay} min)"
        return base

    @classmethod
    def from_dict(cls, journey_id: str, data: dict[str, Any]) -> OvapiDeparture:
        """Create an OvapiDeparture instance from API dictionary."""
        return cls(
            journey_id=journey_id,
            line_number=str(data.get("LinePublicNumber", "")),
            line_name=data.get("LineName", ""),
            line_planning_number=data.get("LinePlanningNumber", ""),
            destination=data.get("DestinationName50", ""),
            destination_code=data.get("DestinationCode"),
            target_departure=parse_datetime(data.get("TargetDepartureTime")),
            expected_departure=parse_datetime(data.get("ExpectedDepartureTime")),
            target_arrival=parse_datetime(data.get("TargetArrivalTime")),
            expected_arrival=parse_datetime(data.get("ExpectedArrivalTime")),
            trip_status=data.get("TripStopStatus", "UNKNOWN"),
            operator_code=data.get("OperatorCode"),
            transport_type=data.get("TransportType") or None,
            side_code=data.get("SideCode"),
            journey_number=data.get("JourneyNumber"),
            wheelchair_accessible=data.get("WheelChairAccessible"),
            journey_stop_type=data.get("JourneyStopType"),
            get_in=data.get("GetIn"),
        )


@dataclass(slots=True)
class OvapiStopDepartures:
    """Represents a stop and all its scheduled/real-time departures."""

    stop: OvapiStop
    departures: list[OvapiDeparture] = field(default_factory=list)
    general_messages: dict[str, Any] = field(default_factory=dict)

    def get_departures(
        self,
        line_number: str | list[str] | set[str] | tuple[str, ...] | None = None,
        exclude_passed: bool = True,
    ) -> list[OvapiDeparture]:
        """Filter boardable departures by line number, sorted chronologically."""
        results = [d for d in self.departures if not d.is_terminating]

        if exclude_passed:
            results = [d for d in results if d.trip_status != "PASSED"]

        if line_number:
            if isinstance(line_number, (list, set, tuple)):
                target_lines = {
                    str(line).strip().lower()
                    for line in line_number
                    if str(line).strip().lower() and str(line).strip().lower() != "all"
                }
            elif "," in str(line_number):
                target_lines = {
                    line.strip().lower()
                    for line in str(line_number).split(",")
                    if line.strip().lower() and line.strip().lower() != "all"
                }
            else:
                single = str(line_number).strip().lower()
                target_lines = {single} if single and single != "all" else set()

            if target_lines:
                results = [d for d in results if d.line_number.strip().lower() in target_lines]

        max_dt = datetime.max.replace(tzinfo=AMSTERDAM_TZ)

        def sort_key(d: OvapiDeparture) -> datetime:
            return d.best_departure_time or max_dt

        return sorted(results, key=sort_key)
