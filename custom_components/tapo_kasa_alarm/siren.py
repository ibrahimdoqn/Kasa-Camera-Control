"""Manual siren: sound the camera alarm right now."""

from __future__ import annotations

from typing import Any

from homeassistant.components.siren import SirenEntity, SirenEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TapoAlarmConfigEntry
from .api import KasaException
from .coordinator import TapoAlarmCoordinator
from .entity import TapoAlarmEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TapoAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the siren."""
    async_add_entities([ManualSiren(entry.runtime_data)])


class ManualSiren(TapoAlarmEntity, SirenEntity):
    """Start/stop the camera siren (the camera does not report its state)."""

    _attr_assumed_state = True
    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF

    def __init__(self, coordinator: TapoAlarmCoordinator) -> None:
        super().__init__(coordinator, "siren")
        self._attr_is_on = False

    async def _set(self, start: bool) -> None:
        try:
            await self.coordinator.api.manual_alarm(start)
        except KasaException as err:
            raise HomeAssistantError(f"Could not control siren: {err}") from err
        self._attr_is_on = start
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
