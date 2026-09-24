"""Thin wrapper around pytapo for the Tapo camera alarm endpoints.

pytapo is the library used by the Tapo Control integration, and the camera
is connected the same way that integration does it with a cloud password:
"admin" with the TP-Link cloud password. pytapo is
blocking, so every call runs in the executor. pytapo keeps one session per
camera, sends the requests one at a time and logs in again when the camera
ends the session.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from pytapo import Tapo
import requests

from homeassistant.core import HomeAssistant

from .const import ALARM_SECTION, MODE_LIGHT, MODE_SOUND, PUSH_SECTION

_LOGGER = logging.getLogger(__name__)
_PYTAPO_LOGGER = logging.getLogger(f"{__name__}.pytapo")

# pytapo raises plain exceptions; these messages mean the login was rejected.
_AUTH_MESSAGE = "Invalid authentication"


class CameraError(Exception):
    """The camera could not be reached or rejected a request."""


class AuthenticationError(CameraError):
    """The camera rejected the login."""


def _wrap(err: Exception) -> CameraError:
    if isinstance(err, CameraError):
        return err
    if _AUTH_MESSAGE in str(err):
        return AuthenticationError(str(err))
    return CameraError(str(err) or type(err).__name__)


def connect(
    hass: HomeAssistant | None,
    host: str,
    cloud_password: str,
    is_klap: bool | None = None,
) -> Tapo:
    """Log in to the camera the way Tapo Control does (blocking).

    Same pytapo settings as Tapo Control's registerController, with the
    login Tapo Control uses when a cloud password is given: "admin" and
    the TP-Link cloud password.
    """
    try:
        return Tapo(
            host,
            "admin",
            cloud_password,
            cloud_password,
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
    """Sound/light modes of the automatic alarm.

    Only alarm_mode, like the Tapo app. getAlertConfig also reports
    sound_alarm_enabled / light_alarm_enabled, but those belong to the
    manual alarm (the app reads them only for it) and the camera does not
    change them when alarm_mode changes.
    """
    return list(alarm.get("alarm_mode") or [])


# Reasons that mean the camera could not be reached (see connection_reason).
UNREACHABLE_REASONS = frozenset({"restarting", "unreachable", "timeout"})


def connection_reason(err: BaseException) -> str:
    """Why a request to the camera failed, from the exception chain.

    restarting: the camera is on the network but refuses the connection
                (ConnectionRefusedError, errno 111): its services restart
    timeout: the camera did not answer in time
    unreachable: the camera is not on the network (e.g. errno 113, Wi-Fi drop)
    auth: the login was rejected
    error: the camera answered with an error
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
            return "restarting"
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

    def __init__(self, hass: HomeAssistant, controller: Tapo, host: str) -> None:
        self.hass = hass
        self.controller = controller
        self.host = host
        self.info = basic_info(controller)

    async def _run(self, func: Callable[..., Any], *args: Any) -> Any:
        """Run one blocking pytapo call in the executor."""
        try:
            return await self.hass.async_add_executor_job(func, *args)
        except Exception as err:  # noqa: BLE001 - pytapo raises plain exceptions
            raise _wrap(err) from err

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
            for mode, value in ((MODE_SOUND, sound), (MODE_LIGHT, light)):
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
