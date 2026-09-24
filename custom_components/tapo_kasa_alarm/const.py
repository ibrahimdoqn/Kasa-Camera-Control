"""Constants for the Kasa Camera Control integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "tapo_kasa_alarm"

# Login like Tapo Control: the camera account, or "admin" with the TP-Link
# cloud password when one is given.
CONF_CLOUD_PASSWORD = "cloud_password"
CONF_IS_KLAP = "is_klap"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 5
MIN_SCAN_INTERVAL = 5

# The cameras end the session about 10 minutes after login. Log in again
# before that (0 turns it off).
CONF_SESSION_RENEW = "session_renew"
DEFAULT_SESSION_RENEW = 8  # minutes
MAX_SESSION_RENEW = 60

# Delay before a requested refresh.
REQUEST_REFRESH_DELAY = 0.35

ALARM_SECTION = "chn1_msg_alarm_info"
PUSH_SECTION = "chn1_msg_push_info"
MODE_SOUND = "sound"
MODE_LIGHT = "light"


def scan_interval(seconds: int | None) -> timedelta:
    """Return a bounded polling interval."""
    return timedelta(seconds=max(MIN_SCAN_INTERVAL, seconds or DEFAULT_SCAN_INTERVAL))
