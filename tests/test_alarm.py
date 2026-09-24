"""Tests for the Tapo camera alarm integration with a fake pytapo camera."""

from datetime import timedelta
import threading
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
import requests

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.tapo_kasa_alarm.const import DOMAIN

DATA = {"host": "192.168.1.50", "cloud_password": "cloudpw", "is_klap": False}
CONNECT = "custom_components.tapo_kasa_alarm.connect"


async def _press(hass: HomeAssistant, service: str, entity_id: str) -> None:
    await hass.services.async_call(
        "switch", service, {"entity_id": entity_id}, blocking=True
    )


class FakeTapo:
    """A pytapo Tapo controller talking to a fake camera."""

    def __init__(self, mac="AA-BB-CC-DD-EE-FF"):
        # Same fields as a real C520WS getAlertConfig answer.
        self.alarm = {
            "alarm_duration": "0",
            "alarm_mode": ["sound", "light"],
            "alarm_type": "3",
            "alarm_volume": "high",
            "enabled": "off",
            "light_alarm_enabled": "on",
            "light_type": "1",
            "sound_alarm_enabled": "on",
        }
        self.push = {"notification_enabled": "on", "rich_notification_enabled": "off"}
        self.basicInfo = {
            "device_info": {
                "basic_info": {
                    "device_model": "C520WS",
                    "device_alias": "Bahce",
                    "sw_version": "1.0",
                    "hw_version": "1.0",
                    "mac": mac,
                    "dev_id": "abc",
                }
            }
        }
        self.isKLAP = False
        self.calls = []  # (method, params)
        self.writes = []  # chn1_msg_alarm_info sent with setAlertConfig
        self.closed = 0
        self.fail = None  # exception raised by every call when set
        self.alert_error = False  # answer getAlertConfig with an error
        self.threads = set()

    def _answer(self, method, params):
        if method == "getAlertConfig":
            if self.alert_error:
                return {"method": method, "error_code": -40106}
            return {
                "method": method,
                "result": {"msg_alarm": {"chn1_msg_alarm_info": dict(self.alarm)}},
                "error_code": 0,
            }
        if method == "getMsgPushConfig":
            return {
                "method": method,
                "result": {"msg_push": {"chn1_msg_push_info": dict(self.push)}},
                "error_code": 0,
            }
        raise AssertionError(method)

    def executeFunction(self, method, params, retry=False):
        self.threads.add(threading.current_thread().name)
        self.calls.append((method, params))
        if self.fail:
            raise self.fail
        if method == "multipleRequest":
            return [self._answer(r["method"], r["params"]) for r in params["requests"]]
        if method == "setAlertConfig":
            sent = params["msg_alarm"]["chn1_msg_alarm_info"]
            self.writes.append(sent)
            # The camera merges the sent fields into its config. Like the
            # real cameras, sound/light_alarm_enabled (the manual alarm's
            # settings) do not follow alarm_mode.
            self.alarm.update(sent)
            return {}
        raise AssertionError(method)

    def setNotificationsEnabled(self, notificationsEnabled=None, richNotificationsEnabled=None):
        self.calls.append(("setMsgPushConfig", notificationsEnabled))
        if self.fail:
            raise self.fail
        self.push["notification_enabled"] = "on" if notificationsEnabled else "off"
        return {}

    def reboot(self):
        self.calls.append(("rebootDevice", None))
        return {}

    def close(self):
        self.closed += 1

    def methods(self):
        return [m for m, _ in self.calls]


async def _setup(hass: HomeAssistant, cam: FakeTapo, options=None, data=None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data=data or DATA,
        unique_id="aa:bb:cc:dd:ee:ff",
        options=options or {},
    )
    entry.add_to_hass(hass)
    with patch(CONNECT, return_value=cam) as connect:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, connect


