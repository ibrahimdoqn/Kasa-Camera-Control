"""Polling coordinator, modelled on the TP-Link integration's coordinator.

Switch changes go through a write queue: the wanted value is kept until a
poll reads the same value back from the camera. Failed writes are retried
on the next poll and a value the camera already has is never written.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, KasaException, TapoAlarmApi, is_permanent_error
from .const import (
    CONF_SCAN_INTERVAL,
    MAX_WRITE_MISMATCHES,
    MODE_LIGHT,
    MODE_SOUND,
    REQUEST_REFRESH_DELAY,
    scan_interval,
)

_LOGGER = logging.getLogger(__name__)

# Settings a switch can change. The alarm ones are written together.
ALARM_KEYS = ("enabled", MODE_SOUND, MODE_LIGHT)
NOTIFICATIONS = "notifications"


def camera_value(data: dict[str, Any] | None, key: str) -> bool | None:
    """Return a setting as read from the camera (None if unknown)."""
    if not data:
        return None
    if key == NOTIFICATIONS:
        push = data.get("push") or {}
        value = push.get("notification_enabled")
        return None if value is None else value == "on"
    alarm = data.get("alarm") or {}
    if key == "enabled":
        return alarm.get("enabled") == "on"
    modes = alarm.get("alarm_mode") or []
    if key == MODE_SOUND:
        # Some firmwares call the sound mode "siren".
        return MODE_SOUND in modes or "siren" in modes
    return key in modes


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
        # Write queue: setting -> wanted value, until the camera confirms it.
        self.pending: dict[str, bool] = {}
        # Writes the camera accepted but did not apply, per setting.
        self._mismatches: dict[str, int] = {}
        # When each queued setting was last written successfully. A poll only
        # verifies a write if it started reading after that write.
        self._written: dict[str, float] = {}
        self._write_lock = asyncio.Lock()

    async def _async_update_data(self) -> dict[str, Any]:
        read_started = time.monotonic()
        try:
            data = await self.api.get_state()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed on update: {err}") from err
        except KasaException as err:
            raise UpdateFailed(f"Error on update: {err}") from err
        await self._async_verify_and_retry(data, read_started)
        return data

    # --- Write queue -----------------------------------------------------

    def value(self, key: str) -> bool | None:
        """Value to show: the queued value while a write is pending."""
        if key in self.pending:
            return self.pending[key]
        return camera_value(self.data, key)

    async def async_set(self, key: str, value: bool) -> None:
        """Queue a setting and write it now.

        Nothing is written when the value is already queued, or when nothing
        is queued for the setting and the camera already has the value.
        Temporary failures keep the value queued for the next poll; a
        command the camera rejects is dropped and reported.
        """
        async with self._write_lock:
            if key in self.pending:
                if self.pending[key] == value:
                    return
            elif camera_value(self.data, key) == value:
                return
            self.pending[key] = value
            self._mismatches.pop(key, None)
            self._written.pop(key, None)
            self.async_update_listeners()
            await self._async_write(self.data, raise_errors=True, keys={key})
        await self.async_request_refresh()

    async def _async_verify_and_retry(
        self, data: dict[str, Any], read_started: float
    ) -> None:
        """Check queued settings against what the camera reports."""
        async with self._write_lock:
            for key in list(self.pending):
                written = self._written.get(key)
                if written is not None and written > read_started:
                    # Written while this poll was reading: the data is older
                    # than the write, the next poll verifies it.
                    continue
                if camera_value(data, key) == self.pending[key]:
                    _LOGGER.debug("%s: %s confirmed", self.name, key)
                    self._drop(key)
                elif written is not None:
                    # Accepted but not applied: write again, but not forever.
                    count = self._mismatches.get(key, 0) + 1
                    self._mismatches[key] = count
                    if count > MAX_WRITE_MISMATCHES:
                        _LOGGER.error(
                            "%s: the camera does not keep %s=%s after %s writes,"
                            " giving up",
                            self.name,
                            key,
                            self.pending[key],
                            count,
                        )
                        self._drop(key)
            # Write what is still queued, except writes this poll cannot judge yet.
            if retry := {
                key
                for key in self.pending
                if (written := self._written.get(key)) is None or written <= read_started
            }:
                await self._async_write(data, raise_errors=False, keys=retry)

    def _drop(self, key: str) -> None:
        self.pending.pop(key, None)
        self._mismatches.pop(key, None)
        self._written.pop(key, None)

    async def _async_write(
        self,
        data: dict[str, Any],
        *,
        raise_errors: bool,
        keys: set[str] | None = None,
    ) -> None:
        """Write queued settings: the alarm ones together in one request.

        Alarm settings that are queued but not in ``keys`` are still sent
        with their queued value, so one write never undoes another.
        """
        wanted = set(self.pending) if keys is None else keys
        groups: list[tuple[list[str], Callable[[], Awaitable[Any]]]] = []
        if any(key in wanted for key in ALARM_KEYS):
            alarm_keys = [key for key in ALARM_KEYS if key in self.pending]
            changes = {key: self.pending[key] for key in alarm_keys}
            groups.append(
                (alarm_keys, lambda: self.api.set_alarm(data["alarm"], **changes))
            )
        if NOTIFICATIONS in wanted and NOTIFICATIONS in self.pending:
            enabled = self.pending[NOTIFICATIONS]
            groups.append(([NOTIFICATIONS], lambda: self.api.set_notifications(enabled)))

        for group, write in groups:
            try:
                await write()
            except AuthenticationError as err:
                # Keep it queued; it is written again after reauth.
                self.config_entry.async_start_reauth(self.hass)
                for key in group:
                    self._written.pop(key, None)
                if raise_errors:
                    raise HomeAssistantError(
                        f"Authentication failed writing {', '.join(group)}: {err}"
                    ) from err
            except (KasaException, ValueError) as err:
                if is_permanent_error(err):
                    for key in group:
                        self._drop(key)
                    self.async_update_listeners()
                    msg = f"{self.name}: the camera rejected {', '.join(group)}: {err}"
                    if raise_errors:
                        raise HomeAssistantError(msg) from err
                    _LOGGER.error(msg)
                else:
                    for key in group:
                        self._written.pop(key, None)
                    _LOGGER.warning(
                        "%s: writing %s failed, will retry on the next update: %s",
                        self.name,
                        ", ".join(group),
                        err,
                    )
            else:
                now = time.monotonic()
                for key in group:
                    self._written[key] = now

    # --- One-shot commands -----------------------------------------------

    async def async_reboot(self) -> None:
        """Reboot the camera. It is unreachable for a while, so no refresh."""
        try:
            await self.api.reboot()
        except AuthenticationError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(f"Authentication failed on reboot: {err}") from err
        except TimeoutError as err:
            raise HomeAssistantError(f"Timeout on reboot: {err}") from err
        except KasaException as err:
            raise HomeAssistantError(f"Error on reboot: {err}") from err
