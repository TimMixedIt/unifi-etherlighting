"""Bounded repair issues for runtime compatibility and verified writes."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .compatibility import network_version_is_supported
from .coordinator import EtherlightingCoordinatorData
from .const import (
    CONTROLLER_STATUS_UNSUPPORTED,
    DOMAIN,
    WRITE_CAPABILITY_BLOCKED_STATE,
)


def _sync_issue(
    hass: HomeAssistant,
    entry: ConfigEntry,
    suffix: str,
    active: bool,
    translation_key: str,
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
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)


async def async_sync_repairs(
    hass: HomeAssistant, entry: ConfigEntry, data: EtherlightingCoordinatorData
) -> None:
    """Synchronize safe issues without exposing hosts, credentials, or Device IDs."""
    _sync_issue(
        hass,
        entry,
        "write_configuration_incomplete",
        data.write_capability == WRITE_CAPABILITY_BLOCKED_STATE,
        "write_configuration_incomplete",
    )
    _sync_issue(
        hass,
        entry,
        "network_version_unconfirmed",
        not network_version_is_supported(data.network_application_version),
        "network_version_unconfirmed",
    )
    _sync_issue(
        hass,
        entry,
        "unsupported_combination",
        data.controller_status == CONTROLLER_STATUS_UNSUPPORTED,
        "unsupported_combination",
    )
    _sync_issue(
        hass,
        entry,
        "etherlighting_field_missing",
        any(device.brightness is None for device in data.devices),
        "etherlighting_field_missing",
    )
    error = data.last_error or ""
    _sync_issue(
        hass,
        entry,
        "authentication_failed",
        error in {"UniFiAuthenticationError", "UniFiPermissionError"},
        "authentication_failed",
    )
    _sync_issue(
        hass,
        entry,
        "write_unverified",
        bool(error)
        and ("Verification" in error or error == "write_verification_failed"),
        "write_unverified",
    )
    _sync_issue(
        hass,
        entry,
        "api_schema_mismatch",
        error == "UniFiSchemaError",
        "api_schema_mismatch",
    )
    _sync_issue(
        hass,
        entry,
        "write_blocked",
        any(device.write_blocked for device in data.devices),
        "write_blocked",
    )
