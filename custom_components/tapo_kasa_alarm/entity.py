"""Base entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TapoAlarmCoordinator
from .port_check import PortCheckCoordinator


def _describe(entity, coordinator: TapoAlarmCoordinator, key: str) -> None:
    """Unique id, translation key and the camera's device info."""
    info = coordinator.api.info
    mac = info.get("mac")
    uid = coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
    entity._attr_unique_id = f"{uid}_{key}"
    entity._attr_translation_key = key
    entity._attr_device_info = DeviceInfo(
        identifiers={(DOMAIN, str(uid))},
        connections={(CONNECTION_NETWORK_MAC, format_mac(mac))} if mac else set(),
        manufacturer="TP-Link",
        model=info.get("device_model"),
        name=info.get("device_alias") or coordinator.config_entry.title,
        sw_version=info.get("sw_version"),
        hw_version=info.get("hw_version"),
    )


class TapoAlarmEntity(CoordinatorEntity[TapoAlarmCoordinator]):
    """An entity fed by the camera polls."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TapoAlarmCoordinator, key: str) -> None:
        super().__init__(coordinator)
        _describe(self, coordinator, key)


class PortCheckEntity(CoordinatorEntity[PortCheckCoordinator]):
    """A connection diagnostic entity fed by the port check."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TapoAlarmCoordinator, key: str) -> None:
        assert coordinator.port_check is not None
        super().__init__(coordinator.port_check)
        _describe(self, coordinator, key)
