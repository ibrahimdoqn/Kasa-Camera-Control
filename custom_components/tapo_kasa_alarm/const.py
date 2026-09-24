"""Constants for the Kasa Camera Control integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "tapo_kasa_alarm"

# Login like Tapo Control with a cloud password: "admin" and the TP-Link
# cloud password.
CONF_CLOUD_PASSWORD = "cloud_password"
# Whether the camera uses the KLAP login, found once and saved like Tapo
# Control does.
CONF_IS_KLAP = "is_klap"

# Like Tapo Control: a rejected login ("Invalid authentication data") is
# tried again this many times before Home Assistant asks for the password.
# Cameras can reject a valid login for a moment, e.g. while they restart.
AUTH_RETRIES = 3

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 5
MIN_SCAN_INTERVAL = 5

ALARM_SECTION = "chn1_msg_alarm_info"
PUSH_SECTION = "chn1_msg_push_info"
MODE_SOUND = "sound"
MODE_LIGHT = "light"


def scan_interval(seconds: int | None) -> timedelta:
    """Return a bounded polling interval."""
    return timedelta(seconds=max(MIN_SCAN_INTERVAL, seconds or DEFAULT_SCAN_INTERVAL))
