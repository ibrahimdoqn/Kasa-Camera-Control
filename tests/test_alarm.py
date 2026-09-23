"""Tests for the Tapo camera alarm integration with a fake camera."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from kasa.exceptions import DeviceError, SmartErrorCode

from custom_components.tapo_kasa_alarm.const import DOMAIN

DATA = {"host": "192.168.1.50", "username": "me@example.com", "password": "pw"}
CONNECTION = {"device_family": "SMART.IPCAMERA", "encryption_type": "AES", "https": True}


DISCOVER = "custom_components.tapo_kasa_alarm.discovery.discover_macs"


@pytest.fixture(autouse=True)
def no_real_discovery():
    """Never send UDP broadcasts from tests."""
    with patch(DISCOVER, AsyncMock(return_value={})) as discover:
        yield discover


async def refresh_after_command(hass: HomeAssistant) -> None:
    """Let the debounced refresh after a command run (0.35 s, like TP-Link)."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()


class FakeProtocol:
    def __init__(self):
        self.alarm = {
            "enabled": "off",
            "alarm_type": "3",
            "light_type": "0",
            "alarm_mode": ["sound", "light"],
        }
        self.push = {"notification_enabled": "on", "rich_notification_enabled": "off"}
        self.requests = []

    async def query(self, request):
        self.requests.append(request)
        method = next(iter(request))
        if method == "set":
            self.alarm = request[method]["msg_alarm"]["chn1_msg_alarm_info"]
            return {}
        resp = {}
        for method, params in request.items():
            if method == "getLastAlarmInfo":
                resp[method] = {"msg_alarm": {"chn1_msg_alarm_info": dict(self.alarm)}}
            elif method == "getMsgPushConfig":
                resp[method] = {"msg_push": {"chn1_msg_push_info": dict(self.push)}}
            elif method == "setMsgPushConfig":
                self.push.update(params["msg_push"]["chn1_msg_push_info"])
                resp[method] = {}
            elif method == "rebootDevice":
                self.rebooted = params
                resp[method] = {}
            else:
                raise AssertionError(request)
        return resp

    async def close(self):
        pass


def fake_device():
    dev = MagicMock()
    dev.protocol = FakeProtocol()
    dev.mac = "AA-BB-CC-DD-EE-FF"
    dev.device_id = "abc"
    dev.alias = "Bahce"
    dev.model = "C520WS"
    dev.hw_info = {"sw_ver": "1.0", "hw_ver": "1.0"}
    dev.disconnect = AsyncMock()
    dev.update = AsyncMock()
    dev.host = "192.168.1.50"
    dev.config.connection_type.to_dict.return_value = CONNECTION
    return dev


async def test_setup_and_toggle(hass: HomeAssistant) -> None:
    dev = fake_device()
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id="aa:bb:cc:dd:ee:ff")
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old_siren = registry.async_get_or_create(
        "siren", DOMAIN, "aa:bb:cc:dd:ee:ff_siren", config_entry=entry
    )
    old_rich = registry.async_get_or_create(
        "switch", DOMAIN, "aa:bb:cc:dd:ee:ff_rich_notifications", config_entry=entry
    )
    with patch(
        "custom_components.tapo_kasa_alarm.connect_device",
        AsyncMock(return_value=dev),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert registry.async_get(old_siren.entity_id) is None
    assert registry.async_get(old_rich.entity_id) is None

    assert hass.states.get("switch.bahce_alarm").state == "off"
    assert hass.states.get("switch.bahce_alarm_sound").state == "on"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.bahce_alarm"}, blocking=True
    )
    assert dev.protocol.alarm["enabled"] == "on"
    assert dev.protocol.alarm["alarm_mode"] == ["sound", "light"]
    # Like TP-Link, the new state comes from the refresh after the command.
    await refresh_after_command(hass)
    assert hass.states.get("switch.bahce_alarm").state == "on"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.bahce_alarm_light"}, blocking=True
    )
    assert dev.protocol.alarm == {
        "alarm_type": "3",
        "light_type": "0",
        "enabled": "on",
        "alarm_mode": ["sound"],
    }
    await refresh_after_command(hass)

    assert hass.states.get("switch.bahce_notifications").state == "on"
    assert hass.states.get("switch.bahce_rich_notifications") is None
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.bahce_notifications"}, blocking=True
    )
    assert dev.protocol.push["notification_enabled"] == "off"
    await refresh_after_command(hass)
    assert hass.states.get("switch.bahce_notifications").state == "off"

    # Every 5 seconds, one request with only the alarm and notification config.
    dev.update.reset_mock()
    dev.protocol.requests.clear()
    await entry.runtime_data.async_refresh()
    dev.update.assert_not_awaited()
    assert dev.protocol.requests == [
        {
            "getLastAlarmInfo": {"msg_alarm": {"name": ["chn1_msg_alarm_info"]}},
            "getMsgPushConfig": {"msg_push": {"name": ["chn1_msg_push_info"]}},
        }
    ]
    assert entry.runtime_data.update_interval == timedelta(seconds=5)

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.bahce_reboot"}, blocking=True
    )
    assert dev.protocol.rebooted == {"system": {"reboot": "null"}}

    assert await hass.config_entries.async_unload(entry.entry_id)
    dev.disconnect.assert_awaited()


