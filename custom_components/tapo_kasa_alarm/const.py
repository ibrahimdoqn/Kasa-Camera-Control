"""Constants for the Kasa Camera Control integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "tapo_kasa_alarm"

CONF_SCAN_INTERVAL = "scan_interval"
# Same polling interval as the TP-Link integration.
DEFAULT_SCAN_INTERVAL = 5
MIN_SCAN_INTERVAL = 5

# Follow cameras to a new IP by MAC with UDP discovery (on by default,
# like the TP-Link integration; can be turned off for static IPs).
CONF_DISCOVERY = "discovery"
DEFAULT_DISCOVERY = True
DISCOVERY_INTERVAL = timedelta(minutes=15)

# Same delay as the TP-Link integration before refreshing after a command.
REQUEST_REFRESH_DELAY = 0.35

# Same timeouts as the TP-Link integration.
DEFAULT_TIMEOUT = 5
DISCOVERY_TIMEOUT = 5

CONF_CONNECTION_PARAMETERS = "connection_parameters"

ALARM_SECTION = "chn1_msg_alarm_info"
PUSH_SECTION = "chn1_msg_push_info"
MODE_SOUND = "sound"
MODE_LIGHT = "light"


def scan_interval(seconds: int | None) -> timedelta:
    """Return a bounded polling interval."""
    return timedelta(seconds=max(MIN_SCAN_INTERVAL, seconds or DEFAULT_SCAN_INTERVAL))
