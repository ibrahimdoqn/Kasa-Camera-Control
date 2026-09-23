"""Alarm and notification switches (same toggles as in the Tapo app)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TapoAlarmConfigEntry
from .const import MODE_LIGHT, MODE_SOUND
from .coordinator import NOTIFICATIONS, TapoAlarmCoordinator
from .entity import TapoAlarmEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TapoAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the alarm switches."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = [
        AlarmSwitch(coordinator),
        AlarmModeSwitch(coordinator, MODE_SOUND),
        AlarmModeSwitch(coordinator, MODE_LIGHT),
    ]
    push = coordinator.data.get("push") or {}
    if "notification_enabled" in push:
        entities.append(NotificationSwitch(coordinator))
    async_add_entities(entities)


class QueuedSwitch(TapoAlarmEntity, SwitchEntity):
    """A switch whose changes go through the coordinator's write queue."""

    _key: str

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.value(self._key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # True while the value is queued and not yet confirmed by the camera.
        return {"pending_write": self._key in self.coordinator.pending}

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set(self._key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set(self._key, False)


class AlarmSwitch(QueuedSwitch):
    """Turns the camera's automatic alarm on/off."""

    _attr_icon = "mdi:alarm-light"
    _key = "enabled"

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "alarm")


class AlarmModeSwitch(QueuedSwitch):
    """Selects whether the alarm uses sound and/or light."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: TapoAlarmCoordinator, mode: str) -> None:
        super().__init__(coordinator, f"alarm_{mode}")
        self._key = mode
        self._attr_icon = "mdi:volume-high" if mode == MODE_SOUND else "mdi:lightbulb-on"


class NotificationSwitch(QueuedSwitch):
    """Tapo app push notifications on/off."""

    _attr_icon = "mdi:bell-ring"
    _key = NOTIFICATIONS

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "notifications")

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data.get("push"))