async def test_config_flow(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.tapo_kasa_alarm.config_flow.connect_device",
        AsyncMock(return_value=fake_device()),
    ), patch("custom_components.tapo_kasa_alarm.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], DATA
        )
    assert result["type"] == "create_entry"
    assert result["title"] == "Bahce"
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert result["result"].data["connection_parameters"] == CONNECTION


class AlertConfigProtocol(FakeProtocol):
    """Firmware that rejects getLastAlarmInfo and uses getAlertConfig."""

    def __init__(self):
        super().__init__()
        self.alarm.update(
            {"sound_alarm_enabled": "on", "light_alarm_enabled": "on", "alarm_volume": "7"}
        )

    async def query(self, request):
        if "getLastAlarmInfo" in request:
            self.requests.append(request)
            return {
                "getLastAlarmInfo": SmartErrorCode.INVALID_ARGUMENTS,
                "getMsgPushConfig": {"msg_push": {"chn1_msg_push_info": dict(self.push)}},
            }
        method = next(iter(request))
        if method == "getAlertConfig":
            self.requests.append(request)
            return {
                method: {"msg_alarm": {"chn1_msg_alarm_info": dict(self.alarm)}},
                "getMsgPushConfig": {"msg_push": {"chn1_msg_push_info": dict(self.push)}},
            }
        if method == "setAlertConfig":
            self.requests.append(request)
            self.alarm = request[method]["msg_alarm"]["chn1_msg_alarm_info"]
            return {method: {}}
        if method == "set":
            raise AssertionError("raw set must not be used with getAlertConfig")
        return await super().query(request)


async def test_alert_config_firmware(hass: HomeAssistant) -> None:
    dev = fake_device()
    dev.protocol = AlertConfigProtocol()
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id="aa:bb:cc:dd:ee:ff")
    entry.add_to_hass(hass)
    with patch(
        "custom_components.tapo_kasa_alarm.connect_device",
        AsyncMock(return_value=dev),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("switch.bahce_alarm").state == "off"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.bahce_alarm"}, blocking=True
    )
    await refresh_after_command(hass)
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.bahce_alarm_sound"}, blocking=True
    )
    await refresh_after_command(hass)
    assert dev.protocol.alarm["enabled"] == "on"
    assert dev.protocol.alarm["alarm_mode"] == ["light"]
    assert dev.protocol.alarm["sound_alarm_enabled"] == "off"
    assert dev.protocol.alarm["alarm_volume"] == "7"

    # Later polls go straight to getAlertConfig.
    dev.protocol.requests.clear()
    await entry.runtime_data.async_refresh()
    assert [next(iter(r)) for r in dev.protocol.requests] == ["getAlertConfig"]


async def test_session_expired_is_not_retried() -> None:
    """Like TP-Link: a 401 fails that request, python-kasa logs in again next time."""
    from kasa import KasaException

    from custom_components.tapo_kasa_alarm.api import TapoAlarmApi

    dev = fake_device()
    calls = {"n": 0}

    async def expired(request):
        calls["n"] += 1
        raise KasaException("responded with an unexpected status code 401 to passthrough")

    dev.protocol.query = expired
    with pytest.raises(KasaException):
        await TapoAlarmApi(dev).get_state()
    assert calls["n"] == 1


