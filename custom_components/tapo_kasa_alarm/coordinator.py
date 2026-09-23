"""Polling coordinator, modelled on the TP-Link integration's coordinator."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, KasaException, TapoAlarmApi
from .const import CONF_SCAN_INTERVAL, REQUEST_REFRESH_DELAY, scan_interval

_LOGGER = logging.getLogger(__name__)


class TapoAlarmCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the alarm and notification config, like the TP-Link coordinator.

    Only what the entities use is read: one request per poll. The full
    device.update() the TP-Link integration polls is not needed here.

    data = {"alarm": {...}, "push": {...} | None}
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: TapoAlarmApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=api.device.host,
            update_interval=scan_interval(entry.options.get(CONF_SCAN_INTERVAL)),
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.get_state()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed on update: {err}") from err
        except KasaException as err:
            raise UpdateFailed(f"Error on update: {err}") from err

    async def async_command(
        self,
        func: Callable[[], Awaitable[Any]],
        name: str,
        *,
        refresh: bool = True,
    ) -> None:
        """Run a command, map errors and refresh after, like the TP-Link integration."""
        try:
            await func()
        except AuthenticationError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(f"Authentication failed on {name}: {err}") from err
        except TimeoutError as err:
            raise HomeAssistantError(f"Timeout on {name}: {err}") from err
        except (KasaException, ValueError) as err:
            raise HomeAssistantError(f"Error on {name}: {err}") from err
        if refresh:
            await self.async_request_refresh()

    async def async_set_alarm(self, **changes: bool) -> None:
        """Write alarm settings."""
        await self.async_command(
            lambda: self.api.set_alarm(self.data["alarm"], **changes), "set alarm"
        )

    async def async_set_notifications(self, enabled: bool) -> None:
        """Write the notification setting."""
        await self.async_command(
            lambda: self.api.set_notifications(enabled), "set notifications"
        )

    async def async_reboot(self) -> None:
        """Reboot the camera. It is unreachable for a while, so no refresh."""
        await self.async_command(self.api.reboot, "reboot", refresh=False)
