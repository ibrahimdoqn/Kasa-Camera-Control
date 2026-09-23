"""Config flow for Kasa Camera Control."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from kasa.httpclient import get_cookie_jar
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.device_registry import format_mac

from .api import AuthenticationError, KasaException, connect_device
from .const import (
    CONF_CONNECTION_PARAMETERS,
    CONF_DISCOVERY,
    CONF_SCAN_INTERVAL,
    CONF_SESSION_RENEW,
    DEFAULT_DISCOVERY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SESSION_RENEW,
    DOMAIN,
    MAX_SESSION_RENEW,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def _validate(
    hass: HomeAssistant, host: str, username: str, password: str
) -> tuple[str, str, dict[str, Any]]:
    """Connect once and return (unique_id, title, connection parameters)."""
    device = await connect_device(
        host,
        username,
        password,
        http_client=async_create_clientsession(
            hass, verify_ssl=False, cookie_jar=get_cookie_jar()
        ),
    )
    try:
        uid = format_mac(device.mac) if device.mac else device.device_id
        return (
            str(uid),
            device.alias or device.model or host,
            device.config.connection_type.to_dict(),
        )
    finally:
        await device.disconnect()


class TapoAlarmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                uid, title, connection_parameters = await _validate(
                    self.hass,
                    user_input[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except KasaException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(
                    title=title,
                    data={
                        **user_input,
                        CONF_CONNECTION_PARAMETERS: connection_parameters,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_USERNAME): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await _validate(
                    self.hass,
                    entry.data[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except KasaException:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return TapoAlarmOptionsFlow()


class TapoAlarmOptionsFlow(OptionsFlow):
    """Polling interval, session renewal and IP discovery options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                    vol.Required(
                        CONF_SESSION_RENEW,
                        default=self.config_entry.options.get(
                            CONF_SESSION_RENEW, DEFAULT_SESSION_RENEW
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=MAX_SESSION_RENEW)),
                    vol.Required(
                        CONF_DISCOVERY,
                        default=self.config_entry.options.get(
                            CONF_DISCOVERY, DEFAULT_DISCOVERY
                        ),
                    ): bool,
                }
            ),
        )
