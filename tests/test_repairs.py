from __future__ import annotations

from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unifi_etherlighting.api.models import (
    current_capture_capabilities,
)
from custom_components.unifi_etherlighting.const import DOMAIN
from custom_components.unifi_etherlighting.coordinator import (
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
        network_application_version="11.0.0",
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
    assert (
        registry.async_get_issue(
            DOMAIN, f"{entry.entry_id}_network_version_unconfirmed"
        )
        is not None
    )
