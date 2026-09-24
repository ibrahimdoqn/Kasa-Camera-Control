"""Connection diagnostic: since when the camera has answered ping without a break."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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
    """Set up the connected-since sensor."""
    async_add_entities([ConnectedSinceSensor(entry.runtime_data)])


class ConnectedSinceSensor(CameraPingEntity, SensorEntity):
    """When the camera started answering ping without a break.

    Home Assistant shows a timestamp as "x minutes ago", which is how long
    the camera has been reachable. Unknown while it does not answer.
    Counted from when Home Assistant set the camera up.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "connected_since")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.data.connected_since
