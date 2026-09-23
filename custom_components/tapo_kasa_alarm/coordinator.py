"""Polling coordinator for the camera alarm and notification state."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, KasaException, TapoAlarmApi
from .const import CONF_SCAN_INTERVAL, DOMAIN, scan_interval

_LOGGER = logging.getLogger(__name__)


class TapoAlarmCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll alarm + notification config, one light request per interval.

    data = {"alarm": {...}, "push": {...} | None}
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: TapoAlarmApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=scan_interval(entry.options.get(CONF_SCAN_INTERVAL)),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.get_state()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except KasaException as err:
            raise UpdateFailed(str(err)) from err

    async def async_set_alarm(self, **changes: bool) -> None:
        """Write alarm settings and publish the new state immediately."""
        try:
            new = await self.api.set_alarm(self.data["alarm"], **changes)
        except (KasaException, ValueError) as err:
            raise HomeAssistantError(f"Could not set alarm: {err}") from err
        self.async_set_updated_data({**self.data, "alarm": new})

    async def async_set_notifications(self, **changes: bool) -> None:
        """Write notification settings and publish the new state immediately."""
        try:
            new = await self.api.set_notifications(**changes)
        except KasaException as err:
            raise HomeAssistantError(f"Could not set notifications: {err}") from err
        self.async_set_updated_data(
            {**self.data, "push": {**(self.data.get("push") or {}), **new}}
        )
