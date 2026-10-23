"""Bounded repair issues for runtime compatibility and verified writes."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .compatibility import (
    MINIMUM_NETWORK_VERSION_TEXT,
    network_version_is_supported,
    parse_network_version,
)
from .coordinator import EtherlightingCoordinatorData
from .const import (
    CONTROLLER_STATUS_UNSUPPORTED,
    DOMAIN,
    WRITE_CAPABILITY_BLOCKED_STATE,
)

# Refresh error categories that settle whether the credentials work, and
# whether the API schema matched. A transport or other failure settles
# neither, so those Repairs keep their last known state instead of clearing.
_AUTH_ERRORS = frozenset({"authentication", "permission"})
_AUTH_SETTLING_ERRORS = _AUTH_ERRORS | {"schema"}
_SCHEMA_SETTLING_ERRORS = frozenset({"schema"})


def _sync_issue(
    hass: HomeAssistant,
    entry: ConfigEntry,
    suffix: str,
    active: bool,
    translation_key: str,
    translation_placeholders: dict[str, str] | None = None,
) -> None:
    issue_id = f"{entry.entry_id}_{suffix}"
    if active:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)


async def async_sync_repairs(
    hass: HomeAssistant,
    entry: ConfigEntry,
    data: EtherlightingCoordinatorData,
    refresh_error: str | None = None,
) -> None:
    """Synchronize safe issues without exposing hosts, credentials, or Device IDs.

    ``refresh_error`` is the coordinator's allowlisted category of the most
    recent failed refresh, or ``None`` after a successful one.
    """
    _sync_issue(
        hass,
        entry,
        "write_configuration_incomplete",
        data.write_capability == WRITE_CAPABILITY_BLOCKED_STATE,
        "write_configuration_incomplete",
    )
    detected = parse_network_version(data.network_application_version)
    _sync_issue(
        hass,
        entry,
        "network_version_unconfirmed",
        not network_version_is_supported(data.network_application_version),
        "network_version_unconfirmed",
        {
            # Only a successfully parsed numeric version is echoed back.
            "version": ".".join(map(str, detected)) if detected else "unknown",
            "minimum": MINIMUM_NETWORK_VERSION_TEXT,
        },
    )
    _sync_issue(
        hass,
        entry,
        "unsupported_combination",
        data.controller_status == CONTROLLER_STATUS_UNSUPPORTED
        and data.runtime_read_contract_reason != "selected_devices_not_returned",
        "unsupported_combination",
    )
    _sync_issue(
        hass,
        entry,
        "write_contract_incomplete",
        data.read_contract_compatible_device_count
        > data.contract_compatible_device_count,
        "write_contract_incomplete",
    )
    _sync_issue(
        hass,
        entry,
        "selected_devices_not_returned",
        data.runtime_read_contract_reason == "selected_devices_not_returned",
        "selected_devices_not_returned",
    )
    _sync_issue(
        hass,
        entry,
        "etherlighting_field_missing",
        any(device.brightness is None for device in data.devices),
        "etherlighting_field_missing",
    )
    _sync_issue(
        hass,
        entry,
        "color_metadata_unavailable",
        data.color_metadata_status == "unavailable",
        "color_metadata_unavailable",
    )
    error = data.last_error or ""
    if refresh_error is None or refresh_error in _AUTH_SETTLING_ERRORS:
        _sync_issue(
            hass,
            entry,
            "authentication_failed",
            refresh_error in _AUTH_ERRORS,
            "authentication_failed",
        )
    _sync_issue(
        hass,
        entry,
        "write_unverified",
        error == "write_verification_failed",
        "write_unverified",
    )
    if refresh_error is None or refresh_error in _SCHEMA_SETTLING_ERRORS:
        _sync_issue(
            hass,
            entry,
            "api_schema_mismatch",
            refresh_error == "schema",
            "api_schema_mismatch",
        )
    _sync_issue(
        hass,
        entry,
        "write_blocked",
        any(device.write_blocked for device in data.devices)
        or any(color.write_blocked for color in data.colors),
        "write_blocked",
    )
