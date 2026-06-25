# config_flow.py
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from pymodbus.exceptions import ModbusException

from . import AOKProtocol
from .const import CONF_DEVICE_ID, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    vol.Optional(CONF_DEVICE_ID, default="1,65535;2,65535;3,65535"): str,
})

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    client = AOKProtocol(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        loop=hass.loop,
    )

    try:
        await client.connect()
        if not client.connected:
            raise ConnectionError("Modbus connection failed")
        return {"title": "AOK"}
    except ModbusException as exc:
        raise ValueError("modbus_communication_error") from exc
    finally:
        client.close()


@config_entries.HANDLERS.register(DOMAIN)
class AOKConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AOK."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    _entry: config_entries.ConfigEntry

    def _get_data_schema(self, user_input: dict | None = None) -> vol.Schema:
        """Build the form schema, pre-filling existing values during reconfigure."""
        if self.source == SOURCE_RECONFIGURE:
            return self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                {**self._entry.data, **(user_input or {})},
            )
        return STEP_USER_DATA_SCHEMA

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._entry,
                        data_updates=user_input,
                    )

                return self.async_create_entry(title=info["title"], data=user_input)

            except ConnectionError:
                errors["base"] = "cannot_connect"
            except ValueError as exc:
                if str(exc) == "modbus_communication_error":
                    errors["base"] = "modbus_error"
                else:
                    errors["base"] = "unknown"
                    _LOGGER.error("Unexpected error %s: %s", exc.__class__.__name__, exc)
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected error %s: %s", exc.__class__.__name__, exc)
                errors["base"] = "unknown"

        step_id = "reconfigure" if self.source == SOURCE_RECONFIGURE else "user"

        return self.async_show_form(
            step_id=step_id,
            data_schema=self._get_data_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device re-configuration."""
        self._entry = self._get_reconfigure_entry()
        return await self.async_step_user(user_input)