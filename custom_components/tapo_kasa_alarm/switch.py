"""Alarm and notification switches (same toggles as in the Tapo app)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TapoAlarmConfigEntry
from .api import alarm_modes
from .const import CONF_DEBUG, MODE_LIGHT, MODE_SOUND
from .coordinator import TapoAlarmCoordinator
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
    entities.append(DebugModeSwitch(coordinator))
    async_add_entities(entities)


class AlarmSwitch(TapoAlarmEntity, SwitchEntity):
    """Turns the camera's automatic alarm on/off."""

    _attr_icon = "mdi:alarm-light"

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "alarm")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data["alarm"].get("enabled") == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.debug_command("turn on")
        await self.coordinator.async_set_alarm(enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.debug_command("turn off")
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
        modes = alarm_modes(self.coordinator.data["alarm"])
        # Some firmwares call the sound mode "siren".
        if self._mode == MODE_SOUND:
            return MODE_SOUND in modes or "siren" in modes
        return self._mode in modes

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.debug_command("turn on")
        await self.coordinator.async_set_alarm(**{self._mode: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.debug_command("turn off")
        await self.coordinator.async_set_alarm(**{self._mode: False})


class NotificationSwitch(TapoAlarmEntity, SwitchEntity):
    """Tapo app push notifications on/off."""

    _attr_icon = "mdi:bell-ring"

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "notifications")

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data.get("push"))

    @property
    def is_on(self) -> bool:
        return (self.coordinator.data.get("push") or {}).get("notification_enabled") == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.debug_command("turn on")
        await self.coordinator.async_set_notifications(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.debug_command("turn off")
        await self.coordinator.async_set_notifications(False)


class DebugModeSwitch(TapoAlarmEntity, SwitchEntity):
    """Debug mode: detailed logs of everything done with this camera.

    Stored in the options, so it stays on across restarts and the
    connection at startup is logged too.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:bug"

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "debug_mode")

    @property
    def available(self) -> bool:
        # Usable while the camera is unreachable, to log the outage.
        return True

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.config_entry.options.get(CONF_DEBUG))

    async def _set(self, enabled: bool) -> None:
        entry = self.coordinator.config_entry
        self.hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_DEBUG: enabled}
        )
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
