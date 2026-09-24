"""Connection diagnostic: whether the camera answers ping."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TapoAlarmConfigEntry
from .coordinator import TapoAlarmCoordinator
from .entity import CameraPingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TapoAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the connection sensor."""
    async_add_entities([ConnectionSensor(entry.runtime_data)])


class ConnectionSensor(CameraPingEntity, BinarySensorEntity):
    """On while the camera answers ping; the attributes describe the last outage."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "connection")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.connected

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.coordinator.data
        return {
            "latency_ms": state.latency_ms,
            "last_disconnect": _iso(state.last_disconnect),
            "last_outage_seconds": state.last_outage_seconds,
            "down_since": _iso(state.down_since),
        }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
