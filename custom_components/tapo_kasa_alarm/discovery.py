"""Follow cameras to a new IP address, like the TP-Link integration does.

The TP-Link integration runs UDP discovery when Home Assistant starts and
every 15 minutes, and updates the IP of a configured device found at a new
address. The same is done here for the cameras that have the discovery
option on. Discovery only listens for the devices' broadcast answers; it
does not log in to anything.
"""

from __future__ import annotations

import logging

from homeassistant.components import network
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from .api import discover_macs
from .const import CONF_DISCOVERY, DEBUG_LOGGER_NAME, DEFAULT_DISCOVERY, DOMAIN

_LOGGER = logging.getLogger(__name__)


def discovery_enabled(entry: ConfigEntry) -> bool:
    """Return whether the camera should be followed to a new IP."""
    return entry.options.get(CONF_DISCOVERY, DEFAULT_DISCOVERY)


async def async_discover_and_update(hass: HomeAssistant) -> None:
    """Run discovery once and move cameras whose IP changed."""
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.unique_id and discovery_enabled(entry) and not entry.disabled_by
    ]
    if not entries:
        return
    addresses = [
        str(address)
        for address in await network.async_get_ipv4_broadcast_addresses(hass)
    ]
    found = {
        format_mac(mac): host for mac, host in (await discover_macs(addresses)).items()
    }
    if logging.getLogger(DEBUG_LOGGER_NAME).isEnabledFor(logging.DEBUG):
        logging.getLogger(DEBUG_LOGGER_NAME).debug(
            "discovery on %s found %s", addresses, found
        )
    for entry in entries:
        new_host = found.get(entry.unique_id)
        if not new_host or new_host == entry.data[CONF_HOST]:
            continue
        _LOGGER.info(
            "%s moved from %s to %s", entry.title, entry.data[CONF_HOST], new_host
        )
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_HOST: new_host}
        )
        if entry.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY):
            hass.config_entries.async_schedule_reload(entry.entry_id)
