"""Thin wrapper around pytapo for the Tapo camera alarm endpoints.

pytapo is the library used by the Tapo Control integration, and the camera
is connected the same way that integration does it: a camera account, or
"admin" with the TP-Link cloud password when one is given. pytapo is
blocking, so every call runs in the executor. Only a single session is kept
open per camera and every request is serialized, so the camera never sees
parallel logins.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import time
from typing import Any

from pytapo import Tapo
import requests

from homeassistant.core import HomeAssistant

from .const import ALARM_SECTION, MODE_LIGHT, MODE_SOUND, PUSH_SECTION

_LOGGER = logging.getLogger(__name__)
_PYTAPO_LOGGER = logging.getLogger(f"{__name__}.pytapo")

# pytapo raises plain exceptions; these messages mean the login was rejected.
_AUTH_MESSAGES = ("Invalid authentication data", "Invalid authentication")


class CameraError(Exception):
    """The camera could not be reached or rejected a request."""


class AuthenticationError(CameraError):
    """The camera rejected the login."""


def login_credentials(
    username: str, password: str, cloud_password: str
) -> tuple[str, str, str]:
    """(user, password, cloud password) to log in with, like Tapo Control.

    With a cloud password Tapo Control logs in as "admin" with it,
    otherwise with the camera account.
    """
    if cloud_password:
        return "admin", cloud_password, cloud_password
    return username, password, ""


def _wrap(err: Exception) -> CameraError:
    if isinstance(err, CameraError):
        return err
    if any(message in str(err) for message in _AUTH_MESSAGES):
        return AuthenticationError(str(err))
    return CameraError(str(err) or type(err).__name__)


def connect(
    hass: HomeAssistant | None,
    host: str,
    username: str,
    password: str,
    cloud_password: str = "",
    is_klap: bool | None = None,
) -> Tapo:
    """Log in to the camera the way Tapo Control does (blocking).

    Same pytapo settings as Tapo Control's registerController.
    """
    user, pwd, cloud = login_credentials(username, password, cloud_password)
    try:
        return Tapo(
            host,
            user,
            pwd,
            cloud,
            reuseSession=False,
            printDebugInformation=_PYTAPO_LOGGER.debug,
            printWarnInformation=_PYTAPO_LOGGER.warning,
            retryStok=False,
            isKLAP=is_klap,
            hass=hass,
        )
    except Exception as err:  # noqa: BLE001 - pytapo raises plain exceptions
        raise _wrap(err) from err


def basic_info(controller: Tapo) -> dict[str, Any]:
    """The camera's basic_info (model, alias, versions, MAC)."""
    info = controller.basicInfo
    if isinstance(info, dict):
        info = info.get("device_info", info).get("basic_info", info)
    return info if isinstance(info, dict) else {}


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
    timeout = connection = False
    while todo:
        item = todo.pop()
        if not isinstance(item, BaseException) or id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, ConnectionRefusedError):
            return "reboot"
        if isinstance(item, (requests.Timeout, TimeoutError)):
            timeout = True
        elif isinstance(item, (requests.ConnectionError, OSError)):
            connection = True
        todo.extend(
            [item.__cause__, item.__context__, getattr(item, "reason", None), *item.args]
        )
    if timeout:
        return "timeout"
    if connection:
        return "unreachable"
    return "error"


def _response(responses: list[Any], method: str) -> dict[str, Any] | None:
    """The result of one method in a multipleRequest answer, None on error."""
    for response in responses:
        if not isinstance(response, dict) or response.get("method") != method:
            continue
        if response.get("error_code", 0) != 0 or not isinstance(response.get("result"), dict):
            _LOGGER.debug("%s answered with an error: %s", method, response)
            return None
        return response["result"]
    return None


def _section(result: dict[str, Any] | None, module: str, section: str) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    info = result.get(module, result).get(section)
    return info if isinstance(info, dict) else None


# The alarm config is read and written with getAlertConfig / setAlertConfig,
# the current camera API and the one the Tapo app uses for these cameras.
ALARM_READ = {
    "method": "getAlertConfig",
    "params": {"msg_alarm": {"name": [ALARM_SECTION], "table": ["usr_def_audio"]}},
}
PUSH_READ = {
    "method": "getMsgPushConfig",
    "params": {"msg_push": {"name": [PUSH_SECTION]}},
}


