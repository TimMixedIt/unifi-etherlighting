from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unifi_etherlighting import number as number_module
from custom_components.unifi_etherlighting.api.models import CapabilityState
from custom_components.unifi_etherlighting.brightness import BrightnessWriteOutcome
from custom_components.unifi_etherlighting.const import CONF_SITE, DOMAIN
from custom_components.unifi_etherlighting.coordinator import DiagnosticDevice
from custom_components.unifi_etherlighting.number import (
    EtherlightingBrightnessNumber,
    async_setup_entry,
)


def test_number_uses_confirmed_ui_constraints() -> None:
    entity = object.__new__(EtherlightingBrightnessNumber)
    assert entity.native_min_value == 1
    assert entity.native_max_value == 100
    assert entity.native_step == 1
    assert entity.native_unit_of_measurement == "%"


def _ready_number() -> EtherlightingBrightnessNumber:
    device = DiagnosticDevice(
        identifier="device_001",
        model="USWED72",
        firmware="7.4.1.16850",
        brightness=30,
        brightness_read_supported=True,
        brightness_write_supported=CapabilityState.CONFIRMED,
        brightness_write_ready=True,
        behavior="steady",
        behavior_read_supported=True,
        behavior_write_supported=CapabilityState.CONFIRMED,
        behavior_write_ready=True,
        mode="network",
        mode_read_supported=True,
        mode_write_supported=CapabilityState.CONFIRMED,
        mode_write_ready=True,
        write_blocked=False,
    )
    entity = object.__new__(EtherlightingBrightnessNumber)
    entity._device_id = "device_001"
    entity.coordinator = SimpleNamespace(
        last_update_success=True,
        device=lambda device_id: device if device_id == "device_001" else None,
        async_request_refresh=AsyncMock(),
        data=SimpleNamespace(),
    )
    return entity


def test_number_keeps_read_value_and_exposes_write_readiness() -> None:
    entity = _ready_number()
    assert entity.native_value == 30
    assert entity.available
    assert entity.extra_state_attributes == {
        "brightness_read_supported": True,
        "brightness_write_supported": "confirmed",
        "brightness_write_ready": True,
        "write_capability": "ready",
        "write_block_reason": None,
        "missing_confirmed_fields": [],
    }


async def test_direct_number_service_call_uses_verified_brightness_service(
    monkeypatch,
) -> None:
    entity = _ready_number()
    brightness_service = AsyncMock()
    brightness_service.async_set_brightness.return_value = SimpleNamespace(
        outcome=BrightnessWriteOutcome.APPLIED
    )
    entity._runtime = SimpleNamespace(brightness_service=brightness_service)
    entity._entry = SimpleNamespace(data={CONF_SITE: "site_001"})
    entity.hass = object()
    sync_repairs = AsyncMock()
    monkeypatch.setattr(number_module, "async_sync_repairs", sync_repairs)

    await entity.async_set_native_value(31)

    brightness_service.async_set_brightness.assert_awaited_once_with(
        "site_001", "device_001", 31
    )
    entity.coordinator.async_request_refresh.assert_awaited_once()
    sync_repairs.assert_awaited_once()


async def test_candidate_device_creates_no_number(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = SimpleNamespace(
        coordinator=SimpleNamespace(
            data=SimpleNamespace(
                devices=(
                    DiagnosticDevice(
                        identifier="device_001",
                        model="USWED72",
                        firmware="7.4.1.16850",
                        brightness=30,
                        brightness_read_supported=False,
                        brightness_write_supported=CapabilityState.UNSUPPORTED,
                        brightness_write_ready=False,
                        behavior=None,
                        behavior_read_supported=False,
                        behavior_write_supported=CapabilityState.UNSUPPORTED,
                        behavior_write_ready=False,
                        mode=None,
                        mode_read_supported=False,
                        mode_write_supported=CapabilityState.UNSUPPORTED,
                        mode_write_ready=False,
                        write_blocked=False,
                    ),
                )
            )
        )
    )
    added = []
    await async_setup_entry(hass, entry, lambda entities: added.extend(entities))
    assert added == []