async def test_setup_and_toggle(hass: HomeAssistant) -> None:
    cam = FakeTapo()
    entry = MockConfigEntry(
        domain=DOMAIN, version=2, data=DATA, unique_id="aa:bb:cc:dd:ee:ff"
    )
    entry.add_to_hass(hass)
    with patch(CONNECT, return_value=cam):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert hass.states.get("switch.bahce_alarm").state == "off"
    assert hass.states.get("switch.bahce_alarm_sound").state == "on"

    cam.calls.clear()
    await _press(hass, "turn_on", "switch.bahce_alarm")
    # Like the Tapo app, only the changed field is sent.
    assert cam.writes[-1] == {"enabled": "on"}
    assert cam.alarm["alarm_mode"] == ["sound", "light"]
    # The camera is read right before the write. Like the Tapo app, the
    # written state is shown at once and the camera is not read again
    # right after the write.
    assert hass.states.get("switch.bahce_alarm").state == "on"
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert cam.methods() == ["multipleRequest", "setAlertConfig"]

    # Already on: the camera is read, nothing is written.
    cam.calls.clear()
    await _press(hass, "turn_on", "switch.bahce_alarm")
    await _press(hass, "turn_on", "switch.bahce_alarm_sound")
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.bahce_notifications"}, blocking=True
    )
    assert set(cam.methods()) == {"multipleRequest"}
    assert hass.states.get("switch.bahce_alarm").state == "on"

    # Changed in the Tapo app since the last poll: the fresh read sees it
    # and the write is still sent.
    cam.alarm["enabled"] = "off"
    await _press(hass, "turn_on", "switch.bahce_alarm")
    assert cam.writes[-1] == {"enabled": "on"}

    await _press(hass, "turn_off", "switch.bahce_alarm_light")
    assert cam.writes[-1] == {"alarm_mode": ["sound"]}
    assert cam.alarm["alarm_volume"] == "high"
    assert cam.alarm["light_type"] == "1"
    assert hass.states.get("switch.bahce_alarm_light").state == "off"
    assert hass.states.get("switch.bahce_alarm_sound").state == "on"

    assert hass.states.get("switch.bahce_notifications").state == "on"
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.bahce_notifications"}, blocking=True
    )
    assert cam.push["notification_enabled"] == "off"
    assert hass.states.get("switch.bahce_notifications").state == "off"

    # Each poll is one request with only the alarm and notification config.
    cam.calls.clear()
    await entry.runtime_data.async_refresh()
    assert cam.calls == [
        (
            "multipleRequest",
            {
                "requests": [
                    {
                        "method": "getAlertConfig",
                        "params": {
                            "msg_alarm": {
                                "name": ["chn1_msg_alarm_info"],
                                "table": ["usr_def_audio"],
                            }
                        },
                    },
                    {
                        "method": "getMsgPushConfig",
                        "params": {"msg_push": {"name": ["chn1_msg_push_info"]}},
                    },
                ]
            },
        )
    ]
    assert entry.runtime_data.update_interval == timedelta(seconds=5)
    # pytapo is blocking: it never runs in the event loop thread.
    assert "MainThread" not in cam.threads

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.bahce_reboot"}, blocking=True
    )
    assert cam.methods()[-1] == "rebootDevice"

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert cam.closed >= 1


def test_login_like_tapo_control() -> None:
    """ "admin" + cloud password, with Tapo Control's controller settings."""
    from custom_components.tapo_kasa_alarm.api import connect

    with patch("custom_components.tapo_kasa_alarm.api.Tapo") as tapo:
        connect(None, "1.2.3.4", "cloudpw", False)
        args, kwargs = tapo.call_args
        assert args == ("1.2.3.4", "admin", "cloudpw", "cloudpw")
        assert kwargs["reuseSession"] is False
        assert kwargs["retryStok"] is False
        assert kwargs["isKLAP"] is False


def test_login_errors() -> None:
    from custom_components.tapo_kasa_alarm.api import (
        AuthenticationError,
        CameraError,
        connect,
    )

    with patch(
        "custom_components.tapo_kasa_alarm.api.Tapo",
        side_effect=Exception("Invalid authentication data"),
    ), pytest.raises(AuthenticationError):
        connect(None, "1.2.3.4", "bad")
    with patch(
        "custom_components.tapo_kasa_alarm.api.Tapo",
        side_effect=requests.ConnectionError("refused"),
    ), pytest.raises(CameraError) as err:
        connect(None, "1.2.3.4", "cloudpw")
    assert not isinstance(err.value, AuthenticationError)


