from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unifi_etherlighting.api.models import CapabilityState
from custom_components.unifi_etherlighting.const import DOMAIN
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


def _read_only_number() -> EtherlightingBrightnessNumber:
    device = DiagnosticDevice(
        "device_001",
        "USWED72",
        "7.4.1.16850",
        30,
        True,
        CapabilityState.CANDIDATE,
        False,
        False,
    )
    entity = object.__new__(EtherlightingBrightnessNumber)
    entity._device_id = "device_001"
    entity.coordinator = SimpleNamespace(
        last_update_success=True,
        device=lambda device_id: device if device_id == "device_001" else None,
    )
    return entity


def test_number_keeps_read_value_and_exposes_write_lock() -> None:
    entity = _read_only_number()
    assert entity.native_value == 30
    assert entity.available
    assert entity.extra_state_attributes == {
        "brightness_read_supported": True,
        "brightness_write_supported": "candidate",
        "brightness_write_ready": False,
        "write_capability": "blocked",
        "write_block_reason": "confirmed_write_configuration_incomplete",
        "missing_confirmed_fields": ["lcm_night_mode_enabled"],
    }


async def test_direct_number_service_call_fails_before_brightness_service() -> None:
    entity = _read_only_number()
    brightness_service = AsyncMock()
    entity._runtime = SimpleNamespace(brightness_service=brightness_service)

    with pytest.raises(HomeAssistantError) as caught:
        await entity.async_set_native_value(31)

    assert str(caught.value) == (
        "Etherlighting brightness writes are temporarily disabled because the "
        "complete confirmed write configuration is unavailable."
    )
    brightness_service.async_set_brightness.assert_not_awaited()


async def test_candidate_device_creates_no_number(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = SimpleNamespace(
        coordinator=SimpleNamespace(
            data=SimpleNamespace(
                devices=(
                    DiagnosticDevice(
                        "device_001",
                        "USWED72",
                        "7.4.1.16850",
                        30,
                        False,
                        CapabilityState.UNSUPPORTED,
                        False,
                        False,
                    ),
                )
            )
        )
    )
    added = []
    await async_setup_entry(hass, entry, lambda entities: added.extend(entities))
    assert added == []
