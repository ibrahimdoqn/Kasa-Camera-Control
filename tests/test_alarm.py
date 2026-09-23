"""Tests for the Tapo camera alarm integration with a fake camera."""

from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from kasa.exceptions import DeviceError, SmartErrorCode

from custom_components.tapo_kasa_alarm.const import DOMAIN

DATA = {"host": "192.168.1.50", "username": "me@example.com", "password": "pw"}


class FakeProtocol:
    def __init__(self):
        self.alarm = {
            "enabled": "off",
            "alarm_type": "3",
            "light_type": "0",
            "alarm_mode": ["sound", "light"],
        }
        self.push = {"notification_enabled": "on", "rich_notification_enabled": "off"}
        self.siren = "off"
        self.requests = []

    async def query(self, request):
        self.requests.append(request)
        method = next(iter(request))
        if method == "set":
            self.alarm = request[method]["msg_alarm"]["chn1_msg_alarm_info"]
            return {}
        if method == "do":
            # C5x0 firmware rejects the manual alarm "do" call.
            raise DeviceError("UNSUPPORTED_METHOD")
        resp = {}
        for method, params in request.items():
            if method == "getLastAlarmInfo":
                resp[method] = {"msg_alarm": {"chn1_msg_alarm_info": dict(self.alarm)}}
            elif method == "getMsgPushConfig":
                resp[method] = {"msg_push": {"chn1_msg_push_info": dict(self.push)}}
            elif method == "setMsgPushConfig":
                self.push.update(params["msg_push"]["chn1_msg_push_info"])
                resp[method] = {}
            elif method == "setSirenStatus":
                # Newer C520WS firmware rejects this too.
                raise DeviceError("UNSUPPORTED_METHOD")
            elif method == "testUsrDefAudio":
                audio = params["msg_alarm"]["test_usr_def_audio"]
                self.siren = "off" if audio.get("action") == "stop" else audio["id"]
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
    return dev


async def test_setup_and_toggle(hass: HomeAssistant) -> None:
    dev = fake_device()
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
    assert hass.states.get("switch.bahce_alarm_sound").state == "on"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.bahce_alarm"}, blocking=True
    )
    assert dev.protocol.alarm["enabled"] == "on"
    assert dev.protocol.alarm["alarm_mode"] == ["sound", "light"]
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

    await hass.services.async_call(
        "siren", "turn_on", {"entity_id": "siren.bahce_siren"}, blocking=True
    )
    assert dev.protocol.siren == "3"
    assert hass.states.get("siren.bahce_siren").state == "on"
    # The working variant is remembered, "do" is not retried.
    before = len(dev.protocol.requests)
    await hass.services.async_call(
        "siren", "turn_off", {"entity_id": "siren.bahce_siren"}, blocking=True
    )
    assert dev.protocol.siren == "off"
    assert len(dev.protocol.requests) == before + 1

    assert hass.states.get("switch.bahce_notifications").state == "on"
    assert hass.states.get("switch.bahce_rich_notifications").state == "off"
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.bahce_notifications"}, blocking=True
    )
    assert dev.protocol.push["notification_enabled"] == "off"
    assert hass.states.get("switch.bahce_notifications").state == "off"

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
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.bahce_alarm_sound"}, blocking=True
    )
    assert dev.protocol.alarm["enabled"] == "on"
    assert dev.protocol.alarm["alarm_mode"] == ["light"]
    assert dev.protocol.alarm["sound_alarm_enabled"] == "off"
    assert dev.protocol.alarm["alarm_volume"] == "7"

    # Later polls go straight to getAlertConfig.
    dev.protocol.requests.clear()
    await entry.runtime_data.async_refresh()
    assert [next(iter(r)) for r in dev.protocol.requests] == ["getAlertConfig"]