async def test_config_flow(hass: HomeAssistant) -> None:
    user_input = {"host": "192.168.1.50", "cloud_password": "cloudpw"}
    with patch(
        "custom_components.tapo_kasa_alarm.config_flow.connect", return_value=FakeTapo()
    ) as connect, patch(
        "custom_components.tapo_kasa_alarm.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
    assert result["type"] == "create_entry"
    assert result["title"] == "Bahce"
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert result["result"].version == 2
    assert result["result"].data == {**user_input, "is_klap": False}
    assert connect.call_args.args[1:] == ("192.168.1.50", "cloudpw")


async def test_config_flow_errors(hass: HomeAssistant) -> None:
    from custom_components.tapo_kasa_alarm.api import AuthenticationError, CameraError

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    for error, expected in (
        (AuthenticationError("bad"), "invalid_auth"),
        (CameraError("refused"), "cannot_connect"),
    ):
        with patch(
            "custom_components.tapo_kasa_alarm.config_flow.connect", side_effect=error
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"host": "192.168.1.50", "cloud_password": "bad"}
            )
        assert result["errors"] == {"base": expected}


async def test_login_type_saved_on_first_connection(hass: HomeAssistant) -> None:
    """Like Tapo Control, the KLAP login type is found once and saved."""
    data = {"host": "192.168.1.50", "cloud_password": "cloudpw"}
    entry, connect = await _setup(hass, FakeTapo(), data=data)
    assert entry.state is ConfigEntryState.LOADED
    assert connect.call_args.args[1:] == ("192.168.1.50", "cloudpw", None)
    assert entry.data["is_klap"] is False


async def test_login_type_of_another_device_is_not_saved(hass: HomeAssistant) -> None:
    """Another device at the camera's IP never decides the saved login type."""
    data = {"host": "192.168.1.50", "cloud_password": "cloudpw"}
    other = FakeTapo(mac="11-22-33-44-55-66")
    other.isKLAP = True
    entry, _ = await _setup(hass, other, data=data)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert "is_klap" not in entry.data


async def test_camera_account_entry_asks_for_cloud_password(hass: HomeAssistant) -> None:
    """An entry set up with a camera account in 2.0.0 asks for the cloud password."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={"host": "192.168.1.50", "username": "cam", "password": "campw",
              "cloud_password": ""},
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)
    with patch(CONNECT) as connect:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    connect.assert_not_called()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    [flow] = hass.config_entries.flow.async_progress()
    assert flow["context"]["source"] == "reauth"

    with patch(
        "custom_components.tapo_kasa_alarm.config_flow.connect", return_value=FakeTapo()
    ), patch(CONNECT, return_value=FakeTapo()):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"cloud_password": "cloudpw"}
        )
        await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert entry.data == DATA
    assert entry.state is ConfigEntryState.LOADED


async def test_reconfigure(hass: HomeAssistant) -> None:
    entry, _ = await _setup(hass, FakeTapo())
    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "custom_components.tapo_kasa_alarm.config_flow.connect", return_value=FakeTapo()
    ), patch(CONNECT, return_value=FakeTapo()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.168.1.51", "cloud_password": "new"}
        )
        await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {"host": "192.168.1.51", "cloud_password": "new", "is_klap": False}

    # Another camera at the new IP is not saved.
    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "custom_components.tapo_kasa_alarm.config_flow.connect",
        return_value=FakeTapo(mac="11-22-33-44-55-66"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.168.1.52", "cloud_password": "new"}
        )
    assert result["reason"] == "wrong_camera"
    assert entry.data["host"] == "192.168.1.51"


async def test_only_the_alert_config_calls_are_used(hass: HomeAssistant) -> None:
    """Old alarm calls (getLastAlarmInfo, raw set, *AlarmConfig) are never sent."""
    cam = FakeTapo()
    await _setup(hass, cam)
    await _press(hass, "turn_on", "switch.bahce_alarm")
    await _press(hass, "turn_off", "switch.bahce_alarm_sound")
    methods = set(cam.methods())
    for method, params in cam.calls:
        if method == "multipleRequest":
            methods.update(r["method"] for r in params["requests"])
    assert methods <= {
        "multipleRequest",
        "getAlertConfig",
        "setAlertConfig",
        "getMsgPushConfig",
    }
    assert cam.alarm["enabled"] == "on"
    assert cam.alarm["alarm_mode"] == ["light"]
    assert hass.states.get("switch.bahce_alarm_sound").state == "off"


async def test_camera_without_alert_config_fails_clearly(hass: HomeAssistant) -> None:
    cam = FakeTapo()
    cam.alert_error = True
    entry, _ = await _setup(hass, cam)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert "getAlertConfig" in (entry.reason or "")


async def test_sound_off_stays_off(hass: HomeAssistant) -> None:
    """Only alarm_mode decides sound/light; the manual alarm's flags do not."""
    cam = FakeTapo()
    entry, _ = await _setup(hass, cam)
    await _press(hass, "turn_off", "switch.bahce_alarm_sound")
    assert cam.writes[-1] == {"alarm_mode": ["light"]}
    # The camera keeps sound_alarm_enabled "on" (it is the manual alarm's).
    assert cam.alarm["sound_alarm_enabled"] == "on"
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("switch.bahce_alarm_sound").state == "off"
    assert hass.states.get("switch.bahce_alarm_light").state == "on"