class TapoAlarmApi:
    """Alarm related calls on top of a connected pytapo controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        controller: Tapo,
        host: str,
        session_renew_minutes: float = 0,
    ) -> None:
        self.hass = hass
        self.controller = controller
        self.host = host
        self.info = basic_info(controller)
        self._lock = asyncio.Lock()
        # The controller was just connected, so a fresh session exists.
        self._session_started = time.monotonic()
        self.session_renew_minutes = session_renew_minutes

    async def _run(self, func: Callable[..., Any], *args: Any) -> Any:
        """Run one blocking pytapo call, one at a time per camera."""
        async with self._lock:
            await self._renew_session_if_due()
            try:
                return await self.hass.async_add_executor_job(func, *args)
            except Exception as err:  # noqa: BLE001 - pytapo raises plain exceptions
                raise _wrap(err) from err

    async def _renew_session_if_due(self) -> None:
        """Log in again before the camera ends the session.

        Cameras end the session about 10 minutes after login. pytapo then
        logs in again and repeats the request by itself; renewing first
        avoids that failed request. Closing drops the old session (cameras
        have no logout call; the camera expires it) and pytapo logs in again
        on the next request.
        """
        if not self.session_renew_minutes:
            return
        now = time.monotonic()
        if now - self._session_started < self.session_renew_minutes * 60:
            return
        _LOGGER.debug("Renewing the session with %s", self.host)
        try:
            await self.hass.async_add_executor_job(self.controller.close)
        except Exception as err:  # noqa: BLE001 - the next request logs in anyway
            _LOGGER.debug("Closing the session with %s failed: %s", self.host, err)
        self._session_started = now

    async def get_state(self) -> dict[str, Any]:
        """Read the alarm and notification config in one multipleRequest."""
        responses = await self._run(
            self.controller.executeFunction,
            "multipleRequest",
            {"requests": [ALARM_READ, PUSH_READ]},
        )
        if not isinstance(responses, list):
            raise CameraError(f"Unexpected response from {self.host}: {responses}")
        alarm = _section(_response(responses, "getAlertConfig"), "msg_alarm", ALARM_SECTION)
        if alarm is None or "enabled" not in alarm:
            raise CameraError(
                f"{self.host} does not answer getAlertConfig, the only alarm call"
                f" this integration uses: {responses}"
            )
        push = _section(_response(responses, "getMsgPushConfig"), "msg_push", PUSH_SECTION)
        return {"alarm": alarm, "push": push}

    async def set_alarm(
        self, current: dict[str, Any], *, enabled: bool | None = None,
        sound: bool | None = None, light: bool | None = None,
    ) -> dict[str, Any]:
        """Change the alarm with setAlertConfig.

        Only the changed field is sent, like the Tapo app does with this
        call: {"enabled": ...} to turn the alarm on/off, {"alarm_mode": ...}
        to change sound/light. The rest of the config (volume, duration,
        light type, ...) is not written again. A field that already has the
        wanted value is left out, and nothing is sent when no field changes.
        """
        new: dict[str, Any] = {}
        if enabled is not None and (current.get("enabled") == "on") != enabled:
            new["enabled"] = "on" if enabled else "off"
        if sound is not None or light is not None:
            old_modes = alarm_modes(current)
            modes = list(old_modes)
            # Some firmwares call the sound mode "siren".
            sound_mode = "siren" if "siren" in modes else MODE_SOUND
            for mode, value in ((sound_mode, sound), (MODE_LIGHT, light)):
                if value is True and mode not in modes:
                    modes.append(mode)
                elif value is False and mode in modes:
                    modes.remove(mode)
            if set(modes) != set(old_modes):
                if not modes:
                    raise ValueError("At least one of sound or light must stay enabled")
                new["alarm_mode"] = modes
        if not new:
            _LOGGER.debug("%s: alarm already as asked, nothing written", self.host)
            return new
        await self._run(
            self.controller.executeFunction,
            "setAlertConfig",
            {"msg_alarm": {ALARM_SECTION: new}},
        )
        return new

    async def set_notifications(
        self, current: dict[str, Any] | None, enabled: bool
    ) -> dict[str, str]:
        """Turn app push notifications on/off, unless already as asked.

        pytapo's setNotificationsEnabled sends only notification_enabled.
        """
        value = "on" if enabled else "off"
        if current is not None and current.get("notification_enabled") == value:
            _LOGGER.debug("%s: notifications already as asked, nothing written", self.host)
            return {}
        await self._run(self.controller.setNotificationsEnabled, enabled)
        return {"notification_enabled": value}

    async def reboot(self) -> None:
        """Reboot the camera with pytapo's reboot (rebootDevice)."""
        await self._run(self.controller.reboot)

    async def close(self) -> None:
        """Close the session."""
        try:
            await self.hass.async_add_executor_job(self.controller.close)
        except Exception as err:  # noqa: BLE001 - nothing to do on unload
            _LOGGER.debug("Closing the session with %s failed: %s", self.host, err)
