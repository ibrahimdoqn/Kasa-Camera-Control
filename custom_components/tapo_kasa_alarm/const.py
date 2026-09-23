"""Constants for the Kasa Camera Control integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "tapo_kasa_alarm"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15

DEFAULT_TIMEOUT = 10
DISCOVERY_TIMEOUT = 5
# Look for a camera that stopped answering at a new IP at most this often.
REDISCOVERY_INTERVAL = timedelta(minutes=15)
# Consecutive failed polls before looking for a new IP.
REDISCOVERY_AFTER_FAILURES = 3

CONF_CONNECTION_PARAMETERS = "connection_parameters"

ALARM_SECTION = "chn1_msg_alarm_info"
PUSH_SECTION = "chn1_msg_push_info"
MODE_SOUND = "sound"
MODE_LIGHT = "light"


def scan_interval(seconds: int | None) -> timedelta:
    """Return a bounded polling interval."""
    return timedelta(seconds=max(MIN_SCAN_INTERVAL, seconds or DEFAULT_SCAN_INTERVAL))
