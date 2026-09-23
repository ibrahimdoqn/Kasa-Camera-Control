"""Follow a camera to a new IP address, like the TP-Link integration does."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import network
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from .api import discover_macs

_LOGGER = logging.getLogger(__name__)


async def async_update_host(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Find the camera by MAC with UDP discovery and store its new IP.

    Returns True when the IP address changed.
    """
    if not entry.unique_id:
        return False
    addresses = [
        str(address)
        for address in await network.async_get_ipv4_broadcast_addresses(hass)
    ]
    found = {
        format_mac(mac): host for mac, host in (await discover_macs(addresses)).items()
    }
    new_host = found.get(entry.unique_id)
    if not new_host or new_host == entry.data[CONF_HOST]:
        return False
    _LOGGER.info(
        "%s moved from %s to %s", entry.title, entry.data[CONF_HOST], new_host
    )
    data: dict[str, Any] = {**entry.data, CONF_HOST: new_host}
    hass.config_entries.async_update_entry(entry, data=data)
    return True