async def test_rejected_login_on_setup_is_tried_again(hass: HomeAssistant) -> None:
    """Like Tapo Control: the password is asked for on the 4th rejection in a row."""
    from custom_components.tapo_kasa_alarm.api import AuthenticationError

    entry = MockConfigEntry(
        domain=DOMAIN, version=2, data=DATA, unique_id="aa:bb:cc:dd:ee:ff"
    )
    entry.add_to_hass(hass)
    with patch(CONNECT, side_effect=AuthenticationError("Invalid authentication data")):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        for _ in range(3):
            assert entry.state is ConfigEntryState.SETUP_RETRY
            assert not hass.config_entries.flow.async_progress()
            await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]

    # The password is entered again and accepted, but the first poll fails
    # (the camera is still starting). The count starts over at the accepted
    # login, so one more rejection right after does not ask for it at once.
    for flow in flows:
        hass.config_entries.flow.async_abort(flow["flow_id"])
    starting = FakeTapo()
    starting.alert_error = True
    with patch(CONNECT, return_value=starting):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    with patch(CONNECT, side_effect=AuthenticationError("Invalid authentication data")):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


async def test_rejected_login_on_poll_is_tried_again(hass: HomeAssistant) -> None:
    cam = FakeTapo()
    entry, _ = await _setup(hass, cam)
    coordinator = entry.runtime_data

    # A rejected command does not ask for the password.
    cam.fail = Exception("Invalid authentication data")
    with pytest.raises(HomeAssistantError):
        await _press(hass, "turn_on", "switch.bahce_alarm")
    assert not hass.config_entries.flow.async_progress()

    for _ in range(3):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert not hass.config_entries.flow.async_progress()
    # A successful poll in between starts the count again.
    cam.fail = None
    await coordinator.async_refresh()
    cam.fail = Exception("Invalid authentication data")
    for _ in range(3):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert not hass.config_entries.flow.async_progress()
    assert hass.states.get("switch.bahce_alarm").state == "unavailable"

    await coordinator.async_refresh()  # 4th in a row
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_wrong_device_at_ip(hass: HomeAssistant) -> None:
    """Another device at the stored IP is never used."""
    other = FakeTapo(mac="11-22-33-44-55-66")
    entry, _ = await _setup(hass, other)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert other.closed == 1


async def test_no_mac_does_not_block_setup(hass: HomeAssistant) -> None:
    """A camera that reports no MAC is not mistaken for another device."""
    entry, _ = await _setup(hass, FakeTapo(mac=""))
    assert entry.state is ConfigEntryState.LOADED


async def test_options_flow(hass: HomeAssistant) -> None:
    entry, _ = await _setup(hass, FakeTapo())
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 30}
    )
    await hass.async_block_till_done()
    assert entry.options == {"scan_interval": 30}
    assert entry.runtime_data.update_interval == timedelta(seconds=30)
    assert entry.state is ConfigEntryState.LOADED


async def test_unreachable_camera(hass: HomeAssistant) -> None:
    """While the camera does not answer the switches are unavailable."""
    cam = FakeTapo()
    entry, _ = await _setup(hass, cam)
    cam.fail = requests.ConnectionError("Connection refused")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("switch.bahce_alarm").state == "unavailable"
    assert not hass.config_entries.flow.async_progress()

    cam.fail = None
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("switch.bahce_alarm").state == "off"


def _refused() -> requests.ConnectionError:
    """What pytapo raises while the camera restarts its services."""
    try:
        try:
            raise ConnectionRefusedError(111, "Connection refused")
        except ConnectionRefusedError as refused:
            raise OSError("Failed to establish a new connection") from refused
    except OSError as err:
        return requests.ConnectionError(err)


