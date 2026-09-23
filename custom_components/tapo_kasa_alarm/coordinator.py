"""Polling coordinator for the camera alarm and notification state."""

from __future__ import annotations

import logging
from typing import Any

from kasa.exceptions import DeviceError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AuthenticationError, KasaException, TapoAlarmApi
from .const import (
    CONF_SCAN_INTERVAL,
    DOMAIN,
    REDISCOVERY_AFTER_FAILURES,
    REDISCOVERY_INTERVAL,
    scan_interval,
)
from .discovery import async_update_host

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
        self._failures = 0
        self._last_rediscovery = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.get_state()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except KasaException as err:
            if not isinstance(err, DeviceError):
                # The camera did not answer at all, it may have a new IP.
                await self._async_maybe_rediscover()
            raise UpdateFailed(str(err)) from err
        self._failures = 0
        return data

    async def _async_maybe_rediscover(self) -> None:
        self._failures += 1
        now = dt_util.utcnow()
        if self._failures < REDISCOVERY_AFTER_FAILURES or (
            self._last_rediscovery and now - self._last_rediscovery < REDISCOVERY_INTERVAL
        ):
            return
        self._last_rediscovery = now
        if await async_update_host(self.hass, self.config_entry):
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    async def async_set_alarm(self, **changes: bool) -> None:
        """Write alarm settings and publish the new state immediately."""
        try:
            new = await self.api.set_alarm(self.data["alarm"], **changes)
        except (KasaException, ValueError) as err:
            raise HomeAssistantError(f"Could not set alarm: {err}") from err
        self.async_set_updated_data({**self.data, "alarm": new})

    async def async_set_notifications(self, enabled: bool) -> None:
        """Write notification setting and publish the new state immediately."""
        try:
            new = await self.api.set_notifications(enabled)
        except KasaException as err:
            raise HomeAssistantError(f"Could not set notifications: {err}") from err
        self.async_set_updated_data(
            {**self.data, "push": {**(self.data.get("push") or {}), **new}}
        )
