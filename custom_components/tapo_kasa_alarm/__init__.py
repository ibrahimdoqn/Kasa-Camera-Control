"""Kasa Camera Control: Tapo camera alarm control via pytapo.

The camera is connected the same way the Tapo Control integration does it
with a cloud password: pytapo, "admin" and the TP-Link cloud password.
A MAC check makes sure a changed DHCP lease never mixes up cameras. Each
poll reads only the alarm and notification config, in a single request.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import format_mac

from .api import AuthenticationError, CameraError, TapoAlarmApi, basic_info, connect
from .const import (
    CONF_CLOUD_PASSWORD,
    CONF_IS_KLAP,
    CONF_SCAN_INTERVAL,
    DOMAIN,
    scan_interval,
)
from .coordinator import TapoAlarmCoordinator, auth_failed, auth_ok
from .port_check import PortCheckCoordinator, port_check_interval

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]

type TapoAlarmConfigEntry = ConfigEntry[TapoAlarmCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TapoAlarmConfigEntry) -> bool:
    """Set up the camera from a config entry."""
    host: str = entry.data[CONF_HOST]
    if not entry.data.get(CONF_CLOUD_PASSWORD):
        raise ConfigEntryAuthFailed("The TP-Link cloud password is needed")
    try:
        controller = await hass.async_add_executor_job(
            connect,
            hass,
            host,
            entry.data[CONF_CLOUD_PASSWORD],
            entry.data.get(CONF_IS_KLAP),
        )
    except AuthenticationError as err:
        # Like Tapo Control: try again a few times before asking.
        if auth_failed(hass, entry):
            raise ConfigEntryAuthFailed(str(err)) from err
        raise ConfigEntryNotReady(f"Login rejected, trying again: {err}") from err
    except CameraError as err:
        raise ConfigEntryNotReady(str(err)) from err
    # The password was accepted: start counting rejected logins again.
    auth_ok(hass, entry)

    api = TapoAlarmApi(hass, controller, host)
    mac = basic_info(controller).get("mac")
    if entry.unique_id and mac and (found := format_mac(mac)) != entry.unique_id:
        # The DHCP lease probably moved and another device now has this IP.
        # Do not mix up cameras.
        await api.close()
        raise ConfigEntryNotReady(
            f"Expected {entry.unique_id} at {host} but found {found}"
        )

    if entry.data.get(CONF_IS_KLAP) is None:
        # Found by pytapo on this first connection; saved like Tapo Control
        # does, so later setups skip the check. Only after the MAC check, so
        # another device at this IP never decides it.
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_IS_KLAP: bool(controller.isKLAP)}
        )

    coordinator = TapoAlarmCoordinator(hass, entry, api)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await api.close()
        raise

    coordinator.port_check = PortCheckCoordinator(hass, entry, host)
    await coordinator.port_check.async_refresh()

    entry.runtime_data = coordinator
    _remove_connection_sensors(hass, entry)
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
    coordinator = entry.runtime_data
    coordinator.update_interval = scan_interval(entry.options.get(CONF_SCAN_INTERVAL))
    if coordinator.port_check is not None:
        coordinator.port_check.update_interval = port_check_interval(entry.options)


def _remove_connection_sensors(hass: HomeAssistant, entry: TapoAlarmConfigEntry) -> None:
    """Drop connection sensors earlier versions created and no longer provided."""
    registry = er.async_get(hass)
    for key in ("connected_since", "disconnects"):
        unique_id = f"{entry.unique_id or entry.entry_id}_{key}"
        if entity_id := registry.async_get_entity_id("sensor", DOMAIN, unique_id):
            registry.async_remove(entity_id)
