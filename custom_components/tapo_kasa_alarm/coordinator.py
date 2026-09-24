"""Polling coordinator for the alarm and notification config."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    UNREACHABLE_REASONS,
    AuthenticationError,
    CameraError,
    TapoAlarmApi,
    connection_reason,
)
from .const import AUTH_RETRIES, CONF_SCAN_INTERVAL, DOMAIN, scan_interval

_LOGGER = logging.getLogger(__name__)


def auth_failed(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Count a rejected login; True once it was rejected too often in a row.

    Like Tapo Control, the password is only asked for again after the
    login was rejected more than AUTH_RETRIES times in a row. The count
    is kept across setup retries and reset by the next successful poll.
    """
    failures = hass.data.setdefault(DOMAIN, {})
    failures[entry.entry_id] = failures.get(entry.entry_id, 0) + 1
    return failures[entry.entry_id] > AUTH_RETRIES


def auth_ok(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Forget earlier rejected logins."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)


class TapoAlarmCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the alarm and notification config.

    Only what the entities use is read: one request per poll, instead of
    the full getMost Tapo Control polls.

    data = {"alarm": {...}, "push": {...} | None}
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: TapoAlarmApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=api.host,
            update_interval=scan_interval(entry.options.get(CONF_SCAN_INTERVAL)),
        )
        self.api = api
        # Connection state for the diagnostic entities. The connection counts
        # from the first successful poll; it is lost when a poll fails, when
        # a command cannot reach the camera and when the camera is rebooted.
        self.connected_since: datetime | None = None
        self.down_since: datetime | None = None
        self.last_disconnect: datetime | None = None
        self.last_disconnect_reason: str | None = None
        self.last_disconnect_source: str | None = None
        self.last_outage_seconds: int | None = None

    @property
    def connected(self) -> bool:
        """Whether the camera answered and nothing has failed since."""
        return self.connected_since is not None

    def _connection_ok(self) -> None:
        now = dt_util.utcnow()
        if self.down_since is not None:
            self.last_outage_seconds = round((now - self.down_since).total_seconds())
            _LOGGER.info(
                "%s: connected again after %s seconds (%s)",
                self.name,
                self.last_outage_seconds,
                self.last_disconnect_reason,
            )
            self.down_since = None
        if self.connected_since is None:
            self.connected_since = now

    def _connection_lost(self, reason: str, source: str) -> None:
        """Mark the camera as not connected; an outage keeps its first cause."""
        if self.down_since is not None:
            return
        now = dt_util.utcnow()
        self.down_since = now
        self.connected_since = None
        self.last_disconnect = now
        self.last_disconnect_reason = reason
        self.last_disconnect_source = source

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.get_state()
        except AuthenticationError as err:
            self._connection_lost("auth", "poll")
            if auth_failed(self.hass, self.config_entry):
                raise ConfigEntryAuthFailed(
                    f"Authentication failed on update: {err}"
                ) from err
            raise UpdateFailed(f"Login rejected, trying again: {err}") from err
        except CameraError as err:
            self._connection_lost(connection_reason(err), "poll")
            raise UpdateFailed(f"Error on update: {err}") from err
        auth_ok(self.hass, self.config_entry)
        self._connection_ok()
        return data

    async def async_command(self, func: Callable[[], Awaitable[Any]], name: str) -> Any:
        """Run a command and map its errors.

        A rejected login is left to the polls, which ask for the password
        only after it was rejected several times in a row.
        """
        try:
            result = await func()
        except CameraError as err:
            if (reason := connection_reason(err)) in UNREACHABLE_REASONS:
                self._connection_lost(reason, "command")
                self.async_update_listeners()
            raise HomeAssistantError(f"Error on {name}: {err}") from err
        except ValueError as err:
            raise HomeAssistantError(f"Error on {name}: {err}") from err
        self._connection_ok()
        return result

    async def _read_then_write(
        self, write: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]], name: str
    ) -> dict[str, Any]:
        """Read the camera, then write only what differs from what it reports.

        The known state can be up to one poll old (for example the alarm was
        changed in the Tapo app meanwhile), so it is read fresh right before
        the write. Nothing is written when the camera is already as asked:
        writing the alarm sometimes makes the camera restart its services,
        reading never did.
        """
        fresh: dict[str, Any] = {}

        async def _run() -> dict[str, Any]:
            fresh.update(await self.api.get_state())
            return await write(fresh)

        sent = await self.async_command(_run, name)
        self.data = {**self.data, **fresh}
        return sent

    async def async_set_alarm(self, **changes: bool) -> None:
        """Write alarm settings.

        Like the Tapo app, the camera is not read again right after the
        write: the written fields are applied to the known state and the
        next regular poll (which starts over from now) confirms them. This
        way the camera is not asked for its config while it is still
        applying the new alarm setting.
        """
        sent = await self._read_then_write(
            lambda state: self.api.set_alarm(state["alarm"], **changes), "set alarm"
        )
        self.async_set_updated_data(
            {**self.data, "alarm": {**self.data["alarm"], **sent}}
        )

    async def async_set_notifications(self, enabled: bool) -> None:
        """Write the notification setting, like async_set_alarm."""
        sent = await self._read_then_write(
            lambda state: self.api.set_notifications(state["push"], enabled),
            "set notifications",
        )
        self.async_set_updated_data(
            {**self.data, "push": {**(self.data.get("push") or {}), **sent}}
        )

    async def async_reboot(self) -> None:
        """Reboot the camera. It is unreachable for a while, so no refresh."""
        await self.async_command(self.api.reboot, "reboot")
        self._connection_lost("reboot", "reboot")
        self.async_update_listeners()
