"""Tests for OVapi sensor entities and translations."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.ovapi.const import (
    ATTR_DELAY_MINUTES,
    ATTR_DESTINATION,
    ATTR_LINE_NUMBER,
    ATTR_PLATFORM,
    ATTR_STALE,
    ATTR_STATUS,
    ATTR_SUMMARY,
    CONF_LINE_NUMBER,
    CONF_STOP_CODE,
    DEPARTURES_COUNT,
    DOMAIN,
)
from custom_components.ovapi.ovapi_client.models import (
    AMSTERDAM_TZ,
    OvapiDeparture,
    OvapiStop,
    OvapiStopDepartures,
)
from custom_components.ovapi.sensor import (
    OvapiDepartureSensor,
    async_setup_entry,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "tpc_30005029.json"
COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "ovapi"


def load_fixture_data() -> OvapiStopDepartures:
    """Load sample fixture into OvapiStopDepartures model."""
    with open(FIXTURE_PATH) as f:
        data = json.load(f)["30005029"]
    stop = OvapiStop.from_dict("30005029", data["Stop"])
    departures = [OvapiDeparture.from_dict(jid, p) for jid, p in data["Passes"].items()]
    return OvapiStopDepartures(stop=stop, departures=departures)


def resolve_translated_name(sensor: OvapiDepartureSensor, lang: str = "en") -> str:
    """Resolve sensor's translated entity name from translations/{lang}.json."""
    trans_path = COMPONENT_DIR / "translations" / f"{lang}.json"
    translations = json.loads(trans_path.read_text(encoding="utf-8"))
    template = translations["entity"]["sensor"][sensor.translation_key]["name"]
    return template.format(**sensor.translation_placeholders)


@pytest.mark.asyncio
async def test_async_setup_entry_creates_fixed_three_sensors():
    """Test setup creates strictly 3 departure timestamp sensors."""
    hass = HomeAssistant()
    departures_data = load_fixture_data()

    coordinator = MagicMock()
    coordinator.data = departures_data
    coordinator.stop_name = departures_data.stop.name
    coordinator.is_stale = False
    hass.data[DOMAIN] = {"entry_1": coordinator}

    entry = ConfigEntry(
        entry_id="entry_1",
        data={CONF_STOP_CODE: "30005029", CONF_LINE_NUMBER: "all"},
    )

    added_entities: list[OvapiDepartureSensor] = []
    await async_setup_entry(hass, entry, lambda ents: added_entities.extend(ents))

    assert len(added_entities) == DEPARTURES_COUNT == 3
    # _attr_name must remain None so Home Assistant uses translation_key
    assert all(e.name is None for e in added_entities)
    assert [resolve_translated_name(e, "en") for e in added_entities] == [
        "Next Departure",
        "Departure 2",
        "Departure 3",
    ]
    assert [resolve_translated_name(e, "nl") for e in added_entities] == [
        "Volgend vertrek",
        "Vertrek 2",
        "Vertrek 3",
    ]
    assert [resolve_translated_name(e, "fr") for e in added_entities] == [
        "Prochain départ",
        "Départ 2",
        "Départ 3",
    ]
    assert [e.unique_id for e in added_entities] == [
        "entry_1_departure",
        "entry_1_departure_2",
        "entry_1_departure_3",
    ]


def test_departure_sensor_all_lines_and_summary():
    """Test departure sensor state, whole-minute rounding, and summary attribute."""
    departures_data = load_fixture_data()

    coordinator = MagicMock()
    coordinator.data = departures_data
    coordinator.stop_name = departures_data.stop.name
    coordinator.is_stale = False

    entry = ConfigEntry(
        entry_id="test_all_lines",
        data={CONF_STOP_CODE: "30005029", CONF_LINE_NUMBER: "all"},
    )

    sensor = OvapiDepartureSensor(coordinator, entry, "30005029", "all", departure_index=0)

    assert sensor.translation_key == "next_departure"
    assert sensor.icon == "mdi:tram"
    assert sensor.native_value is not None
    assert sensor.native_value.second == 0
    assert sensor.native_value.microsecond == 0

    attrs = sensor.extra_state_attributes
    assert attrs[ATTR_LINE_NUMBER] == "26"
    assert attrs[ATTR_DESTINATION] == "IJburg"
    assert attrs[ATTR_SUMMARY].startswith("26 → IJburg")
    assert attrs[ATTR_STALE] is False
    assert "upcoming_departures" not in attrs


