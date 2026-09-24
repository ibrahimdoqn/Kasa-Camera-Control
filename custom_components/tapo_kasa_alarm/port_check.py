"""Watch the camera's HTTPS port for the connection diagnostic entities.

Every few seconds a TCP connection is opened to the camera's port 443 and
closed at once: no login, no TLS handshake, no data. This shows more than
ICMP ping does:

- accepted: the camera's main program (API, RTSP, alarm) is running
- refused: the camera is on the network but its main program is down,
  typically restarting after it crashed (as seen after alarm writes)
- no answer: the camera is not on the network (Wi-Fi, power, full reboot)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_PORT_CHECK_INTERVAL,
    DEFAULT_PORT_CHECK_INTERVAL,
    MAX_PORT_CHECK_INTERVAL,
    MIN_PORT_CHECK_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PORT = 443
CONNECT_TIMEOUT = 2  # seconds
# A single failed check can be a hiccup; the camera counts as disconnected
# after this many failures in a row. The outage starts at the first one.
FAILURES_TO_DISCONNECT = 2

REASON_RESTARTING = "restarting"
REASON_UNREACHABLE = "unreachable"


def port_check_interval(options: dict) -> timedelta:
    """The configured check interval, bounded."""
    seconds = options.get(CONF_PORT_CHECK_INTERVAL, DEFAULT_PORT_CHECK_INTERVAL)
    seconds = min(MAX_PORT_CHECK_INTERVAL, max(MIN_PORT_CHECK_INTERVAL, int(seconds)))
    return timedelta(seconds=seconds)


async def check_port(host: str, port: int = PORT) -> str | None:
    """None if the port accepts a connection, otherwise why not."""
    try:
        async with asyncio.timeout(CONNECT_TIMEOUT):
            _, writer = await asyncio.open_connection(host, port)
    except ConnectionRefusedError:
        return REASON_RESTARTING
    except (TimeoutError, OSError):
        return REASON_UNREACHABLE
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    return None


@dataclass(frozen=True)
class ConnectionState:
    """What the connection entities show. Changes only on connect/disconnect."""

    connected: bool | None = None  # None until the first result
    up_since: datetime | None = None
    down_since: datetime | None = None
    last_disconnect: datetime | None = None
    last_disconnect_reason: str | None = None
    last_outage_seconds: int | None = None


class PortCheckCoordinator(DataUpdateCoordinator[ConnectionState]):
    """Check the camera's port every few seconds and keep the connection history."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, host: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{host} port check",
            update_interval=port_check_interval(entry.options),
            # Entities are only told when the state really changes.
            always_update=False,
        )
        self.host = host
        self._failures = 0
        self._first_failure: datetime | None = None
        self._first_failure_reason: str | None = None

    async def _async_update_data(self) -> ConnectionState:
        state = self.data or ConnectionState()
        reason = await check_port(self.host)
        now = dt_util.utcnow()

        if reason is None:
            self._failures = 0
            if state.connected:
                return state
            outage = (
                round((now - state.down_since).total_seconds())
                if state.down_since
                else state.last_outage_seconds
            )
            if state.down_since:
                _LOGGER.info(
                    "%s port %s answers again after %s seconds (%s)",
                    self.host, PORT, outage, state.last_disconnect_reason,
                )
            return replace(
                state, connected=True, up_since=now, down_since=None,
                last_outage_seconds=outage,
            )

        if self._failures == 0:
            self._first_failure = now
            self._first_failure_reason = reason
        self._failures += 1
        if state.connected is False or (
            state.connected and self._failures < FAILURES_TO_DISCONNECT
        ):
            return state
        _LOGGER.info(
            "%s port %s: %s", self.host, PORT, self._first_failure_reason
        )
        return replace(
            state,
            connected=False,
            up_since=None,
            down_since=self._first_failure,
            last_disconnect=self._first_failure,
            last_disconnect_reason=self._first_failure_reason,
        )
