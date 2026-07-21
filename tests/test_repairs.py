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
                "device_001",
                "USWED72",
                "7.4.1.16850",
                30,
                True,
                current_capture_capabilities()[1].state,
                False,
                False,
            ),
        ),
        capabilities=current_capture_capabilities(),
        last_successful_update=None,
        last_verified_write=None,
        last_error=None,
        write_capability="blocked",
        write_block_reason="confirmed_write_configuration_incomplete",
        missing_confirmed_fields=("lcm_night_mode_enabled",),
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
        is not None
    )

    unsupported = EtherlightingCoordinatorData(
        controller_status="unsupported_version_combination",
        controller_type="unifi_os",
        network_application_version="10.5.63",
        devices=(),
        capabilities=data.capabilities,
        last_successful_update=None,
        last_verified_write=None,
        last_error=None,
        write_capability="blocked",
        write_block_reason="confirmed_write_configuration_incomplete",
        missing_confirmed_fields=("lcm_night_mode_enabled",),
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