def test_departure_sensor_translations_for_single_and_multiple_lines():
    """Test translated entity names across EN, NL, and FR for single and multi-line filters."""
    coordinator = MagicMock()
    coordinator.data = OvapiStopDepartures(
        stop=OvapiStop(tpc="30005029", name="Centraal Station"), departures=[]
    )
    coordinator.stop_name = "Centraal Station"
    coordinator.is_stale = False

    entry_single = ConfigEntry(
        entry_id="e_single",
        data={CONF_STOP_CODE: "30005029", CONF_LINE_NUMBER: "26"},
    )
    s1 = OvapiDepartureSensor(coordinator, entry_single, "30005029", "26", departure_index=0)
    s2 = OvapiDepartureSensor(coordinator, entry_single, "30005029", "26", departure_index=1)
    assert resolve_translated_name(s1, "en") == "Line 26 Next Departure"
    assert resolve_translated_name(s2, "en") == "Line 26 Departure 2"
    assert resolve_translated_name(s1, "nl") == "Lijn 26 volgend vertrek"
    assert resolve_translated_name(s2, "nl") == "Lijn 26 vertrek 2"
    assert resolve_translated_name(s1, "fr") == "Ligne 26 prochain départ"
    assert resolve_translated_name(s2, "fr") == "Ligne 26 départ 2"

    entry_multi = ConfigEntry(
        entry_id="e_multi",
        data={CONF_STOP_CODE: "30005029", CONF_LINE_NUMBER: ["7", "39"]},
    )
    m1 = OvapiDepartureSensor(coordinator, entry_multi, "30005029", ["7", "39"], departure_index=0)
    m3 = OvapiDepartureSensor(coordinator, entry_multi, "30005029", ["7", "39"], departure_index=2)
    assert resolve_translated_name(m1, "en") == "Lines 7, 39 Next Departure"
    assert resolve_translated_name(m3, "en") == "Lines 7, 39 Departure 3"
    assert resolve_translated_name(m1, "nl") == "Lijnen 7, 39 volgend vertrek"
    assert resolve_translated_name(m3, "nl") == "Lijnen 7, 39 vertrek 3"
    assert resolve_translated_name(m1, "fr") == "Lignes 7, 39 prochain départ"
    assert resolve_translated_name(m3, "fr") == "Lignes 7, 39 départ 3"


def test_departure_sensor_empty_and_delayed_states():
    """Test empty stop fallback attributes and delayed summary."""
    stop = OvapiStop(tpc="30005029", name="Centraal Station")
    dep_delayed = OvapiDeparture(
        journey_id="1",
        line_number="7",
        destination="Slotermeer",
        target_departure=datetime(2026, 10, 10, 19, 10, 0, tzinfo=AMSTERDAM_TZ),
        expected_departure=datetime(2026, 10, 10, 19, 13, 10, tzinfo=AMSTERDAM_TZ),
        trip_status="DRIVING",
        side_code="B",
        transport_type="BUS",
    )

    coordinator = MagicMock()
    coordinator.data = OvapiStopDepartures(stop=stop, departures=[dep_delayed])
    coordinator.stop_name = "Centraal Station"
    coordinator.is_stale = True

    entry = ConfigEntry(
        entry_id="e1",
        data={CONF_STOP_CODE: "30005029", CONF_LINE_NUMBER: "all"},
    )

    first = OvapiDepartureSensor(coordinator, entry, "30005029", "all", departure_index=0)
    second = OvapiDepartureSensor(coordinator, entry, "30005029", "all", departure_index=1)

    assert first.icon == "mdi:bus"
    assert first.extra_state_attributes[ATTR_SUMMARY] == "7 → Slotermeer (+3 min)"
    assert first.extra_state_attributes[ATTR_DELAY_MINUTES] == 3
    assert first.extra_state_attributes[ATTR_PLATFORM] == "B"
    assert first.extra_state_attributes[ATTR_STALE] is True

    assert second.native_value is None
    # Empty slot preserves the stop's vehicle icon inferred from other passes
    assert second.icon == "mdi:bus"
    assert second.extra_state_attributes[ATTR_STATUS] == "No Upcoming Departures"
    assert ATTR_SUMMARY not in second.extra_state_attributes

    # Completely empty stop with no known transport_type uses mode-neutral icon
    empty_coordinator = MagicMock()
    empty_coordinator.data = OvapiStopDepartures(stop=stop, departures=[])
    empty_coordinator.stop_name = "Centraal Station"
    empty_coordinator.is_stale = False
    empty_sensor = OvapiDepartureSensor(empty_coordinator, entry, "30005029", "all", 0)
    assert empty_sensor.icon == "mdi:transit-connection-variant"


def _flatten_json(obj: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten nested translation dictionary into dot-separated key -> string pairs."""
    out: dict[str, str] = {}
    for k, v in obj.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten_json(v, path))
        else:
            out[path] = str(v)
    return out


def test_translation_files_parity():
    """Verify strings.json, en.json, nl.json, and fr.json share identical keys and placeholders."""
    base = _flatten_json(json.loads((COMPONENT_DIR / "strings.json").read_text(encoding="utf-8")))
    placeholder_re = re.compile(r"\{[a-zA-Z0-9_]+\}")

    for lang in ("en", "nl", "fr"):
        lang_path = COMPONENT_DIR / "translations" / f"{lang}.json"
        assert lang_path.exists(), f"Missing translation file {lang_path}"
        flat = _flatten_json(json.loads(lang_path.read_text(encoding="utf-8")))
        assert set(flat.keys()) == set(base.keys()), f"Key mismatch in {lang}.json"

        for key, base_val in base.items():
            assert flat[key].strip(), f"Empty translation for {key} in {lang}.json"
            assert set(placeholder_re.findall(flat[key])) == set(
                placeholder_re.findall(base_val)
            ), f"Placeholder mismatch for {key} in {lang}.json"
