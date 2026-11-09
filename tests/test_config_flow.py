"""Tests for the 1-step OvapiConfigFlow."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.ovapi.config_flow import OvapiConfigFlow
from custom_components.ovapi.const import (
    ALL_LINES_VALUE,
    CONF_LINE_NUMBER,
    CONF_STOP_CODE,
)
from custom_components.ovapi.ovapi_client.exceptions import (
    OvapiConnectionError,
    OvapiStopNotFoundError,
)
from custom_components.ovapi.ovapi_client.models import (
    OvapiStop,
    OvapiStopDepartures,
)


@pytest.mark.asyncio
async def test_config_flow_show_initial_form():
    """Test showing the single-step setup form."""
    flow = OvapiConfigFlow()
    result = await flow.async_step_user(None)
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


@pytest.mark.asyncio
async def test_config_flow_all_lines_default():
    """Test leaving line_number empty creates an All Lines entry in 1 step."""
    flow = OvapiConfigFlow()
    mock_stop = OvapiStop(tpc="30005029", name="Centraal Station", town="Amsterdam")
    mock_data = OvapiStopDepartures(stop=mock_stop, departures=[])

    with patch(
        "custom_components.ovapi.config_flow.OvapiClient.get_stop_departures",
        new=AsyncMock(return_value=mock_data),
    ):
        result = await flow.async_step_user({CONF_STOP_CODE: "30005029"})

    assert result["type"] == "create_entry"
    assert result["title"] == "Centraal Station (All Lines)"
    assert flow.unique_id == "30005029_all"
    assert result["data"] == {
        CONF_STOP_CODE: "30005029",
        CONF_LINE_NUMBER: ALL_LINES_VALUE,
    }


@pytest.mark.asyncio
async def test_config_flow_single_line():
    """Test entering a single line creates a line-specific entry in 1 step."""
    flow = OvapiConfigFlow()
    mock_stop = OvapiStop(tpc="30005029", name="Centraal Station", town="Amsterdam")
    mock_data = OvapiStopDepartures(stop=mock_stop, departures=[])

    with patch(
        "custom_components.ovapi.config_flow.OvapiClient.get_stop_departures",
        new=AsyncMock(return_value=mock_data),
    ):
        result = await flow.async_step_user(
            {CONF_STOP_CODE: "30005029", CONF_LINE_NUMBER: "Lijn 26"}
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Centraal Station (Line 26)"
    assert flow.unique_id == "30005029_26"
    assert result["data"] == {
        CONF_STOP_CODE: "30005029",
        CONF_LINE_NUMBER: "26",
    }


@pytest.mark.asyncio
async def test_config_flow_multiple_lines():
    """Test entering comma/semicolon-separated lines creates a multi-line entry."""
    flow = OvapiConfigFlow()
    mock_stop = OvapiStop(tpc="30005029", name="Centraal Station", town="Amsterdam")
    mock_data = OvapiStopDepartures(stop=mock_stop, departures=[])

    with patch(
        "custom_components.ovapi.config_flow.OvapiClient.get_stop_departures",
        new=AsyncMock(return_value=mock_data),
    ):
        result = await flow.async_step_user(
            {CONF_STOP_CODE: "30005029", CONF_LINE_NUMBER: "Ferry F3; Ligne 7, trein 39, 7"}
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Centraal Station (Lines 7, 39, F3)"
    assert flow.unique_id == "30005029_7_39_f3"
    assert result["data"] == {
        CONF_STOP_CODE: "30005029",
        CONF_LINE_NUMBER: ["7", "39", "F3"],
    }


@pytest.mark.asyncio
async def test_config_flow_input_sanitization():
    """Test forgiving stop code input cleaning for spaces, hashes, and prefixes."""
    flow = OvapiConfigFlow()
    mock_stop = OvapiStop(tpc="30005029", name="Centraal Station", town="Amsterdam")
    mock_data = OvapiStopDepartures(stop=mock_stop, departures=[])

    with patch(
        "custom_components.ovapi.config_flow.OvapiClient.get_stop_departures",
        new=AsyncMock(return_value=mock_data),
    ) as mock_get:
        result = await flow.async_step_user({CONF_STOP_CODE: " TPC: 3000 5029 "})

    assert result["type"] == "create_entry"
    mock_get.assert_awaited_once_with("30005029")


@pytest.mark.asyncio
async def test_config_flow_errors():
    """Test stop_not_found, cannot_connect, and empty input errors."""
    flow = OvapiConfigFlow()

    # Empty stop code
    res_empty = await flow.async_step_user({CONF_STOP_CODE: "   "})
    assert res_empty["type"] == "form"
    assert res_empty["errors"] == {"base": "stop_not_found"}

    # Stop not found (404)
    with patch(
        "custom_components.ovapi.config_flow.OvapiClient.get_stop_departures",
        new=AsyncMock(side_effect=OvapiStopNotFoundError("Not found")),
    ):
        res_404 = await flow.async_step_user({CONF_STOP_CODE: "99999999"})
    assert res_404["type"] == "form"
    assert res_404["errors"] == {"base": "stop_not_found"}

    # Connection error
    with patch(
        "custom_components.ovapi.config_flow.OvapiClient.get_stop_departures",
        new=AsyncMock(side_effect=OvapiConnectionError("Timeout")),
    ):
        res_conn = await flow.async_step_user({CONF_STOP_CODE: "30005029"})
    assert res_conn["type"] == "form"
    assert res_conn["errors"] == {"base": "cannot_connect"}
