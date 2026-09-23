"""Tests for the Tapo camera alarm integration with a fake camera."""

from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.tapo_kasa_alarm.const import DOMAIN

DATA = {"host": "192.168.1.50", "username": "me@example.com", "password": "pw"}


class FakeProtocol:
    def __init__(self):
        self.alarm = {
            "enabled": "off",
            "alarm_type": "0",
            "light_type": "0",
            "alarm_mode": ["sound", "light"],
        }
        self.requests = []

    async def query(self, request):
        self.requests.append(request)
        method = next(iter(request))
        if method == "getLastAlarmInfo":
            return {method: {"msg_alarm": {"chn1_msg_alarm_info": dict(self.alarm)}}}
        if method == "set":
            self.alarm = request[method]["msg_alarm"]["chn1_msg_alarm_info"]
            return {}
        if method == "do":
            return {"do": {}}
        raise AssertionError(request)

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
        "alarm_type": "0",
        "light_type": "0",
        "enabled": "on",
        "alarm_mode": ["sound"],
    }

    await hass.services.async_call(
        "siren", "turn_on", {"entity_id": "siren.bahce_siren"}, blocking=True
    )
    assert dev.protocol.requests[-1] == {
        "do": {"msg_alarm": {"manual_msg_alarm": {"action": "start"}}}
    }

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
