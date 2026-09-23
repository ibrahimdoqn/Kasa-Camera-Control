"""Tests for the Tapo camera alarm integration with a fake camera."""

from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from kasa.exceptions import DeviceError, SmartErrorCode

from custom_components.tapo_kasa_alarm.const import DOMAIN

DATA = {"host": "192.168.1.50", "username": "me@example.com", "password": "pw"}
CONNECTION = {"device_family": "SMART.IPCAMERA", "encryption_type": "AES", "https": True}


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

    assert hass.states.get("switch.bahce_notifications").state == "on"
    assert hass.states.get("switch.bahce_rich_notifications") is None
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


async def test_retry_after_session_expired() -> None:
    """A 401 from an expired camera session is retried once, errors are not."""
    from kasa import KasaException

    from custom_components.tapo_kasa_alarm.api import TapoAlarmApi

    dev = fake_device()
    proto = dev.protocol
    real_query = proto.query
    calls = {"n": 0}

    async def expired_once(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise KasaException(
                "192.168.31.8 responded with an unexpected status code 401 to passthrough"
            )
        return await real_query(request)

    proto.query = expired_once
    api = TapoAlarmApi(dev)
    state = await api.get_state()
    assert state["alarm"]["enabled"] == "off"
    assert calls["n"] == 2

    async def device_error(request):
        calls["n"] += 1
        raise DeviceError("INVALID_ARGUMENTS")

    proto.query = device_error
    calls["n"] = 0
    try:
        await api.set_notifications(True)
    except DeviceError:
        pass
    assert calls["n"] == 1


async def _setup(hass: HomeAssistant, dev, data=None):
    entry = MockConfigEntry(
        domain=DOMAIN, data=data or DATA, unique_id="aa:bb:cc:dd:ee:ff"
    )
    entry.add_to_hass(hass)
    connect = AsyncMock(return_value=dev)
    with patch("custom_components.tapo_kasa_alarm.connect_device", connect):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, connect


async def test_connects_like_tplink(hass: HomeAssistant) -> None:
    """HA managed HTTP session, stored connection parameters are saved and reused."""
    entry, connect = await _setup(hass, fake_device())
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data["connection_parameters"] == CONNECTION
    kwargs = connect.call_args.kwargs
    assert kwargs["http_client"] is not None
    assert kwargs["connection_parameters"] is None

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


async def test_wrong_device_at_ip(hass: HomeAssistant) -> None:
    """Another device at the stored IP: do not use it, follow ours by MAC."""
    other = fake_device()
    other.mac = "11-22-33-44-55-66"
    with patch(
        "custom_components.tapo_kasa_alarm.discovery.discover_macs",
        AsyncMock(return_value={"AA:BB:CC:DD:EE:FF": "192.168.1.77"}),
    ):
        entry, _ = await _setup(hass, other)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    other.disconnect.assert_awaited()
    assert entry.data["host"] == "192.168.1.77"


async def test_unreachable_camera_found_at_new_ip(hass: HomeAssistant) -> None:
    from kasa import KasaException

    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id="aa:bb:cc:dd:ee:ff")
    entry.add_to_hass(hass)
    with patch(
        "custom_components.tapo_kasa_alarm.connect_device",
        AsyncMock(side_effect=KasaException("timeout")),
    ), patch(
        "custom_components.tapo_kasa_alarm.discovery.discover_macs",
        AsyncMock(return_value={"AA:BB:CC:DD:EE:FF": "192.168.1.77"}),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.data["host"] == "192.168.1.77"


async def test_rediscover_after_failed_polls(hass: HomeAssistant) -> None:
    """Polls that get no answer look for the camera at a new IP (not every time)."""
    dev = fake_device()
    entry, _ = await _setup(hass, dev)
    coordinator = entry.runtime_data

    async def no_answer(request):
        from kasa.exceptions import TimeoutError as KasaTimeoutError

        raise KasaTimeoutError("Unable to query the device")

    dev.protocol.query = no_answer
    discover = AsyncMock(return_value={})
    with patch("custom_components.tapo_kasa_alarm.discovery.discover_macs", discover):
        for _ in range(5):
            await coordinator.async_refresh()
    # Once after the 3rd failure, then not again within 15 minutes.
    assert discover.await_count == 1

    async def device_error(request):
        raise DeviceError("INVALID_ARGUMENTS")

    dev.protocol.query = device_error
    discover.reset_mock()
    with patch("custom_components.tapo_kasa_alarm.discovery.discover_macs", discover):
        coordinator._last_rediscovery = None
        for _ in range(5):
            await coordinator.async_refresh()
    # A camera that answers with an error code is reachable, no discovery.
    assert discover.await_count == 0
