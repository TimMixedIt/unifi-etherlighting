from __future__ import annotations

from dataclasses import replace

from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unifi_etherlighting.api.models import (
    CapabilityState,
    current_capture_capabilities,
)
from custom_components.unifi_etherlighting.const import DOMAIN
from custom_components.unifi_etherlighting.coordinator import (
    DiagnosticColor,
    DiagnosticDevice,
    EtherlightingCoordinatorData,
)
from custom_components.unifi_etherlighting.repairs import async_sync_repairs


async def test_repairs_are_idempotent_and_old_read_issue_is_removed(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    data = EtherlightingCoordinatorData(
        controller_status="online",
        controller_type="unifi_os",
        network_application_version="10.5.62",
        devices=(
            DiagnosticDevice(
                identifier="device_001",
                model="USWED72",
                firmware="7.4.1.16850",
                brightness=30,
                brightness_read_supported=True,
                brightness_write_supported=current_capture_capabilities()[1].state,
                brightness_write_ready=True,
                behavior="steady",
                behavior_read_supported=True,
                behavior_write_supported=current_capture_capabilities()[2].state,
                behavior_write_ready=True,
                mode="network",
                mode_read_supported=True,
                mode_write_supported=current_capture_capabilities()[3].state,
                mode_write_ready=True,
                write_blocked=False,
            ),
        ),
        colors=(),
        capabilities=current_capture_capabilities(),
        last_successful_update=None,
        last_verified_write=None,
        last_error=None,
        write_capability="ready",
        write_block_reason=None,
        missing_confirmed_fields=(),
    )
    await async_sync_repairs(hass, entry, data)
    await async_sync_repairs(hass, entry, data)
    registry = ir.async_get(hass)
    assert (
        registry.async_get_issue(DOMAIN, f"{entry.entry_id}_read_path_unconfirmed")
        is None
    )
    assert (
        registry.async_get_issue(DOMAIN, f"{entry.entry_id}_unsupported_combination")
        is None
    )
    assert (
        registry.async_get_issue(
            DOMAIN, f"{entry.entry_id}_write_configuration_incomplete"
        )
        is None
    )

    unsupported = EtherlightingCoordinatorData(
        controller_status="unsupported_version_combination",
        controller_type="unifi_os",
        network_application_version="10.5.61",
        devices=(),
        colors=(),
        capabilities=data.capabilities,
        last_successful_update=None,
        last_verified_write=None,
        last_error=None,
        write_capability="ready",
        write_block_reason=None,
        missing_confirmed_fields=(),
    )
    await async_sync_repairs(hass, entry, unsupported)
    assert (
        registry.async_get_issue(DOMAIN, f"{entry.entry_id}_unsupported_combination")
        is not None
    )
    version_issue = registry.async_get_issue(
        DOMAIN, f"{entry.entry_id}_network_version_unconfirmed"
    )
    assert version_issue is not None
    assert version_issue.translation_placeholders == {
        "version": "10.5.61",
        "minimum": "10.5.62",
    }

    unreadable = replace(unsupported, network_application_version="not a version")
    await async_sync_repairs(hass, entry, unreadable)
    version_issue = registry.async_get_issue(
        DOMAIN, f"{entry.entry_id}_network_version_unconfirmed"
    )
    assert version_issue is not None
    assert version_issue.translation_placeholders["version"] == "unknown"

    newer_major = replace(data, network_application_version="11.0.0")
    await async_sync_repairs(hass, entry, newer_major)
    assert (
        registry.async_get_issue(
            DOMAIN, f"{entry.entry_id}_network_version_unconfirmed"
        )
        is None
    )


async def test_selected_devices_not_returned_uses_a_distinct_repair(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    base = EtherlightingCoordinatorData(
        controller_status="unsupported_version_combination",
        controller_type="unifi_os",
        network_application_version="11.0.81",
        devices=(),
        colors=(),
        capabilities=current_capture_capabilities(),
        last_successful_update=None,
        last_verified_write=None,
        last_error=None,
        write_capability="ready",
        write_block_reason=None,
        missing_confirmed_fields=(),
    )
    registry = ir.async_get(hass)

    await async_sync_repairs(hass, entry, base)
    assert (
        registry.async_get_issue(DOMAIN, f"{entry.entry_id}_unsupported_combination")
        is not None
    )

    stale_selection = replace(
        base,
        controller_status="online",
        configured_device_count=2,
        returned_device_count=2,
        returned_switch_count=1,
        selected_device_count=1,
        read_contract_compatible_device_count=1,
        runtime_read_contract_reason="selected_devices_not_returned",
    )
    await async_sync_repairs(hass, entry, stale_selection)

    assert (
        registry.async_get_issue(DOMAIN, f"{entry.entry_id}_unsupported_combination")
        is None
    )
    issue = registry.async_get_issue(
        DOMAIN, f"{entry.entry_id}_selected_devices_not_returned"
    )
    assert issue is not None
    assert issue.translation_key == "selected_devices_not_returned"
    assert issue.translation_placeholders is None

    await async_sync_repairs(
        hass,
        entry,
        replace(
            stale_selection,
            controller_status="online",
            selected_device_count=1,
            runtime_read_contract_reason="read_contract_supported",
        ),
    )
    assert (
        registry.async_get_issue(
            DOMAIN, f"{entry.entry_id}_selected_devices_not_returned"
        )
        is None
    )


async def test_read_only_device_creates_and_clears_write_contract_repair(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    data = EtherlightingCoordinatorData(
        controller_status="online",
        controller_type="unifi_os",
        network_application_version="11.0.81",
        devices=(),
        colors=(),
        capabilities=current_capture_capabilities(),
        last_successful_update=None,
        last_verified_write=None,
        last_error=None,
        write_capability="ready",
        write_block_reason=None,
        missing_confirmed_fields=(),
        configured_device_count=1,
        selected_device_count=1,
        read_contract_compatible_device_count=1,
        contract_compatible_device_count=0,
        runtime_read_contract_reason="read_contract_supported",
    )
    registry = ir.async_get(hass)

    await async_sync_repairs(hass, entry, data)
    issue = registry.async_get_issue(
        DOMAIN, f"{entry.entry_id}_write_contract_incomplete"
    )
    assert issue is not None
    assert issue.translation_key == "write_contract_incomplete"

    await async_sync_repairs(
        hass, entry, replace(data, contract_compatible_device_count=1)
    )
    assert (
        registry.async_get_issue(
            DOMAIN, f"{entry.entry_id}_write_contract_incomplete"
        )
        is None
    )


async def test_write_repairs_track_only_indeterminate_results(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    base = EtherlightingCoordinatorData(
        controller_status="online",
        controller_type="unifi_os",
        network_application_version="10.5.66",
        devices=(),
        colors=(),
        capabilities=current_capture_capabilities(),
        last_successful_update=None,
        last_verified_write=None,
        last_error="write_not_applied",
        write_capability="ready",
        write_block_reason=None,
        missing_confirmed_fields=(),
    )
    registry = ir.async_get(hass)

    await async_sync_repairs(hass, entry, base)
    assert (
        registry.async_get_issue(
            DOMAIN, f"{entry.entry_id}_write_unverified"
        )
        is None
    )
    assert (
        registry.async_get_issue(DOMAIN, f"{entry.entry_id}_write_blocked")
        is None
    )

    indeterminate = replace(
        base,
        last_error="write_verification_failed",
        colors=(
            DiagnosticColor(
                category="speed",
                key="FE",
                name="FE",
                raw_color_hex="FFC105",
                witness_device_id="device_001",
                read_supported=True,
                write_supported=CapabilityState.CONFIRMED,
                write_ready=True,
                write_blocked=True,
            ),
        ),
    )
    await async_sync_repairs(hass, entry, indeterminate)
    assert (
        registry.async_get_issue(
            DOMAIN, f"{entry.entry_id}_write_unverified"
        )
        is not None
    )
    assert (
        registry.async_get_issue(DOMAIN, f"{entry.entry_id}_write_blocked")
        is not None
    )

    await async_sync_repairs(hass, entry, replace(base, last_error=None))
    assert (
        registry.async_get_issue(
            DOMAIN, f"{entry.entry_id}_write_unverified"
        )
        is None
    )
    assert (
        registry.async_get_issue(DOMAIN, f"{entry.entry_id}_write_blocked")
        is None
    )
