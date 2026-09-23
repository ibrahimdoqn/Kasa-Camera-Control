"""Kasa Camera Control: Tapo camera alarm control via python-kasa.

The camera is connected the same way Home Assistant's TP-Link integration
does it: a Home Assistant managed HTTP session, the connection
parameters saved from the first successful connection, a MAC check so a
changed DHCP lease never mixes up cameras, polling every 5 seconds and
UDP discovery to follow a camera to a new IP address. Each poll reads
only the alarm and notification config, in a single request.
"""

from __future__ import annotations

import logging
from typing import Any

from kasa.httpclient import get_cookie_jar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .api import AuthenticationError, KasaException, TapoAlarmApi, connect_device
from .const import (
    CONF_CONNECTION_PARAMETERS,
    CONF_DEBUG,
    DEBUG_LOGGER_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SESSION_RENEW,
    DEFAULT_SESSION_RENEW,
    DISCOVERY_INTERVAL,
    DOMAIN,
    scan_interval,
)
from .coordinator import TapoAlarmCoordinator
from .discovery import async_discover_and_update

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type TapoAlarmConfigEntry = ConfigEntry[TapoAlarmCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Run discovery at start and every 15 minutes, like the TP-Link integration."""

    async def _async_discovery(*_: Any) -> None:
        await async_discover_and_update(hass)

    hass.async_create_background_task(
        _async_discovery(), f"{DOMAIN} first discovery", eager_start=True
    )
    async_track_time_interval(
        hass, _async_discovery, DISCOVERY_INTERVAL, cancel_on_shutdown=True
    )
    return True


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
        raise ConfigEntryNotReady(str(err)) from err

    if (
        entry.unique_id
        and device.mac
        and (found := format_mac(device.mac)) != entry.unique_id
    ):
        # The DHCP lease probably moved and another device now has this IP.
        # Do not mix up cameras: wait for discovery to find ours.
        await device.disconnect()
        raise ConfigEntryNotReady(
            f"Expected {entry.unique_id} at {host} but found {found}"
        )

    connection_parameters = device.config.connection_type.to_dict()
    if entry.data.get(CONF_CONNECTION_PARAMETERS) != connection_parameters:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_CONNECTION_PARAMETERS: connection_parameters},
        )

    api = TapoAlarmApi(
        device, entry.options.get(CONF_SESSION_RENEW, DEFAULT_SESSION_RENEW)
    )
    api.debug = bool(entry.options.get(CONF_DEBUG))
    async_apply_debug_logging(hass)
    api.dbg(
        "connected: model=%s firmware=%s hardware=%s mac=%s connection=%s"
        " session_renew=%smin scan_interval=%ss",
        device.model,
        device.hw_info.get("sw_ver"),
        device.hw_info.get("hw_ver"),
        device.mac,
        connection_parameters,
        api.session_renew_minutes,
        entry.options.get(CONF_SCAN_INTERVAL),
    )
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
        entry.runtime_data.api.dbg("unloading, closing the session")
        entry.runtime_data.api.debug = False
        await entry.runtime_data.api.close()
        async_apply_debug_logging(hass, exclude=entry.entry_id)
    return unloaded


@callback
def async_apply_debug_logging(hass: HomeAssistant, exclude: str | None = None) -> None:
    """Turn the detailed debug log on while any camera has debug mode on.

    Home Assistant normally only writes warnings and errors; the debug
    logger gets its own level so the detailed lines reach the full log.
    """
    enabled = any(
        entry.options.get(CONF_DEBUG)
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id != exclude and not entry.disabled_by
    )
    logging.getLogger(DEBUG_LOGGER_NAME).setLevel(
        logging.DEBUG if enabled else logging.NOTSET
    )


async def _async_options_updated(hass: HomeAssistant, entry: TapoAlarmConfigEntry) -> None:
    """Apply changed options without reconnecting.

    The discovery option is read on every discovery run.
    """
    coordinator = entry.runtime_data
    coordinator.update_interval = scan_interval(entry.options.get(CONF_SCAN_INTERVAL))
    coordinator.api.session_renew_minutes = entry.options.get(
        CONF_SESSION_RENEW, DEFAULT_SESSION_RENEW
    )
    debug = bool(entry.options.get(CONF_DEBUG))
    if debug != coordinator.api.debug:
        # Log the switch in both directions.
        coordinator.api.debug = True
        coordinator.api.dbg("debug mode %s", "on" if debug else "off")
        coordinator.api.debug = debug
    async_apply_debug_logging(hass)
    coordinator.api.dbg(
        "options: scan_interval=%s session_renew=%s discovery=%s",
        entry.options.get(CONF_SCAN_INTERVAL),
        coordinator.api.session_renew_minutes,
        entry.options.get("discovery"),
    )


def _remove_old_entities(hass: HomeAssistant, entry: TapoAlarmConfigEntry) -> None:
    """Drop entities that older versions created and are no longer provided."""
    registry = er.async_get(hass)
    uid = entry.unique_id or entry.entry_id
    for platform, key in (("siren", "siren"), ("switch", "rich_notifications")):
        if entity_id := registry.async_get_entity_id(platform, DOMAIN, f"{uid}_{key}"):
            registry.async_remove(entity_id)
