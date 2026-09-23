"""Polling coordinator, modelled on the TP-Link integration's coordinator."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    AuthenticationError,
    KasaException,
    TapoAlarmApi,
    debug_error,
    debug_json,
    disconnect_reason,
)
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
        # Connection diagnostics (shown by the diagnostic sensors).
        self.connected_since: datetime | None = dt_util.utcnow()
        self.down_since: datetime | None = None
        self.disconnects = 0
        self.last_disconnect: datetime | None = None
        self.last_disconnect_reason: str | None = None
        self.last_outage_seconds: int | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        self.api.dbg("poll started")
        try:
            data = await self.api.get_state()
        except AuthenticationError as err:
            self._connection_lost(err)
            self.api.dbg("poll failed (auth): %s", debug_error(err))
            raise ConfigEntryAuthFailed(f"Authentication failed on update: {err}") from err
        except KasaException as err:
            self._connection_lost(err)
            self.api.dbg("poll failed: %s", debug_error(err))
            raise UpdateFailed(f"Error on update: {err}") from err
        self._connection_ok()
        if self.api.debug:
            self._debug_changes(data)
        return data

    def _debug_changes(self, data: dict[str, Any]) -> None:
        """Log the polled state and what changed since the last poll."""
        old = self.data or {}
        changes = []
        for part in ("alarm", "push"):
            before, after = old.get(part) or {}, data.get(part) or {}
            for key in sorted(set(before) | set(after)):
                if before.get(key) != after.get(key):
                    changes.append(f"{part}.{key}: {before.get(key)!r} -> {after.get(key)!r}")
        self.api.dbg(
            "poll ok, %s; state %s",
            "changed: " + ", ".join(changes) if changes and old else "no change"
            if old
            else "first poll",
            debug_json(data),
        )

    def _connection_lost(self, err: Exception) -> None:
        """Count a disconnect once per outage (a run of failed polls)."""
        if self.down_since is not None:
            return
        now = dt_util.utcnow()
        self.down_since = now
        self.connected_since = None
        self.disconnects += 1
        self.last_disconnect = now
        self.last_disconnect_reason = disconnect_reason(err)
        _LOGGER.info(
            "%s: connection lost (%s): %s", self.name, self.last_disconnect_reason, err
        )
        self.api.dbg(
            "connection lost (%s), disconnect #%s", self.last_disconnect_reason, self.disconnects
        )

    def _connection_ok(self) -> None:
        if self.down_since is None:
            return
        now = dt_util.utcnow()
        self.last_outage_seconds = round((now - self.down_since).total_seconds())
        _LOGGER.info(
            "%s: connection back after %s seconds", self.name, self.last_outage_seconds
        )
        self.api.dbg("connection back after %s seconds", self.last_outage_seconds)
        self.down_since = None
        self.connected_since = now

    async def async_command(
        self,
        func: Callable[[], Awaitable[Any]],
        name: str,
        *,
        refresh: bool = True,
    ) -> None:
        """Run a command, map errors and refresh after, like the TP-Link integration."""
        self.api.dbg("command %s started", name)
        started = time.monotonic()
        try:
            await func()
        except Exception as err:
            self.api.dbg(
                "command %s failed after %.3fs: %s",
                name,
                time.monotonic() - started,
                debug_error(err),
            )
            await self._raise_command_error(name, err)
        self.api.dbg("command %s done in %.3fs", name, time.monotonic() - started)
        if refresh:
            await self.async_request_refresh()

    async def _raise_command_error(self, name: str, err: Exception) -> None:
        """Map a command error like the TP-Link integration."""
        try:
            raise err
        except AuthenticationError:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(f"Authentication failed on {name}: {err}") from err
        except TimeoutError as err:
            raise HomeAssistantError(f"Timeout on {name}: {err}") from err
        except (KasaException, ValueError) as err:
            raise HomeAssistantError(f"Error on {name}: {err}") from err

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
