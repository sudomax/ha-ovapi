"""Constants for the Dutch Public Transport (OVapi) integration."""

from __future__ import annotations

DOMAIN = "ovapi"

# Configuration keys
CONF_STOP_CODE = "stop_code"
CONF_LINE_NUMBER = "line_number"

# Default configuration values
DEFAULT_TIMEOUT = 10  # seconds
DEPARTURES_COUNT = 3
ALL_LINES_VALUE = "all"

# Adaptive polling thresholds & intervals (seconds)
POLL_INTERVAL_ACTIVE = 30  # Next departure within 30 minutes
POLL_INTERVAL_FAR = 300  # Next departure > 30 minutes away (5 minutes)
POLL_INTERVAL_DORMANT = 900  # No departures scheduled / overnight (15 minutes)
ACTIVE_THRESHOLD_MINUTES = 30

# Error resilience
MAX_FAILED_ATTEMPTS = 5  # Tolerate up to 5 failures before marking unavailable
BACKOFF_INTERVALS = [30, 60, 120, 180, 300]  # Progressive backoff on retry

# Sensor attribute keys
ATTR_SUMMARY = "summary"
ATTR_STOP_NAME = "stop_name"
ATTR_STOP_TPC = "stop_tpc"
ATTR_LINE_NUMBER = "line_number"
ATTR_DESTINATION = "destination"
ATTR_SCHEDULED_DEPARTURE = "scheduled_departure"
ATTR_EXPECTED_DEPARTURE = "expected_departure"
ATTR_DELAY_MINUTES = "delay_minutes"
ATTR_STATUS = "status"
ATTR_OPERATOR = "operator"
ATTR_PLATFORM = "platform"
ATTR_TRANSPORT_TYPE = "transport_type"
ATTR_STALE = "stale"
