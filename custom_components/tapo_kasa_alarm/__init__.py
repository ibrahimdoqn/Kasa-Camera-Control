"""Tapo camera alarm control via python-kasa (the TP-Link integration library)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import AuthenticationError, KasaException, TapoAlarmApi, connect_device
from .coordinator import TapoAlarmCoordinator

PLATFORMS = [Platform.SIREN, Platform.SWITCH]

type TapoAlarmConfigEntry = ConfigEntry[TapoAlarmCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TapoAlarmConfigEntry) -> bool:
    """Set up the camera from a config entry."""
    try:
        device = await connect_device(
            entry.data[CONF_HOST], entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except KasaException as err:
        raise ConfigEntryNotReady(str(err)) from err

    api = TapoAlarmApi(device)
    coordinator = TapoAlarmCoordinator(hass, entry, api)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await api.close()
        raise

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TapoAlarmConfigEntry) -> bool:
    """Unload a config entry and close the camera session."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.api.close()
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: TapoAlarmConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
