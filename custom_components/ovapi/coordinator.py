"""DataUpdateCoordinator for the Dutch Public Transport (OVapi) integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ACTIVE_THRESHOLD_MINUTES,
    ALL_LINES_VALUE,
    BACKOFF_INTERVALS,
    DOMAIN,
    MAX_FAILED_ATTEMPTS,
    POLL_INTERVAL_ACTIVE,
    POLL_INTERVAL_DORMANT,
    POLL_INTERVAL_FAR,
)
from .ovapi_client import (
    OvapiClient,
    OvapiError,
    OvapiStopDepartures,
)
from .ovapi_client.models import AMSTERDAM_TZ

_LOGGER = logging.getLogger(__name__)


class OvapiDataUpdateCoordinator(DataUpdateCoordinator[OvapiStopDepartures]):
    """Class to manage fetching OVapi public transit departure data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: OvapiClient,
        tpc: str,
        line_filter: str | list[str] | None = None,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.tpc = str(tpc).strip()
        self.line_filter = line_filter

        self.consecutive_failures: int = 0
        self.is_stale: bool = False
        self._last_valid_data: OvapiStopDepartures | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.tpc}",
            update_interval=timedelta(seconds=POLL_INTERVAL_ACTIVE),
        )

    def _adjust_adaptive_interval(self, data: OvapiStopDepartures) -> None:
        """Adjust polling interval based on schedule proximity."""
        if not self.line_filter:
            line = None
        elif isinstance(self.line_filter, str):
            line = None if self.line_filter.lower() == ALL_LINES_VALUE else self.line_filter
        else:
            lines = [item for item in self.line_filter if item.lower() != ALL_LINES_VALUE]
            line = lines if lines else None

        upcoming = data.get_departures(line_number=line, exclude_passed=True)

        if not upcoming:
            self.update_interval = timedelta(seconds=POLL_INTERVAL_DORMANT)
            _LOGGER.debug(
                "Stop %s has no upcoming departures; dormant poll set to %ds",
                self.tpc,
                POLL_INTERVAL_DORMANT,
            )
            return

        next_dep = upcoming[0]
        departure_time = next_dep.best_departure_time
        if departure_time is None:
            self.update_interval = timedelta(seconds=POLL_INTERVAL_ACTIVE)
            return

        now = datetime.now(AMSTERDAM_TZ)
        seconds_until = max(0.0, (departure_time - now).total_seconds())

        if seconds_until <= ACTIVE_THRESHOLD_MINUTES * 60:
            interval = POLL_INTERVAL_ACTIVE
            # Schedule refresh right as an imminent departure passes so entities roll over promptly.
            if 0 < seconds_until < interval:
                interval = max(5, int(seconds_until) + 1)
            self.update_interval = timedelta(seconds=interval)
            _LOGGER.debug(
                "Stop %s next departure in %.1f min; active poll set to %ds",
                self.tpc,
                seconds_until / 60,
                interval,
            )
        else:
            self.update_interval = timedelta(seconds=POLL_INTERVAL_FAR)
            _LOGGER.debug(
                "Stop %s next departure in %.1f min; relaxed poll set to %ds",
                self.tpc,
                seconds_until / 60,
                POLL_INTERVAL_FAR,
            )

    async def _async_update_data(self) -> OvapiStopDepartures:
        """Fetch latest departure data from OVapi with resilience and adaptive polling."""
        try:
            data = await self.client.get_stop_departures(self.tpc)
            self.consecutive_failures = 0
            self.is_stale = False
            self._last_valid_data = data
            self._adjust_adaptive_interval(data)
            return data
        except (OvapiError, Exception) as err:
            self.consecutive_failures += 1
            _LOGGER.warning(
                "Error communicating with OVapi for stop %s (attempt %d/%d): %s",
                self.tpc,
                self.consecutive_failures,
                MAX_FAILED_ATTEMPTS,
                err,
            )

            # Within grace period with previous data: retain data, mark stale, and back off
            if (
                self.consecutive_failures <= MAX_FAILED_ATTEMPTS
                and self._last_valid_data is not None
            ):
                self.is_stale = True
                backoff_idx = min(self.consecutive_failures - 1, len(BACKOFF_INTERVALS) - 1)
                retry_interval = BACKOFF_INTERVALS[backoff_idx]
                self.update_interval = timedelta(seconds=retry_interval)
                _LOGGER.info(
                    "Retaining cached data for stop %s (stale); retrying in %ds",
                    self.tpc,
                    retry_interval,
                )
                return self._last_valid_data

            self.is_stale = True
            if isinstance(err, OvapiError):
                raise UpdateFailed(
                    f"Error communicating with OVapi for stop {self.tpc} after {self.consecutive_failures} attempts: {err}"
                ) from err
            raise UpdateFailed(
                f"Unexpected error updating OVapi stop {self.tpc} after {self.consecutive_failures} attempts: {err}"
            ) from err

    @property
    def stop_name(self) -> str:
        """Return the name of the stop if data is loaded, else fallback to TPC."""
        if self.data and self.data.stop and self.data.stop.name:
            return self.data.stop.name
        return f"Stop {self.tpc}"
