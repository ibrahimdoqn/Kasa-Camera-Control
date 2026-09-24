"""Connection diagnostic: since when the camera has been connected."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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
    """Set up the connected-since sensor."""
    async_add_entities([ConnectedSinceSensor(entry.runtime_data)])


class ConnectedSinceSensor(TapoAlarmEntity, SensorEntity):
    """When the current uninterrupted connection started.

    Home Assistant shows a timestamp as "x minutes ago", which is how long
    the camera has been connected without a break. Unknown while it is not
    connected. Counted from when Home Assistant set the camera up.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "connected_since")

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.connected_since
