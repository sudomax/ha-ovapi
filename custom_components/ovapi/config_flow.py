"""Config flow for Dutch Public Transport (OVapi) integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ALL_LINES_VALUE,
    CONF_LINE_NUMBER,
    CONF_STOP_CODE,
    DOMAIN,
)
from .ovapi_client import (
    OvapiClient,
    OvapiConnectionError,
    OvapiError,
    OvapiStopNotFoundError,
)

_LOGGER = logging.getLogger(__name__)


class OvapiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a 1-step config flow for Dutch Public Transport (OVapi)."""

    VERSION = 1

    @staticmethod
    def _parse_lines(raw_input: str) -> list[str]:
        """Parse and clean optional comma/semicolon-separated line numbers."""
        lines: list[str] = []
        seen: set[str] = set()
        if not raw_input:
            return lines

        for item in raw_input.replace(";", ",").split(","):
            cleaned = item.strip()
            for prefix in (
                "line ",
                "lijn ",
                "ligne ",
                "bus ",
                "tram ",
                "metro ",
                "ferry ",
                "veer ",
                "boot ",
                "train ",
                "trein ",
            ):
                if cleaned.lower().startswith(prefix):
                    cleaned = cleaned[len(prefix) :].strip()
            lower = cleaned.lower()
            if cleaned and lower != ALL_LINES_VALUE and lower not in seen:
                seen.add(lower)
                lines.append(cleaned)
        return lines

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Prompt user for Timing Point Code (TPC) and optional line filter."""
        errors: dict[str, str] = {}
        default_stop = ""
        default_lines = ""

        if user_input is not None:
            raw_stop = str(user_input.get(CONF_STOP_CODE, "")).strip()
            raw_lines = str(user_input.get(CONF_LINE_NUMBER, "")).strip()
            default_stop = raw_stop
            default_lines = raw_lines

            # Forgiving input cleaning: strip spaces, dashes, or prefixes like "TPC:" or "#"
            cleaned_digits = "".join(c for c in raw_stop if c.isdigit())
            stop_code = cleaned_digits if cleaned_digits else raw_stop

            if not stop_code:
                errors["base"] = "stop_not_found"
            else:
                session = async_get_clientsession(self.hass)
                client = OvapiClient(session=session)

                try:
                    departures = await client.get_stop_departures(stop_code)
                except OvapiStopNotFoundError:
                    errors["base"] = "stop_not_found"
                except (OvapiConnectionError, OvapiError):
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected exception during OVapi stop validation")
                    errors["base"] = "unknown"
                else:
                    stop_name = departures.stop.name
                    lines = self._parse_lines(raw_lines)

                    if not lines:
                        unique_id = f"{stop_code}_all"
                        title = f"{stop_name} (All Lines)"
                        line_data: str | list[str] = ALL_LINES_VALUE
                    elif len(lines) == 1:
                        single_line = lines[0]
                        unique_id = f"{stop_code}_{single_line.lower()}"
                        title = f"{stop_name} (Line {single_line})"
                        line_data = single_line
                    else:
                        lines_sorted = sorted(lines, key=lambda x: (len(x), x.lower()))
                        lines_id = "_".join(item.lower() for item in lines_sorted)
                        unique_id = f"{stop_code}_{lines_id}"
                        title = f"{stop_name} (Lines {', '.join(lines_sorted)})"
                        line_data = lines_sorted

                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_STOP_CODE: stop_code,
                            CONF_LINE_NUMBER: line_data,
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_STOP_CODE, default=default_stop): str,
                vol.Optional(CONF_LINE_NUMBER, default=default_lines): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
