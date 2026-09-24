"""Connection diagnostic: whether the camera is connected."""

from __future__ import annotations

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
from .entity import TapoAlarmEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TapoAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the connection sensor."""
    async_add_entities([ConnectionSensor(entry.runtime_data)])


class ConnectionSensor(TapoAlarmEntity, BinarySensorEntity):
    """On while the camera answers, off from a failed poll, a command that
    cannot reach the camera or a reboot until the next successful poll.

    The attributes describe the last disconnect.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "connection")

    @property
    def available(self) -> bool:
        # Stays available so that "disconnected" can be shown.
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.connected

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        coordinator = self.coordinator
        return {
            "last_disconnect": _iso(coordinator.last_disconnect),
            "last_disconnect_reason": coordinator.last_disconnect_reason,
            "last_disconnect_source": coordinator.last_disconnect_source,
            "last_outage_seconds": coordinator.last_outage_seconds,
            "down_since": _iso(coordinator.down_since),
        }


def _iso(value) -> str | None:
    return value.isoformat() if value else None
