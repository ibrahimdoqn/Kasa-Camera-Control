"""Alarm switches (same toggle as the Tapo app's "Alarm" setting)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TapoAlarmConfigEntry
from .const import MODE_LIGHT, MODE_SOUND
from .coordinator import TapoAlarmCoordinator
from .entity import TapoAlarmEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TapoAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the alarm switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            AlarmSwitch(coordinator),
            AlarmModeSwitch(coordinator, MODE_SOUND),
            AlarmModeSwitch(coordinator, MODE_LIGHT),
        ]
    )


class AlarmSwitch(TapoAlarmEntity, SwitchEntity):
    """Turns the camera's automatic alarm on/off."""

    _attr_icon = "mdi:alarm-light"

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "alarm")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("enabled") == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_alarm(enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_alarm(enabled=False)


class AlarmModeSwitch(TapoAlarmEntity, SwitchEntity):
    """Selects whether the alarm uses sound and/or light."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: TapoAlarmCoordinator, mode: str) -> None:
        super().__init__(coordinator, f"alarm_{mode}")
        self._mode = mode
        self._attr_icon = "mdi:volume-high" if mode == MODE_SOUND else "mdi:lightbulb-on"

    @property
    def is_on(self) -> bool:
        modes = self.coordinator.data.get("alarm_mode") or []
        # Some firmwares call the sound mode "siren".
        if self._mode == MODE_SOUND:
            return MODE_SOUND in modes or "siren" in modes
        return self._mode in modes

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_alarm(**{self._mode: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_alarm(**{self._mode: False})