async def test_connection_diagnostics(hass: HomeAssistant) -> None:
    cam = FakeTapo()
    entry, _ = await _setup(hass, cam)
    coordinator = entry.runtime_data

    connection = hass.states.get("binary_sensor.bahce_connection")
    assert connection.state == "on"
    assert connection.attributes["last_disconnect"] is None
    since = hass.states.get("sensor.bahce_connected_since")
    assert since.state not in ("unknown", "unavailable")

    # A failed poll: disconnected, the first cause is kept for the outage.
    cam.fail = _refused()
    await coordinator.async_refresh()
    cam.fail = requests.ReadTimeout("timeout")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    connection = hass.states.get("binary_sensor.bahce_connection")
    assert connection.state == "off"
    assert connection.attributes["last_disconnect_reason"] == "restarting"
    assert connection.attributes["last_disconnect_source"] == "poll"
    assert connection.attributes["down_since"] is not None
    assert hass.states.get("sensor.bahce_connected_since").state == "unknown"
    assert hass.states.get("switch.bahce_alarm").state == "unavailable"

    # Back: connected again, from now.
    cam.fail = None
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    connection = hass.states.get("binary_sensor.bahce_connection")
    assert connection.state == "on"
    assert connection.attributes["down_since"] is None
    assert connection.attributes["last_outage_seconds"] is not None
    assert hass.states.get("sensor.bahce_connected_since").state != "unknown"


async def test_command_that_cannot_reach_the_camera(hass: HomeAssistant) -> None:
    cam = FakeTapo()
    entry, _ = await _setup(hass, cam)

    # The camera answers with an error: still connected.
    cam.fail = Exception("Error: -40106")
    with pytest.raises(HomeAssistantError):
        await _press(hass, "turn_on", "switch.bahce_alarm")
    assert hass.states.get("binary_sensor.bahce_connection").state == "on"

    # The camera cannot be reached: disconnected at once, before any poll.
    cam.fail = requests.ConnectTimeout("timed out")
    with pytest.raises(HomeAssistantError):
        await _press(hass, "turn_on", "switch.bahce_alarm")
    connection = hass.states.get("binary_sensor.bahce_connection")
    assert connection.state == "off"
    assert connection.attributes["last_disconnect_reason"] == "timeout"
    assert connection.attributes["last_disconnect_source"] == "command"

    cam.fail = None
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.bahce_connection").state == "on"


async def test_reboot_disconnects(hass: HomeAssistant) -> None:
    cam = FakeTapo()
    entry, _ = await _setup(hass, cam)
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.bahce_reboot"}, blocking=True
    )
    connection = hass.states.get("binary_sensor.bahce_connection")
    assert connection.state == "off"
    assert connection.attributes["last_disconnect_reason"] == "reboot"
    assert hass.states.get("sensor.bahce_connected_since").state == "unknown"

    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.bahce_connection").state == "on"


def test_connection_reasons() -> None:
    from custom_components.tapo_kasa_alarm.api import (
        AuthenticationError,
        CameraError,
        _wrap,
        connection_reason,
    )

    def wrapped(err: Exception) -> CameraError:
        try:
            raise _wrap(err) from err
        except CameraError as camera_error:
            return camera_error

    assert connection_reason(wrapped(_refused())) == "restarting"
    assert (
        connection_reason(wrapped(requests.ConnectionError(OSError(113, "no route"))))
        == "unreachable"
    )
    assert connection_reason(wrapped(requests.ReadTimeout("timeout"))) == "timeout"
    assert connection_reason(wrapped(requests.ConnectTimeout("timeout"))) == "timeout"
    assert connection_reason(AuthenticationError("bad")) == "auth"
    assert connection_reason(wrapped(Exception("Error: -40106"))) == "error"


async def test_disconnect_count_sensor_is_removed(hass: HomeAssistant) -> None:
    """The disconnect count sensor earlier versions created is removed."""
    entry = MockConfigEntry(
        domain=DOMAIN, version=2, data=DATA, unique_id="aa:bb:cc:dd:ee:ff"
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor", DOMAIN, "aa:bb:cc:dd:ee:ff_disconnects", config_entry=entry
    )
    with patch(CONNECT, return_value=FakeTapo()):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert registry.async_get(old.entity_id) is None
    assert hass.states.get("sensor.bahce_connected_since") is not None
