"""Asynchronous client for fetching Dutch public transit data from OVapi."""

from __future__ import annotations

import types
from typing import Self

import aiohttp

from .exceptions import (
    OvapiConnectionError,
    OvapiParseError,
    OvapiStopNotFoundError,
)
from .models import OvapiDeparture, OvapiStop, OvapiStopDepartures

DEFAULT_BASE_URL = "http://v0.ovapi.nl"
DEFAULT_TIMEOUT = 10.0


class OvapiClient:
    """Asynchronous client for interacting with OVapi."""

    def __init__(
        self,
        session: aiohttp.ClientSession | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the OVapi client."""
        self._session = session
        self._owns_session = False
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp ClientSession."""
        is_closed = getattr(self._session, "closed", False) is True
        if self._session is None or is_closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._timeout)
            )
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the internal session if created by this client."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()

    async def get_stop_departures(self, tpc: str) -> OvapiStopDepartures:
        """Fetch scheduled and real-time departures for a given stop TimingPointCode."""
        cleaned_tpc = str(tpc).strip()
        if not cleaned_tpc:
            raise ValueError("TimingPointCode (TPC) cannot be empty")

        url = f"{self._base_url}/tpc/{cleaned_tpc}"
        session = await self._get_session()

        try:
            async with session.get(url) as response:
                if response.status == 404:
                    raise OvapiStopNotFoundError(
                        f"Stop with TimingPointCode '{cleaned_tpc}' was not found (404)."
                    )
                if response.status != 200:
                    raise OvapiConnectionError(
                        f"OVapi returned unexpected HTTP status {response.status} for URL {url}"
                    )
                payload = await response.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError) as err:
            raise OvapiConnectionError(f"Failed to connect to OVapi at {url}: {err}") from err
        except Exception as err:
            if isinstance(err, (OvapiStopNotFoundError, OvapiConnectionError)):
                raise
            raise OvapiParseError(f"Unexpected error retrieving stop data: {err}") from err

        if not isinstance(payload, dict) or not payload:
            raise OvapiStopNotFoundError(
                f"No data returned by OVapi for TimingPointCode '{cleaned_tpc}'"
            )

        # Stop data is keyed by its TPC string
        stop_payload = payload.get(cleaned_tpc)
        if not stop_payload and len(payload) == 1:
            # Sometimes TPC keys differ slightly in padding or formatting
            stop_payload = next(iter(payload.values()))

        if not isinstance(stop_payload, dict):
            raise OvapiStopNotFoundError(
                f"Invalid or empty stop response for TimingPointCode '{cleaned_tpc}'"
            )

        try:
            stop_info = stop_payload.get("Stop", {})
            stop = OvapiStop.from_dict(cleaned_tpc, stop_info)

            passes_dict = stop_payload.get("Passes", {})
            departures: list[OvapiDeparture] = []
            for journey_id, pass_data in passes_dict.items():
                if isinstance(pass_data, dict):
                    departures.append(OvapiDeparture.from_dict(journey_id, pass_data))

            general_messages = stop_payload.get("GeneralMessages", {})
            return OvapiStopDepartures(
                stop=stop,
                departures=departures,
                general_messages=general_messages if isinstance(general_messages, dict) else {},
            )
        except Exception as err:
            raise OvapiParseError(f"Failed to parse stop data for {cleaned_tpc}: {err}") from err
