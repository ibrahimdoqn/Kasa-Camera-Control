"""Thin wrapper around python-kasa for the Tapo camera alarm endpoints.

python-kasa is the library used by Home Assistant's built-in TP-Link
integration. Only a single session is kept open per camera and every
request is serialized, so the camera never sees parallel logins.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging
from typing import Any

from kasa import (
    AuthenticationError,
    Credentials,
    Device,
    DeviceConfig,
    DeviceConnectionParameters,
    DeviceEncryptionType,
    DeviceFamily,
    Discover,
    KasaException,
)
from kasa.exceptions import SmartErrorCode

from .const import ALARM_SECTION, DEFAULT_TIMEOUT, MODE_LIGHT, MODE_SOUND, PUSH_SECTION

_LOGGER = logging.getLogger(__name__)

__all__ = ["AuthenticationError", "KasaException", "TapoAlarmApi", "connect_device"]


async def connect_device(host: str, username: str, password: str) -> Device:
    """Connect to a Tapo camera the same way the TP-Link integration does."""
    credentials = Credentials(username, password)
    config = DeviceConfig(
        host=host,
        credentials=credentials,
        timeout=DEFAULT_TIMEOUT,
        connection_type=DeviceConnectionParameters(
            device_family=DeviceFamily.SmartIpCamera,
            encryption_type=DeviceEncryptionType.Aes,
            https=True,
        ),
    )
    try:
        return await Device.connect(config=config)
    except AuthenticationError:
        raise
    except KasaException as err:
        _LOGGER.debug("Direct camera connect to %s failed (%s), trying discovery", host, err)

    device = await Discover.discover_single(
        host, credentials=credentials, timeout=DEFAULT_TIMEOUT
    )
    if device is None:
        raise KasaException(f"Device {host} not found")
    await device.update()
    return device


def _section(result: dict[str, Any], module: str, section: str) -> dict[str, Any] | None:
    info = result.get(module, result).get(section)
    return info if isinstance(info, dict) else None


def _unwrap(resp: dict[str, Any], method: str) -> dict[str, Any]:
    result = resp.get(method)
    if isinstance(result, SmartErrorCode):
        raise KasaException(f"{method} failed: {result.name}")
    if not isinstance(result, dict):
        raise KasaException(f"Unexpected response for {method}: {resp}")
    return result


class TapoAlarmApi:
    """Alarm related calls on top of a connected python-kasa device."""

    def __init__(self, device: Device) -> None:
        self.device = device
        self._lock = asyncio.Lock()
        self._siren_call: Callable[[bool], Awaitable[None]] | None = None

    async def _query(self, request: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            return await self.device.protocol.query(request)

    async def get_state(self) -> dict[str, Any]:
        """Read alarm and notification config in one multipleRequest."""
        resp = await self._query(
            {
                "getLastAlarmInfo": {"msg_alarm": {"name": [ALARM_SECTION]}},
                "getMsgPushConfig": {"msg_push": {"name": [PUSH_SECTION]}},
            }
        )
        alarm = _section(_unwrap(resp, "getLastAlarmInfo"), "msg_alarm", ALARM_SECTION)
        if alarm is None:
            raise KasaException(f"Unexpected alarm response: {resp}")
        try:
            push = _section(_unwrap(resp, "getMsgPushConfig"), "msg_push", PUSH_SECTION)
        except KasaException as err:
            _LOGGER.debug("Notification config not available: %s", err)
            push = None
        return {"alarm": alarm, "push": push}

    async def set_alarm(
        self, current: dict[str, Any], *, enabled: bool | None = None,
        sound: bool | None = None, light: bool | None = None,
    ) -> dict[str, Any]:
        """Change the alarm, keeping the options that are not changed."""
        modes = list(current.get("alarm_mode") or [MODE_SOUND, MODE_LIGHT])
        for mode, value in ((MODE_SOUND, sound), (MODE_LIGHT, light)):
            if value is True and mode not in modes:
                modes.append(mode)
            elif value is False and mode in modes:
                modes.remove(mode)
        if not modes:
            raise ValueError("At least one of sound or light must stay enabled")

        is_on = current.get("enabled") == "on" if enabled is None else enabled
        new = {
            "alarm_type": current.get("alarm_type", "0"),
            "light_type": current.get("light_type", "0"),
            "enabled": "on" if is_on else "off",
            "alarm_mode": modes,
        }
        # Same raw request pytapo sends for cameras; setAlarmConfig is only
        # accepted by hub child devices and fails with PROTOCOL_FORMAT_ERROR.
        await self._query({"set": {"msg_alarm": {ALARM_SECTION: new}}})
        return {**current, **new}

    async def set_notifications(
        self, *, enabled: bool | None = None, rich: bool | None = None
    ) -> dict[str, str]:
        """Turn app push notifications (and rich notifications) on/off."""
        params: dict[str, str] = {}
        if enabled is not None:
            params["notification_enabled"] = "on" if enabled else "off"
        if rich is not None:
            params["rich_notification_enabled"] = "on" if rich else "off"
        method = "setMsgPushConfig"
        resp = await self._query({method: {"msg_push": {PUSH_SECTION: params}}})
        if isinstance(resp.get(method), SmartErrorCode):
            raise KasaException(f"{method} failed: {resp[method].name}")
        return params

    async def manual_alarm(self, start: bool) -> None:
        """Start or stop the siren right now.

        Cameras differ in which call they accept, so try the known variants
        (same order as Tapo Control) and remember the one that worked.
        """
        variants = [self._manual_alarm_do, self._siren_status]
        if self._siren_call is not None:
            variants.remove(self._siren_call)
            variants.insert(0, self._siren_call)
        errors = []
        for call in variants:
            try:
                await call(start)
            except KasaException as err:
                _LOGGER.debug("%s failed: %s", call.__name__, err)
                errors.append(str(err))
                continue
            self._siren_call = call
            return
        raise KasaException("Camera does not support triggering the siren: " + "; ".join(errors))

    async def _manual_alarm_do(self, start: bool) -> None:
        await self._query(
            {"do": {"msg_alarm": {"manual_msg_alarm": {
                "action": "start" if start else "stop"
            }}}}
        )

    async def _siren_status(self, start: bool) -> None:
        method = "setSirenStatus"
        resp = await self._query(
            {method: {"msg_alarm": {"status": "on" if start else "off"}}}
        )
        if isinstance(resp.get(method), SmartErrorCode):
            raise KasaException(f"{method} failed: {resp[method].name}")

    async def close(self) -> None:
        """Close the session."""
        await self.device.disconnect()
