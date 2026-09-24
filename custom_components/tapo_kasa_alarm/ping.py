"""Ping the camera for the connection diagnostic entities.

Done the way Home Assistant's Ping (ICMP) integration does it: icmplib,
privileged or unprivileged sockets, and the ping command when neither is
allowed. Pinging tells whether the camera is on the network; it does not
log in and puts no load on the camera's services.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from icmplib import NameLookupError, SocketPermissionError, async_ping

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PING_INTERVAL = timedelta(seconds=5)
PING_COUNT = 2  # the camera counts as reachable if any reply comes back
PING_TIMEOUT = 1  # seconds to wait for each reply
_PRIVILEGED_KEY = f"{DOMAIN}_ping_privileged"


async def _can_ping(privileged: bool) -> bool:
    try:
        await async_ping("127.0.0.1", count=0, timeout=0, privileged=privileged)
    except SocketPermissionError:
        return False
    return True


async def ping_mode(hass: HomeAssistant) -> bool | None:
    """True/False: icmplib with a privileged/unprivileged socket, None: ping command."""
    if _PRIVILEGED_KEY not in hass.data:
        if await _can_ping(True):
            mode: bool | None = True
        elif await _can_ping(False):
            mode = False
        else:
            _LOGGER.debug("No ICMP socket allowed, using the ping command")
            mode = None
        hass.data[_PRIVILEGED_KEY] = mode
    return hass.data[_PRIVILEGED_KEY]


async def ping(host: str, privileged: bool | None) -> float | None:
    """Round-trip time in ms, or None if the host did not answer."""
    if privileged is not None:
        try:
            result = await async_ping(
                host, count=PING_COUNT, timeout=PING_TIMEOUT, privileged=privileged
            )
        except NameLookupError:
            return None
        return result.avg_rtt if result.is_alive else None

    process = await asyncio.create_subprocess_exec(
        "ping", "-n", "-q", "-c", str(PING_COUNT), f"-W{PING_TIMEOUT}", host,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        close_fds=False,
    )
    try:
        async with asyncio.timeout(PING_COUNT * PING_TIMEOUT + 3):
            output, _ = await process.communicate()
    except TimeoutError:
        with suppress(ProcessLookupError):
            process.kill()
        return None
    if process.returncode != 0:
        return None
    # ".../avg/..." in the summary line (iputils and busybox)
    try:
        return float(output.decode().rsplit("=", 1)[-1].split("/")[1])
    except (IndexError, ValueError):
        return 0.0


@dataclass
class ConnectionState:
    """What the connection entities show."""

    connected: bool
    connected_since: datetime | None
    down_since: datetime | None
    last_disconnect: datetime | None
    last_outage_seconds: int | None
    latency_ms: float | None


class PingCoordinator(DataUpdateCoordinator[ConnectionState]):
    """Ping the camera every few seconds and keep the connection history."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, host: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{host} ping",
            update_interval=PING_INTERVAL,
        )
        self.host = host
        self._state = ConnectionState(
            connected=False,
            connected_since=None,
            down_since=None,
            last_disconnect=None,
            last_outage_seconds=None,
            latency_ms=None,
        )

    async def _async_update_data(self) -> ConnectionState:
        try:
            latency = await ping(self.host, await ping_mode(self.hass))
        except (OSError, SocketPermissionError) as err:
            # Pinging itself is not possible (e.g. no ping command): say so
            # instead of reporting the camera as disconnected.
            raise UpdateFailed(f"Cannot ping {self.host}: {err}") from err
        state = self._state
        now = dt_util.utcnow()
        if latency is not None:
            if state.down_since is not None:
                state.last_outage_seconds = round((now - state.down_since).total_seconds())
                _LOGGER.info(
                    "%s answers ping again after %s seconds",
                    self.host,
                    state.last_outage_seconds,
                )
                state.down_since = None
            if not state.connected:
                state.connected = True
                state.connected_since = now
            state.latency_ms = round(latency, 1)
        else:
            if state.connected or state.connected_since is None and state.down_since is None:
                state.down_since = now
                state.last_disconnect = now
            state.connected = False
            state.connected_since = None
            state.latency_ms = None
        return ConnectionState(**vars(state))
