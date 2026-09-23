"""Thin wrapper around python-kasa for the Tapo camera alarm endpoints.

python-kasa is the library used by Home Assistant's built-in TP-Link
integration, and the camera is connected the same way that integration
does it. Only a single session is kept open per camera and every request
is serialized, so the camera never sees parallel logins.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from aiohttp import ClientSession
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

from .const import (
    ALARM_SECTION,
    DEFAULT_TIMEOUT,
    DISCOVERY_TIMEOUT,
    MODE_LIGHT,
    MODE_SOUND,
    PUSH_SECTION,
)

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "AuthenticationError",
    "KasaException",
    "TapoAlarmApi",
    "connect_device",
    "discover_macs",
]


DEFAULT_CONNECTION = DeviceConnectionParameters(
    device_family=DeviceFamily.SmartIpCamera,
    encryption_type=DeviceEncryptionType.Aes,
    https=True,
)


async def connect_device(
    host: str,
    username: str,
    password: str,
    *,
    http_client: ClientSession | None = None,
    connection_parameters: dict[str, Any] | None = None,
) -> Device:
    """Connect to a Tapo camera the same way the TP-Link integration does.

    The stored connection parameters (saved after the first successful
    connection) are used directly; discovery is only a fallback when the
    camera does not accept the default camera parameters.
    """
    credentials = Credentials(username, password)
    connection_type = DEFAULT_CONNECTION
    if connection_parameters:
        try:
            connection_type = DeviceConnectionParameters.from_dict(connection_parameters)
        except (KasaException, TypeError, ValueError, LookupError):
            _LOGGER.warning(
                "Invalid connection parameters for %s: %s", host, connection_parameters
            )
    config = DeviceConfig(
        host=host,
        credentials=credentials,
        timeout=DEFAULT_TIMEOUT,
        connection_type=connection_type,
        http_client=http_client,
    )
    try:
        return await Device.connect(config=config)
    except AuthenticationError:
        raise
    except KasaException as err:
        if connection_parameters:
            raise
        _LOGGER.debug("Direct camera connect to %s failed (%s), trying discovery", host, err)

    device = await Discover.discover_single(
        host, credentials=credentials, timeout=DEFAULT_TIMEOUT
    )
    if device is None:
        raise KasaException(f"Device {host} not found")
    await device.update()
    return device


async def discover_macs(broadcast_addresses: list[str]) -> dict[str, str]:
    """Return {mac: host} of TP-Link devices answering the UDP discovery.

    Discovery only listens for the devices' broadcast answers; it does not
    log in to anything (the same discovery the TP-Link integration runs).
    """
    found: dict[str, str] = {}
    results = await asyncio.gather(
        *(
            Discover.discover(target=address, discovery_timeout=DISCOVERY_TIMEOUT)
            for address in broadcast_addresses
        ),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, BaseException):
            _LOGGER.debug("Discovery failed: %s", result)
            continue
        for device in result.values():
            try:
                if device.mac:
                    found[device.mac] = device.host
            except Exception:  # noqa: BLE001 - one odd device must not stop discovery
                _LOGGER.debug("No MAC in discovery answer from %s", device.host)
            await device.protocol.close()
    return found


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

    def __init__(self, device: Device, session_renew_minutes: float = 0) -> None:
        self.device = device
        self._lock = asyncio.Lock()
        self._variant: str | None = None
        # The device was just connected, so a fresh session exists.
        self._session_started = time.monotonic()
        self.session_renew_minutes = session_renew_minutes

    async def _query(self, request: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            await self._renew_session_if_due()
            return await self.device.protocol.query(request)

    async def _renew_session_if_due(self) -> None:
        """Log in again before the camera ends the session.

        Cameras end the session about 10 minutes after login and answer the
        next request with HTTP 401. Closing the protocol drops the old
        session (cameras have no logout call; the camera expires it) and
        python-kasa logs in again on the next request. The Home Assistant
        HTTP session is not closed, python-kasa only closes its own.
        """
        if not self.session_renew_minutes:
            return
        now = time.monotonic()
        if now - self._session_started < self.session_renew_minutes * 60:
            return
        _LOGGER.debug("Renewing the session with %s", self.device.host)
        await self.device.protocol.close()
        self._session_started = now

    async def reboot(self) -> None:
        """Reboot the camera (the call Tapo Control uses for cameras).

        python-kasa's own reboot sends a plug/bulb command that cameras do
        not know, so the camera method is sent directly.
        """
        await self._call("rebootDevice", {"system": {"reboot": "null"}})

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

    async def set_notifications(self, enabled: bool) -> dict[str, str]:
        """Turn app push notifications on/off."""
        params = {"notification_enabled": "on" if enabled else "off"}
        await self._call("setMsgPushConfig", {"msg_push": {PUSH_SECTION: params}})
        return params

    async def close(self) -> None:
        """Close the session."""
        await self.device.disconnect()
