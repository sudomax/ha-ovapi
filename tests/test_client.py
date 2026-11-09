"""Tests for ovapi_client."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from aiohttp import ClientResponseError

from custom_components.ovapi.ovapi_client import (
    OvapiClient,
    OvapiConnectionError,
    OvapiStopNotFoundError,
)
from custom_components.ovapi.ovapi_client.models import (
    OvapiDeparture,
    OvapiStop,
    OvapiStopDepartures,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "tpc_30005029.json"


@pytest.fixture
def sample_payload():
    """Load sample Amsterdam Centraal fixture data."""
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def test_models_parsing_from_fixture(sample_payload):
    """Test model construction from fixture and automatic exclusion of terminating trips."""
    tpc = "30005029"
    data = sample_payload[tpc]

    stop = OvapiStop.from_dict(tpc, data["Stop"])
    assert stop.name == "Centraal Station"
    assert stop.town == "Amsterdam"
    assert stop.tpc == "30005029"
    assert stop.stop_area_code == "09575"

    passes = data["Passes"]
    departures = [OvapiDeparture.from_dict(jid, p) for jid, p in passes.items()]
    assert len(departures) == 22

    stop_departures = OvapiStopDepartures(stop=stop, departures=departures)

    # Terminating / drop-off-only passes (JourneyStopType == "LAST", GetIn is False) are excluded
    boardable = stop_departures.get_departures(line_number="26", exclude_passed=False)
    assert len(boardable) > 0
    for dep in boardable:
        assert dep.line_number == "26"
        assert dep.destination == "IJburg"
        assert dep.is_terminating is False


def test_exclude_non_departing_and_terminating_passes():
    """Test that arrival-only, LAST-stop, and GetIn=False trips are excluded."""
    tz = ZoneInfo("Europe/Amsterdam")
    stop = OvapiStop(tpc="30005029", name="Centraal Station", town="Amsterdam")

    dep_valid = OvapiDeparture(
        journey_id="1",
        line_number="26",
        destination="IJburg",
        target_departure=datetime(2026, 10, 10, 19, 15, 0, tzinfo=tz),
    )
    dep_no_departure = OvapiDeparture(
        journey_id="2",
        line_number="26",
        destination="Centraal Station",
        target_arrival=datetime(2026, 10, 10, 19, 10, 0, tzinfo=tz),
        target_departure=None,
        expected_departure=None,
    )
    dep_last_stop = OvapiDeparture(
        journey_id="3",
        line_number="26",
        destination="Centraal Station",
        target_departure=datetime(2026, 10, 10, 19, 12, 0, tzinfo=tz),
        journey_stop_type="LAST",
    )
    dep_no_boarding = OvapiDeparture(
        journey_id="4",
        line_number="26",
        destination="Centraal Station",
        target_departure=datetime(2026, 10, 10, 19, 14, 0, tzinfo=tz),
        get_in=False,
    )

    stop_departures = OvapiStopDepartures(
        stop=stop,
        departures=[dep_no_departure, dep_last_stop, dep_no_boarding, dep_valid],
    )

    deps = stop_departures.get_departures()
    assert len(deps) == 1
    assert deps[0].journey_id == "1"
    assert deps[0].destination == "IJburg"


def test_delay_and_summary_formatting():
    """Test delay calculations and summary strings on departures."""
    tz = ZoneInfo("Europe/Amsterdam")

    dep_ontime = OvapiDeparture(
        journey_id="1",
        line_number="26",
        destination="IJburg",
        target_departure=datetime(2026, 10, 10, 19, 0, 0, tzinfo=tz),
        expected_departure=datetime(2026, 10, 10, 19, 0, 0, tzinfo=tz),
    )
    assert dep_ontime.delay_seconds == 0
    assert dep_ontime.delay_minutes == 0
    assert dep_ontime.summary == "26 → IJburg"

    dep_delayed = OvapiDeparture(
        journey_id="2",
        line_number="26",
        destination="IJburg",
        target_departure=datetime(2026, 10, 10, 19, 0, 0, tzinfo=tz),
        expected_departure=datetime(2026, 10, 10, 19, 4, 15, tzinfo=tz),
    )
    assert dep_delayed.delay_seconds == 255
    assert dep_delayed.delay_minutes == 4
    assert dep_delayed.summary == "26 → IJburg (+4 min)"

    dep_early = OvapiDeparture(
        journey_id="3",
        line_number="26",
        destination="IJburg",
        target_departure=datetime(2026, 10, 10, 19, 5, 0, tzinfo=tz),
        expected_departure=datetime(2026, 10, 10, 19, 3, 50, tzinfo=tz),
    )
    assert dep_early.delay_minutes == -1
    assert dep_early.summary == "26 → IJburg (-1 min)"

    dep_cancelled = OvapiDeparture(
        journey_id="4",
        line_number="26",
        destination="IJburg",
        trip_status="CANCELLED",
    )
    assert dep_cancelled.summary == "26 → IJburg (Cancelled)"


class MockAsyncResponse:
    """Mock aiohttp async response context manager."""

    def __init__(self, status=200, json_data=None, side_effect=None):
        self.status = status
        self._json_data = json_data
        self._side_effect = side_effect

    async def json(self, *args, **kwargs):
        return self._json_data

    async def __aenter__(self):
        if self._side_effect:
            raise self._side_effect
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_client_get_stop_departures_mocked(sample_payload):
    """Test client end-to-end with mocked aiohttp session."""
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.get.return_value = MockAsyncResponse(status=200, json_data=sample_payload)

    client = OvapiClient(session=mock_session)
    result = await client.get_stop_departures("30005029")

    assert isinstance(result, OvapiStopDepartures)
    assert result.stop.name == "Centraal Station"
    assert len(result.departures) == 22


@pytest.mark.asyncio
async def test_client_stop_not_found_404():
    """Test 404 response raises OvapiStopNotFoundError."""
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.get.return_value = MockAsyncResponse(status=404)

    client = OvapiClient(session=mock_session)
    with pytest.raises(OvapiStopNotFoundError):
        await client.get_stop_departures("99999999")


@pytest.mark.asyncio
async def test_client_connection_error():
    """Test connection failure raises OvapiConnectionError."""
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.get.return_value = MockAsyncResponse(
        side_effect=ClientResponseError(
            request_info=MagicMock(), history=(), status=500, message="Server Error"
        )
    )

    client = OvapiClient(session=mock_session)
    with pytest.raises(OvapiConnectionError):
        await client.get_stop_departures("30005029")
