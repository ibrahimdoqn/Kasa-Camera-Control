"""Kasa Camera Control: Tapo camera alarm control via pytapo.

The camera is connected the same way the Tapo Control integration does it
with a cloud password: pytapo, "admin" and the TP-Link cloud password.
A MAC check makes sure a changed DHCP lease never mixes up cameras. Each
poll reads only the alarm and notification config, in a single request.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac

from .api import AuthenticationError, CameraError, TapoAlarmApi, basic_info, connect
from .const import CONF_CLOUD_PASSWORD, CONF_SCAN_INTERVAL, scan_interval
from .coordinator import TapoAlarmCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]

type TapoAlarmConfigEntry = ConfigEntry[TapoAlarmCoordinator]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Move 1.x (python-kasa) entries to pytapo.

    1.x logged in with the TP-Link cloud account. python-kasa logs in to
    cameras as "admin" with the cloud password, which is what Tapo Control
    does when a cloud password is given, so the camera keeps working
    without asking for new credentials.
    """
    if entry.version == 1:
        data = {
            CONF_HOST: entry.data[CONF_HOST],
            CONF_CLOUD_PASSWORD: entry.data.get(CONF_PASSWORD, ""),
        }
        options = {
            k: v for k, v in entry.options.items() if k not in ("discovery", "session_renew")
        }
        hass.config_entries.async_update_entry(
            entry, data=data, options=options, version=2
        )
        _LOGGER.info("Migrated %s to pytapo", entry.title)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TapoAlarmConfigEntry) -> bool:
    """Set up the camera from a config entry."""
    host: str = entry.data[CONF_HOST]
    if not entry.data.get(CONF_CLOUD_PASSWORD):
        # Set up with a camera account in 2.0.0: ask for the cloud password.
        raise ConfigEntryAuthFailed("The TP-Link cloud password is needed")
    try:
        controller = await hass.async_add_executor_job(
            connect,
            hass,
            host,
            entry.data[CONF_CLOUD_PASSWORD],
        )
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except CameraError as err:
        raise ConfigEntryNotReady(str(err)) from err

    api = TapoAlarmApi(hass, controller, host)
    mac = basic_info(controller).get("mac")
    if entry.unique_id and mac and (found := format_mac(mac)) != entry.unique_id:
        # The DHCP lease probably moved and another device now has this IP.
        # Do not mix up cameras.
        await api.close()
        raise ConfigEntryNotReady(
            f"Expected {entry.unique_id} at {host} but found {found}"
        )

    coordinator = TapoAlarmCoordinator(hass, entry, api)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await api.close()
        raise

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TapoAlarmConfigEntry) -> bool:
    """Unload a config entry and close the camera session."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.api.close()
    return unloaded


async def _async_options_updated(hass: HomeAssistant, entry: TapoAlarmConfigEntry) -> None:
    """Apply changed options without reconnecting."""
    entry.runtime_data.update_interval = scan_interval(
        entry.options.get(CONF_SCAN_INTERVAL)
    )

