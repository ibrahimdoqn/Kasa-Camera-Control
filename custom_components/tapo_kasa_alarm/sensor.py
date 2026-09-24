"""Connection diagnostic: uptime, since when the camera has answered without a break."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TapoAlarmConfigEntry
from .coordinator import TapoAlarmCoordinator
from .entity import PortCheckEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TapoAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the uptime sensor."""
    async_add_entities([UptimeSensor(entry.runtime_data)])


class UptimeSensor(PortCheckEntity, SensorEntity):
    """When the camera started answering on port 443 without a break.

    A timestamp, like Home Assistant's own Uptime integration: it is shown
    as "3 hours ago" and does not write a new state every second. Unknown
    while the camera is disconnected. Measured since Home Assistant set
    the camera up.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "uptime")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.data.up_since
