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
from kasa.exceptions import SmartErrorCode, _ConnectionError

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


# The alarm config is read and written with getAlertConfig / setAlertConfig,
# the current camera API. The older getLastAlarmInfo + raw "set" and
# getAlarmConfig / setAlarmConfig calls (used by pytapo / Tapo Control) are
# not used: writing the alarm that way was seen together with the camera
# restarting its services (RTSP dropped), while the camera already using
# setAlertConfig did not show this.
ALARM_READ = (
    "getAlertConfig",
    {"msg_alarm": {"name": [ALARM_SECTION], "table": ["usr_def_audio"]}},
)


def _section(result: dict[str, Any], module: str, section: str) -> dict[str, Any] | None:
    info = result.get(module, result).get(section)
    return info if isinstance(info, dict) else None


def _alarm_info(result: dict[str, Any]) -> dict[str, Any]:
    info = _section(result, "msg_alarm", ALARM_SECTION)
    if info is None or "enabled" not in info:
        raise KasaException(f"Unexpected alarm response: {result}")
    return info


def alarm_modes(alarm: dict[str, Any]) -> list[str]:
    """Sound/light modes of the alarm config.

    getAlertConfig reports both alarm_mode and sound/light_alarm_enabled;
    the enabled flags win when present.
    """
    modes = list(alarm.get("alarm_mode") or [])
    for mode, flag in ((MODE_SOUND, "sound_alarm_enabled"), (MODE_LIGHT, "light_alarm_enabled")):
        if flag not in alarm:
            continue
        present = mode in modes or (mode == MODE_SOUND and "siren" in modes)
        if alarm[flag] == "on" and not present:
            modes.append(mode)
        elif alarm[flag] == "off" and present:
            modes = [m for m in modes if m != mode and not (mode == MODE_SOUND and m == "siren")]
    return modes


def disconnect_reason(err: BaseException) -> str:
    """Classify why a poll failed, for the diagnostic sensors.

    reboot: the camera is on the network but refuses the connection
            (ConnectionRefusedError, errno 111), typically while it restarts
    unreachable: the camera is not on the network (e.g. errno 113, Wi-Fi drop)
    timeout: the camera did not answer in time
    auth: the login was rejected
    error: anything else (e.g. an error answer from the camera)
    """
    if isinstance(err, AuthenticationError):
        return "auth"
    seen: set[int] = set()
    todo: list[Any] = [err]
    connection = False
    while todo:
        item = todo.pop()
        if not isinstance(item, BaseException) or id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, ConnectionRefusedError):
            return "reboot"
        if isinstance(item, _ConnectionError):
            connection = True
        todo.extend(
            [item.__cause__, item.__context__, getattr(item, "os_error", None), *item.args]
        )
    if connection:
        return "unreachable"
    if isinstance(err, TimeoutError):
        return "timeout"
    return "error"


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

    async def _query_with_recovery(self, request: dict[str, Any]) -> dict[str, Any]:
        """Query like python-kasa's device.update() does for the TP-Link integration.

        If the combined request fails (for example the camera ended the
        session and answers 401), python-kasa has already reset the session.
        device.update() then asks each question again on its own, with a new
        login, and only marks the failing ones as errors. That is why the
        TP-Link integration does not go unavailable when a session expires.
        Authentication errors are not recovered, so reauth still starts.
        Connection errors and timeouts are not either: python-kasa has already
        retried those 3 times and the camera is not answering, asking again
        one by one would only make the poll take much longer.
        """
        try:
            return await self._query(request)
        except (AuthenticationError, TimeoutError, _ConnectionError):
            raise
        except Exception as err:  # noqa: BLE001 - same as python-kasa's update
            _LOGGER.warning(
                "Error querying %s for %s, asking again one by one: %s",
                self.device.host,
                ", ".join(request),
                err,
            )
        responses: dict[str, Any] = {}
        for method, params in request.items():
            try:
                responses[method] = (await self._query({method: params}))[method]
            except AuthenticationError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Error querying %s for %s: %s", self.device.host, method, err
                )
                responses[method] = SmartErrorCode.INTERNAL_QUERY_ERROR
        return responses

    async def get_state(self) -> dict[str, Any]:
        """Read the alarm and notification config in one multipleRequest."""
        method, params = ALARM_READ
        resp = await self._query_with_recovery(
            {
                method: params,
                "getMsgPushConfig": {"msg_push": {"name": [PUSH_SECTION]}},
            }
        )
        try:
            alarm = _alarm_info(_unwrap(resp, method))
        except KasaException as err:
            raise KasaException(
                f"{self.device.host} does not answer {method}, the only alarm call"
                f" this integration uses (older calls were removed in 1.6.5): {err}"
            ) from err
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
        """Change the alarm with setAlertConfig.

        Only the changed field is sent, like the Tapo app does with this
        call: {"enabled": ...} to turn the alarm on/off, {"alarm_mode": ...}
        to change sound/light. The rest of the config (volume, duration,
        light type, ...) is not written again.
        """
        new: dict[str, Any] = {}
        if enabled is not None:
            new["enabled"] = "on" if enabled else "off"
        if sound is not None or light is not None:
            modes = alarm_modes(current)
            # Some firmwares call the sound mode "siren".
            sound_mode = "siren" if "siren" in modes else MODE_SOUND
            for mode, value in ((sound_mode, sound), (MODE_LIGHT, light)):
                if value is True and mode not in modes:
                    modes.append(mode)
                elif value is False and mode in modes:
                    modes.remove(mode)
            if not modes:
                raise ValueError("At least one of sound or light must stay enabled")
            new["alarm_mode"] = modes
        if not new:
            return new
        await self._call("setAlertConfig", {"msg_alarm": {ALARM_SECTION: new}})
        return new

    async def set_notifications(self, enabled: bool) -> dict[str, str]:
        """Turn app push notifications on/off."""
        params = {"notification_enabled": "on" if enabled else "off"}
        await self._call("setMsgPushConfig", {"msg_push": {PUSH_SECTION: params}})
        return params

    async def close(self) -> None:
        """Close the session."""
        await self.device.disconnect()
