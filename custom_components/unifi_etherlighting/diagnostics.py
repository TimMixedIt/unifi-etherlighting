"""Allowlist-based Home Assistant diagnostics for the productive read path."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import RuntimeData
from .const import VERSION

_ALLOWED_KEYS = frozenset(
    {
        "integration_version",
        "controller_status",
        "controller_type",
        "network_application_version",
        "device_count",
        "switch_models",
        "firmware_versions",
        "capabilities",
        "last_error_code",
        "last_successful_read",
        "last_verified_write",
        "write_capability",
        "write_block_reason",
        "missing_confirmed_fields",
        "brightness_read_supported",
        "brightness_write_supported",
        "brightness_write_ready",
        "options",
    }
)
_ALLOWED_OPTIONS = frozenset(
    {
        "poll_interval",
        "diagnostic_sensors",
        "debug_diagnostics",
        "verify_ssl",
    }
)
_ALLOWED_CAPABILITY_KEYS = frozenset({"capability", "state", "evidence"})


def redact_diagnostics(data: Mapping[str, Any]) -> dict[str, Any]:
    """Keep an explicit safe subset; all unlisted data including IDs is omitted."""
    redacted: dict[str, Any] = {}
    for key in _ALLOWED_KEYS:
        if key not in data:
            continue
        value = data[key]
        if key == "options" and isinstance(value, Mapping):
            redacted[key] = {
                option: value[option] for option in _ALLOWED_OPTIONS if option in value
            }
        elif key == "capabilities" and isinstance(value, (list, tuple)):
            redacted[key] = [
                {
                    capability_key: item[capability_key]
                    for capability_key in _ALLOWED_CAPABILITY_KEYS
                    if capability_key in item
                }
                for item in value
                if isinstance(item, Mapping)
            ]
        elif isinstance(value, (str, int, float, bool, type(None), list, tuple)):
            redacted[key] = value
    return redacted


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return bounded evidence metadata and never entry credentials or raw responses."""
    runtime: RuntimeData = entry.runtime_data
    data = runtime.coordinator.data
    raw = {
        "integration_version": VERSION,
        "controller_status": data.controller_status,
        "controller_type": data.controller_type,
        "network_application_version": data.network_application_version,
        "device_count": len(data.devices),
        "switch_models": sorted({device.model for device in data.devices}),
        "firmware_versions": sorted({device.firmware for device in data.devices}),
        "capabilities": [
            {
                "capability": item.capability,
                "state": item.state.value,
                "evidence": item.evidence.value,
            }
            for item in data.capabilities
        ],
        "last_error_code": data.last_error,
        "write_capability": data.write_capability,
        "write_block_reason": data.write_block_reason,
        "missing_confirmed_fields": list(data.missing_confirmed_fields),
        "brightness_read_supported": any(
            device.brightness_read_supported for device in data.devices
        ),
        "brightness_write_supported": (
            "candidate"
            if any(
                device.brightness_write_supported.value == "candidate"
                for device in data.devices
            )
            else "unsupported"
        ),
        "brightness_write_ready": any(
            device.brightness_write_ready for device in data.devices
        ),
        "last_successful_read": (
            data.last_successful_update.isoformat()
            if data.last_successful_update
            else None
        ),
        "last_verified_write": (
            data.last_verified_write.isoformat() if data.last_verified_write else None
        ),
        "options": entry.options,
        # Credentials and identifiers may exist in entry.data but are intentionally absent.
    }
    return redact_diagnostics(raw)
