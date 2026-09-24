"""Reboot button, like the TP-Link integration's restart button."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
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
    """Set up the reboot button."""
    async_add_entities([RebootButton(entry.runtime_data)])


class RebootButton(TapoAlarmEntity, ButtonEntity):
    """Reboot the camera."""

    _attr_device_class = ButtonDeviceClass.RESTART
    # Same category as the TP-Link reboot button. TP-Link disables it by
    # default; here it is enabled because it was asked for.
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "reboot")

    async def async_press(self) -> None:
        await self.coordinator.async_reboot()
