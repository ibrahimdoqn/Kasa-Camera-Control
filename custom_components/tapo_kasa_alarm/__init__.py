"""Kasa Camera Control: Tapo camera alarm control via python-kasa.

The camera is connected the same way Home Assistant's TP-Link integration
does it: a Home Assistant managed HTTP session, the connection parameters
saved from the first successful connection, a MAC check so a changed DHCP
lease never mixes up cameras, and UDP discovery to follow a camera to a
new IP address.
"""

from __future__ import annotations

import logging

from kasa.httpclient import get_cookie_jar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.device_registry import format_mac

from .api import AuthenticationError, KasaException, TapoAlarmApi, connect_device
from .const import CONF_CONNECTION_PARAMETERS, CONF_SCAN_INTERVAL, DOMAIN, scan_interval
from .coordinator import TapoAlarmCoordinator
from .discovery import async_update_host

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH]

type TapoAlarmConfigEntry = ConfigEntry[TapoAlarmCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TapoAlarmConfigEntry) -> bool:
    """Set up the camera from a config entry."""
    host: str = entry.data[CONF_HOST]
    # Same HTTP session setup as the TP-Link integration.
    client = async_create_clientsession(
        hass, verify_ssl=False, cookie_jar=get_cookie_jar()
    )
    try:
        device = await connect_device(
            host,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            http_client=client,
            connection_parameters=entry.data.get(CONF_CONNECTION_PARAMETERS),
        )
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except KasaException as err:
        if await async_update_host(hass, entry):
            raise ConfigEntryNotReady(f"{err}; camera found at a new IP address") from err
        raise ConfigEntryNotReady(str(err)) from err

    if entry.unique_id and format_mac(device.mac) != entry.unique_id:
        # The DHCP lease probably moved and another device now has this IP.
        # Do not mix up cameras: look for ours and retry.
        found = format_mac(device.mac)
        await device.disconnect()
        await async_update_host(hass, entry)
        raise ConfigEntryNotReady(
            f"Expected {entry.unique_id} at {host} but found {found}"
        )

    connection_parameters = device.config.connection_type.to_dict()
    if entry.data.get(CONF_CONNECTION_PARAMETERS) != connection_parameters:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_CONNECTION_PARAMETERS: connection_parameters},
        )

    api = TapoAlarmApi(device)
    coordinator = TapoAlarmCoordinator(hass, entry, api)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await api.close()
        raise

    entry.runtime_data = coordinator
    _remove_old_entities(hass, entry)
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
    """Apply a changed polling interval without reconnecting."""
    entry.runtime_data.update_interval = scan_interval(
        entry.options.get(CONF_SCAN_INTERVAL)
    )


def _remove_old_entities(hass: HomeAssistant, entry: TapoAlarmConfigEntry) -> None:
    """Drop entities that older versions created and are no longer provided."""
    registry = er.async_get(hass)
    uid = entry.unique_id or entry.entry_id
    for platform, key in (("siren", "siren"), ("switch", "rich_notifications")):
        if entity_id := registry.async_get_entity_id(platform, DOMAIN, f"{uid}_{key}"):
            registry.async_remove(entity_id)
