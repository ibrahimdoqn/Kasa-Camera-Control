"""Polling coordinator for the alarm and notification config."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, CameraError, TapoAlarmApi
from .const import AUTH_RETRIES, CONF_SCAN_INTERVAL, DOMAIN, scan_interval
from .port_check import PortCheckCoordinator

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
        # Watches the camera's port for the connection diagnostic entities.
        self.port_check: PortCheckCoordinator | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.get_state()
        except AuthenticationError as err:
            if auth_failed(self.hass, self.config_entry):
                raise ConfigEntryAuthFailed(
                    f"Authentication failed on update: {err}"
                ) from err
            raise UpdateFailed(f"Login rejected, trying again: {err}") from err
        except CameraError as err:
            raise UpdateFailed(f"Error on update: {err}") from err
        auth_ok(self.hass, self.config_entry)
        return data

    async def async_command(self, func: Callable[[], Awaitable[Any]], name: str) -> Any:
        """Run a command and map its errors.

        A rejected login is left to the polls, which ask for the password
        only after it was rejected several times in a row.
        """
        try:
            return await func()
        except (CameraError, ValueError) as err:
            raise HomeAssistantError(f"Error on {name}: {err}") from err

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
