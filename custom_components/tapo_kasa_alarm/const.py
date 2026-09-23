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

# The cameras end the session about 10 minutes after login and answer the
# next request with HTTP 401. Log in again before that (0 turns it off).
CONF_SESSION_RENEW = "session_renew"
DEFAULT_SESSION_RENEW = 8  # minutes
MAX_SESSION_RENEW = 60

# Debug mode (switch in the diagnostics section, stored in the options):
# detailed logs of everything the integration does with the camera.
CONF_DEBUG = "debug"
DEBUG_LOGGER_NAME = "custom_components.tapo_kasa_alarm.debug"

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
