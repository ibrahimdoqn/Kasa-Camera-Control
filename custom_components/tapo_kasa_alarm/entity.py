"""Base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TapoAlarmCoordinator


class TapoAlarmEntity(CoordinatorEntity[TapoAlarmCoordinator]):
    """Common device info for all entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TapoAlarmCoordinator, key: str) -> None:
        super().__init__(coordinator)
        info = coordinator.api.info
        mac = info.get("mac")
        uid = coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        self._attr_unique_id = f"{uid}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(uid))},
            connections={(CONNECTION_NETWORK_MAC, format_mac(mac))} if mac else set(),
            manufacturer="TP-Link",
            model=info.get("device_model"),
            name=info.get("device_alias") or coordinator.config_entry.title,
            sw_version=info.get("sw_version"),
            hw_version=info.get("hw_version"),
        )
