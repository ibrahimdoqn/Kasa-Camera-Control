"""Connection diagnostic sensors: connected since and disconnect count."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TapoAlarmConfigEntry
from .coordinator import TapoAlarmCoordinator
from .entity import TapoAlarmEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TapoAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the diagnostic sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [ConnectedSinceSensor(coordinator), DisconnectsSensor(coordinator)]
    )


class _Diagnostic:
    """Diagnostic sensors stay available while the camera is unreachable."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        return True


class ConnectedSinceSensor(_Diagnostic, TapoAlarmEntity, SensorEntity):
    """When the current connection started (unknown while disconnected).

    Home Assistant shows a timestamp both as the time and as "x minutes
    ago", which is how long the connection has lasted.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:lan-connect"

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "connected_since")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.connected_since


class DisconnectsSensor(_Diagnostic, TapoAlarmEntity, SensorEntity):
    """Number of disconnects since Home Assistant started, with the last one's details.

    Starts from 0 on every Home Assistant restart (and integration reload).
    """

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:lan-disconnect"

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "disconnects")

    @property
    def native_value(self) -> int:
        return self.coordinator.disconnects

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        coordinator = self.coordinator
        return {
            "last_disconnect": coordinator.last_disconnect.isoformat()
            if coordinator.last_disconnect
            else None,
            "last_disconnect_reason": coordinator.last_disconnect_reason,
            "last_outage_seconds": coordinator.last_outage_seconds,
            "down_since": coordinator.down_since.isoformat()
            if coordinator.down_since
            else None,
        }
