"""Config flow for Kasa Camera Control."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import AuthenticationError, CameraError, basic_info, connect
from .const import (
    CONF_CLOUD_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PASSWORD_SCHEMA = {
    vol.Required(CONF_CLOUD_PASSWORD): TextSelector(
        TextSelectorConfig(type=TextSelectorType.PASSWORD)
    )
}


def _validate(hass: HomeAssistant, host: str, cloud_password: str) -> dict[str, Any]:
    """Log in once (blocking) and return the camera's details."""
    controller = connect(hass, host, cloud_password)
    try:
        info = basic_info(controller)
        mac = info.get("mac")
        return {
            "unique_id": format_mac(mac) if mac else info.get("dev_id") or host,
            "title": info.get("device_alias") or info.get("device_model") or host,
        }
    finally:
        try:
            controller.close()
        except Exception:  # noqa: BLE001 - only a login test
            pass


class TapoAlarmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 2

    async def _async_validate(
        self, host: str, cloud_password: str, errors: dict[str, str]
    ) -> dict[str, Any] | None:
        try:
            return await self.hass.async_add_executor_job(
                _validate, self.hass, host, cloud_password
            )
        except AuthenticationError:
            errors["base"] = "invalid_auth"
        except CameraError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error")
            errors["base"] = "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            found = await self._async_validate(
                user_input[CONF_HOST], user_input[CONF_CLOUD_PASSWORD], errors
            )
            if found is not None:
                await self.async_set_unique_id(found["unique_id"])
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(title=found["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_HOST): str, **PASSWORD_SCHEMA}),
                {CONF_HOST: (user_input or {}).get(CONF_HOST)},
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
            found = await self._async_validate(
                entry.data[CONF_HOST], user_input[CONF_CLOUD_PASSWORD], errors
            )
            if found is not None:
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        CONF_HOST: entry.data[CONF_HOST],
                        CONF_CLOUD_PASSWORD: user_input[CONF_CLOUD_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(PASSWORD_SCHEMA),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the IP address or the cloud password."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            found = await self._async_validate(
                user_input[CONF_HOST], user_input[CONF_CLOUD_PASSWORD], errors
            )
            if found is not None:
                await self.async_set_unique_id(found["unique_id"])
                self._abort_if_unique_id_mismatch(reason="wrong_camera")
                return self.async_update_reload_and_abort(entry, data=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_HOST): str, **PASSWORD_SCHEMA}),
                {CONF_HOST: entry.data[CONF_HOST]},
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return TapoAlarmOptionsFlow()


class TapoAlarmOptionsFlow(OptionsFlow):
    """Polling interval option."""

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
                }
            ),
        )
