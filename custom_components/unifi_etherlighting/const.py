"""Constants that never contain controller-derived or secret data."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "unifi_etherlighting"
NAME = "UniFi Etherlighting"
VERSION = "0.3.1"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_USE_SSL = "use_ssl"
CONF_VERIFY_SSL = "verify_ssl"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SITE = "site"
CONF_DEVICE_IDS = "device_ids"
CONF_POLL_INTERVAL = "poll_interval"
CONF_DIAGNOSTIC_SENSORS = "diagnostic_sensors"
CONF_DEBUG_DIAGNOSTICS = "debug_diagnostics"
CONF_AUTO_DISCOVERY_PREPARED = "automatic_device_discovery_prepared"

DEFAULT_PORT = 443
DEFAULT_POLL_INTERVAL_SECONDS = 900
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_POLL_INTERVAL_SECONDS)
CONTROLLER_STATUS_ONLINE = "online"
CONTROLLER_STATUS_UNSUPPORTED = "unsupported_version_combination"

BRIGHTNESS_MINIMUM = 1
BRIGHTNESS_MAXIMUM = 100
BRIGHTNESS_STEP = 1
BRIGHTNESS_UNIT = "%"

WRITE_CAPABILITY_ENABLED = True
WRITE_CAPABILITY_STATE = "ready"
WRITE_CAPABILITY_BLOCKED_STATE = "blocked"
WRITE_BLOCK_REASON = "confirmed_write_configuration_incomplete"
ACTIVE_WRITE_BLOCK_REASON: str | None = (
    None if WRITE_CAPABILITY_ENABLED else WRITE_BLOCK_REASON
)
MISSING_CONFIRMED_WRITE_FIELDS: tuple[str, ...] = ()
WRITE_DISABLED_MESSAGE = (
    "Etherlighting writes are temporarily disabled because the complete "
    "confirmed write configuration is unavailable."
)
