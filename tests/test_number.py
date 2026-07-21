from __future__ import annotations

from types import SimpleNamespace

from pytest_homeassistant_custom_component.common import MockConfigEntry

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


async def test_candidate_device_creates_no_number(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = SimpleNamespace(
        coordinator=SimpleNamespace(
            data=SimpleNamespace(
                devices=(
                    DiagnosticDevice(
                        "device_001", "USWED72", "7.4.1.16850", 30, False, False
                    ),
                )
            )
        )
    )
    added = []
    await async_setup_entry(hass, entry, lambda entities: added.extend(entities))
    assert added == []
