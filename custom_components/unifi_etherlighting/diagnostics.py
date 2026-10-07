"""Allowlist-based Home Assistant diagnostics for the productive read path."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import RuntimeData
from .compatibility import READ_CONTRACT_MISMATCH_LABELS
from .const import VERSION
from .write_readiness import effective_write_ready, effective_write_readiness

_ALLOWED_KEYS = frozenset(
    {
        "integration_version",
        "controller_status",
        "controller_type",
        "network_application_version",
        "compatibility_profile",
        "network_api_generation_supported",
        "contract_compatible_device_count",
        "configured_device_count",
        "returned_device_count",
        "returned_switch_count",
        "selected_device_count",
        "read_contract_compatible_device_count",
        "runtime_read_contract_reason",
        "read_contract_mismatch_fields",
        "runtime_integration_version",
        "device_count",
        "switch_models",
        "firmware_versions",
        "capabilities",
        "last_error_code",
        "coordinator_last_update_success",
        "coordinator_refresh_error",
        "last_successful_read",
        "last_verified_write",
        "color_metadata_status",
        "color_metadata_error",
        "write_capability",
        "global_write_capability",
        "effective_write_readiness",
        "effective_write_ready",
        "write_block_reason",
        "missing_confirmed_fields",
        "brightness_read_supported",
        "brightness_write_supported",
        "brightness_write_ready",
        "behavior_read_supported",
        "behavior_write_supported",
        "behavior_write_ready",
        "mode_read_supported",
        "mode_write_supported",
        "mode_write_ready",
        "network_color_read_supported",
        "network_color_write_supported",
        "network_color_write_ready",
        "speed_color_read_supported",
        "speed_color_write_supported",
        "speed_color_write_ready",
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
_ALLOWED_RUNTIME_READ_CONTRACT_REASONS = frozenset(
    {
        "unknown",
        "unsupported_network_api_generation",
        "no_configured_devices",
        "selected_devices_not_returned",
        "selected_devices_read_contract_mismatch",
        "read_contract_supported",
    }
)
_ALLOWED_REFRESH_ERROR_CATEGORIES = frozenset(
    {
        "authentication",
        "permission",
        "transport_connection",
        "transport_timeout",
        "transport_tls",
        "schema",
        "response",
        "unknown",
    }
)
_ALLOWED_COLOR_METADATA_STATUSES = frozenset(
    {"not_applicable", "ready", "unavailable"}
)


def _write_support_state(devices: tuple[Any, ...], attribute: str) -> str:
    states = {getattr(device, attribute).value for device in devices}
    if "confirmed" in states:
        return "confirmed"
    if "candidate" in states:
        return "candidate"
    return "unsupported"


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
        elif key == "runtime_read_contract_reason":
            if value in _ALLOWED_RUNTIME_READ_CONTRACT_REASONS:
                redacted[key] = value
        elif key == "coordinator_last_update_success" and isinstance(value, bool):
            redacted[key] = value
        elif key in {"coordinator_refresh_error", "color_metadata_error"}:
            if value in _ALLOWED_REFRESH_ERROR_CATEGORIES or value is None:
                redacted[key] = value
        elif key == "color_metadata_status":
            if value in _ALLOWED_COLOR_METADATA_STATUSES:
                redacted[key] = value
        elif key == "read_contract_mismatch_fields" and isinstance(
            value, (list, tuple)
        ):
            redacted[key] = [
                label for label in value if label in READ_CONTRACT_MISMATCH_LABELS
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
    effective_ready = effective_write_ready(
        data.write_capability, data.devices, data.colors
    )
    raw = {
        "integration_version": VERSION,
        # This comes from the imported runtime module, unlike a version shown by
        # HACS before Home Assistant has reloaded the custom integration.
        "runtime_integration_version": VERSION,
        "controller_status": data.controller_status,
        "controller_type": data.controller_type,
        "network_application_version": data.network_application_version,
        "compatibility_profile": data.compatibility_profile,
        "network_api_generation_supported": data.network_api_generation_supported,
        "contract_compatible_device_count": data.contract_compatible_device_count,
        "configured_device_count": data.configured_device_count,
        "returned_device_count": data.returned_device_count,
        "returned_switch_count": data.returned_switch_count,
        "selected_device_count": data.selected_device_count,
        "read_contract_compatible_device_count": (
            data.read_contract_compatible_device_count
        ),
        "runtime_read_contract_reason": data.runtime_read_contract_reason,
        "read_contract_mismatch_fields": list(
            data.read_contract_mismatch_fields
        ),
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
        # DataUpdateCoordinator retains the last successful snapshot after a
        # later failed poll. Export this boolean separately so diagnostics
        # cannot accidentally present that stale snapshot as live state.
        "coordinator_last_update_success": runtime.coordinator.last_update_success,
        "coordinator_refresh_error": runtime.coordinator.last_refresh_error,
        # Retain the legacy field: it is a release-wide kill switch, not a
        # statement that the current Device contract permits writes.
        "write_capability": data.write_capability,
        "global_write_capability": data.write_capability,
        "effective_write_readiness": effective_write_readiness(
            data.write_capability, data.devices, data.colors
        ),
        "effective_write_ready": effective_ready,
        "write_block_reason": data.write_block_reason,
        "missing_confirmed_fields": list(data.missing_confirmed_fields),
        "brightness_read_supported": any(
            device.brightness_read_supported for device in data.devices
        ),
        "brightness_write_supported": _write_support_state(
            data.devices, "brightness_write_supported"
        ),
        "brightness_write_ready": any(
            device.brightness_write_ready for device in data.devices
        ),
        "behavior_read_supported": any(
            device.behavior_read_supported for device in data.devices
        ),
        "behavior_write_supported": _write_support_state(
            data.devices, "behavior_write_supported"
        ),
        "behavior_write_ready": any(
            device.behavior_write_ready for device in data.devices
        ),
        "mode_read_supported": any(
            device.mode_read_supported for device in data.devices
        ),
        "mode_write_supported": _write_support_state(
            data.devices, "mode_write_supported"
        ),
        "mode_write_ready": any(device.mode_write_ready for device in data.devices),
        "network_color_read_supported": any(
            color.category == "network" and color.read_supported
            for color in data.colors
        ),
        "network_color_write_supported": (
            "confirmed"
            if any(
                color.category == "network"
                and color.write_supported.value == "confirmed"
                for color in data.colors
            )
            else "unsupported"
        ),
        "network_color_write_ready": any(
            color.category == "network"
            and color.write_ready
            and not color.write_blocked
            for color in data.colors
        ),
        "speed_color_read_supported": any(
            color.category == "speed" and color.read_supported
            for color in data.colors
        ),
        "speed_color_write_supported": (
            "confirmed"
            if any(
                color.category == "speed"
                and color.write_supported.value == "confirmed"
                for color in data.colors
            )
            else "unsupported"
        ),
        "speed_color_write_ready": any(
            color.category == "speed"
            and color.write_ready
            and not color.write_blocked
            for color in data.colors
        ),
        "color_metadata_status": data.color_metadata_status,
        "color_metadata_error": data.color_metadata_error,
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
