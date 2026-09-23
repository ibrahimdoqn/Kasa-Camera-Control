"""Thin wrapper around python-kasa for the Tapo camera alarm endpoints.

python-kasa is the library used by Home Assistant's built-in TP-Link
integration. Only a single session is kept open per camera and every
request is serialized, so the camera never sees parallel logins.
"""

from __future__ import annotations

import asyncio
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


# The calls Tapo Control uses to read the alarm config, tried in this order.
# variant -> (getter method, params)
ALARM_VARIANTS: dict[str, tuple[str, dict[str, Any]]] = {
    "last": ("getLastAlarmInfo", {"msg_alarm": {"name": [ALARM_SECTION]}}),
    "alert": (
        "getAlertConfig",
        {"msg_alarm": {"name": [ALARM_SECTION], "table": ["usr_def_audio"]}},
    ),
    "config": ("getAlarmConfig", {"msg_alarm": {}}),
}


def _section(result: dict[str, Any], module: str, section: str) -> dict[str, Any] | None:
    info = result.get(module, result).get(section)
    return info if isinstance(info, dict) else None


def _alarm_info(result: dict[str, Any]) -> dict[str, Any]:
    info = _section(result, "msg_alarm", ALARM_SECTION)
    if info is None:
        # getAlarmConfig returns the fields without a section.
        info = result.get("msg_alarm", result)
    if not isinstance(info, dict) or "enabled" not in info:
        raise KasaException(f"Unexpected alarm response: {result}")
    return info


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
        self._variant: str | None = None

    async def _query(self, request: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            return await self.device.protocol.query(request)

    async def _call(self, method: str, params: dict[str, Any]) -> None:
        resp = await self._query({method: params})
        if isinstance(resp.get(method), SmartErrorCode):
            raise KasaException(f"{method} failed: {resp[method].name}")

    async def get_state(self) -> dict[str, Any]:
        """Read alarm and notification config in one multipleRequest.

        Cameras expose the alarm config through different calls depending on
        model and firmware. The first one that answers is remembered for
        later polls and writes.
        """
        variants = [self._variant] if self._variant else list(ALARM_VARIANTS)
        errors = []
        for variant in variants:
            method, params = ALARM_VARIANTS[variant]
            resp = await self._query(
                {
                    method: params,
                    "getMsgPushConfig": {"msg_push": {"name": [PUSH_SECTION]}},
                }
            )
            try:
                alarm = _alarm_info(_unwrap(resp, method))
            except KasaException as err:
                _LOGGER.debug("%s not usable: %s", method, err)
                errors.append(str(err))
                continue
            if self._variant != variant:
                _LOGGER.debug("Using %s for the alarm config", method)
                self._variant = variant
            try:
                push = _section(_unwrap(resp, "getMsgPushConfig"), "msg_push", PUSH_SECTION)
            except KasaException as err:
                _LOGGER.debug("Notification config not available: %s", err)
                push = None
            return {"alarm": alarm, "push": push}
        raise KasaException("; ".join(errors))

    async def set_alarm(
        self, current: dict[str, Any], *, enabled: bool | None = None,
        sound: bool | None = None, light: bool | None = None,
    ) -> dict[str, Any]:
        """Change the alarm, keeping the options that are not changed."""
        modes = list(current.get("alarm_mode") or [MODE_SOUND, MODE_LIGHT])
        # Some firmwares call the sound mode "siren".
        sound_mode = "siren" if "siren" in modes else MODE_SOUND
        for mode, value in ((sound_mode, sound), (MODE_LIGHT, light)):
            if value is True and mode not in modes:
                modes.append(mode)
            elif value is False and mode in modes:
                modes.remove(mode)
        if not modes:
            raise ValueError("At least one of sound or light must stay enabled")
        is_on = current.get("enabled") == "on" if enabled is None else enabled
        state = "on" if is_on else "off"

        if self._variant == "alert":
            new = {
                **current,
                "enabled": state,
                "alarm_mode": modes,
                "sound_alarm_enabled": "on" if sound_mode in modes else "off",
                "light_alarm_enabled": "on" if MODE_LIGHT in modes else "off",
            }
            await self._call("setAlertConfig", {"msg_alarm": {ALARM_SECTION: new}})
        elif self._variant == "config":
            new = {"enabled": state, "alarm_mode": modes}
            await self._call("setAlarmConfig", {"msg_alarm": new})
        else:
            new = {
                "alarm_type": current.get("alarm_type", "0"),
                "light_type": current.get("light_type", "0"),
                "enabled": state,
                "alarm_mode": modes,
            }
            # Same raw request pytapo sends for cameras; setAlarmConfig with
            # this layout fails with PROTOCOL_FORMAT_ERROR on C5x0.
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
        await self._call("setMsgPushConfig", {"msg_push": {PUSH_SECTION: params}})
        return params

    async def close(self) -> None:
        """Close the session."""
        await self.device.disconnect()
