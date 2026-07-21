from __future__ import annotations

import json
from pathlib import Path

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unifi_etherlighting.const import DOMAIN
from custom_components.unifi_etherlighting.coordinator import (
    EtherlightingDataUpdateCoordinator,
)
from custom_components.unifi_etherlighting.sensor import (
    EtherlightingCapabilitySensor,
    EtherlightingStatusSensor,
)


class FakeController:
    async def async_read_network_application_version(self) -> str:
        return "10.5.62"


class FakeDevices:
    async def async_read_devices(self, site: str):
        return (
            json.loads(
                (
                    Path(__file__).parent / "fixtures/device_read_brightness_30.json"
                ).read_text()
            ),
        )


class FakeService:
    last_verified_write = None
    last_error_code = None

    def is_write_blocked(self, device_id: str) -> bool:
        return False


async def test_diagnostic_sensor_states_are_bounded(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"site": "site_001", "device_ids": ["device_001"]},
        options={},
    )
    coordinator = EtherlightingDataUpdateCoordinator(
        hass,
        entry,
        FakeController(),
        FakeDevices(),
        FakeService(),  # type: ignore[arg-type]
    )
    await coordinator.async_refresh()
    status = EtherlightingStatusSensor(coordinator, "controller-entry")
    confirmed = EtherlightingCapabilitySensor(
        coordinator, "controller-entry", "confirmed"
    )
    candidates = EtherlightingCapabilitySensor(
        coordinator, "controller-entry", "candidate"
    )
    assert status.native_value == "online"
    assert confirmed.extra_state_attributes == {"brightness": "confirmed"}
    assert "behavior" in candidates.extra_state_attributes
    assert "payload" not in candidates.extra_state_attributes