async def _setup(hass: HomeAssistant, dev, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN, data=DATA, unique_id="aa:bb:cc:dd:ee:ff", options=options or {}
    )
    entry.add_to_hass(hass)
    connect = AsyncMock(return_value=dev)
    with patch("custom_components.tapo_kasa_alarm.connect_device", connect):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, connect


async def test_connects_like_tplink(hass: HomeAssistant) -> None:
    """HA managed HTTP session, connection parameters are saved."""
    entry, connect = await _setup(hass, fake_device())
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data["connection_parameters"] == CONNECTION
    kwargs = connect.call_args.kwargs
    assert kwargs["http_client"] is not None
    assert kwargs["connection_parameters"] is None


async def test_wrong_device_at_ip(hass: HomeAssistant) -> None:
    """Another device at the stored IP is never used."""
    other = fake_device()
    other.mac = "11-22-33-44-55-66"
    entry, _ = await _setup(hass, other)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    other.disconnect.assert_awaited()


async def test_no_mac_does_not_block_setup(hass: HomeAssistant) -> None:
    """A camera that reports no MAC is not mistaken for another device."""
    dev = fake_device()
    dev.mac = ""
    entry, _ = await _setup(hass, dev)
    assert entry.state is ConfigEntryState.LOADED


async def test_discovery_moves_camera(hass: HomeAssistant, no_real_discovery) -> None:
    """Discovery at start / every 15 min follows the camera to a new IP."""
    from custom_components.tapo_kasa_alarm.discovery import async_discover_and_update

    entry, _ = await _setup(hass, fake_device())
    no_real_discovery.return_value = {"AA:BB:CC:DD:EE:FF": "192.168.1.77"}
    with patch(
        "custom_components.tapo_kasa_alarm.connect_device",
        AsyncMock(return_value=fake_device()),
    ):
        await async_discover_and_update(hass)
        await hass.async_block_till_done()
    assert entry.data["host"] == "192.168.1.77"
    assert entry.state is ConfigEntryState.LOADED


async def test_discovery_can_be_turned_off(
    hass: HomeAssistant, no_real_discovery
) -> None:
    """With the option off (static IP) no broadcast is sent at all."""
    from custom_components.tapo_kasa_alarm.discovery import async_discover_and_update

    entry, _ = await _setup(hass, fake_device(), options={"discovery": False})
    no_real_discovery.reset_mock()
    no_real_discovery.return_value = {"AA:BB:CC:DD:EE:FF": "192.168.1.77"}
    await async_discover_and_update(hass)
    no_real_discovery.assert_not_awaited()
    assert entry.data["host"] == DATA["host"]


async def test_options_flow(hass: HomeAssistant) -> None:
    entry, _ = await _setup(hass, fake_device())
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 30, "session_renew": 5, "discovery": False}
    )
    await hass.async_block_till_done()
    assert entry.options == {"scan_interval": 30, "session_renew": 5, "discovery": False}
    assert entry.runtime_data.update_interval == timedelta(seconds=30)
    assert entry.runtime_data.api.session_renew_minutes == 5
    assert entry.state is ConfigEntryState.LOADED


async def test_session_renewed_before_camera_ends_it() -> None:
    """The session is dropped every N minutes so python-kasa logs in again."""
    from custom_components.tapo_kasa_alarm.api import TapoAlarmApi

    dev = fake_device()
    dev.protocol.close = AsyncMock()
    clock = {"now": 1000.0}
    with patch(
        "custom_components.tapo_kasa_alarm.api.time.monotonic",
        side_effect=lambda: clock["now"],
    ):
        api = TapoAlarmApi(dev, session_renew_minutes=8)
        clock["now"] += 7 * 60
        await api.get_state()
        dev.protocol.close.assert_not_awaited()

        clock["now"] += 60  # 8 minutes after login
        await api.get_state()
        dev.protocol.close.assert_awaited_once()

        clock["now"] += 60  # new session is only 1 minute old
        await api.get_state()
        dev.protocol.close.assert_awaited_once()

        api.session_renew_minutes = 0  # turned off
        clock["now"] += 60 * 60
        await api.get_state()
        dev.protocol.close.assert_awaited_once()


async def test_default_session_renew(hass: HomeAssistant) -> None:
    entry, _ = await _setup(hass, fake_device())
    assert entry.runtime_data.api.session_renew_minutes == 8
