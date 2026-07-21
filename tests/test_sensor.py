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
    EtherlightingWriteCapabilitySensor,
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
    write_status = EtherlightingWriteCapabilitySensor(
        coordinator, "controller-entry"
    )
    assert status.native_value == "online"
    assert confirmed.extra_state_attributes == {
        "brightness": "confirmed",
        "behavior": "confirmed",
        "mode": "confirmed",
    }
    assert write_status.native_value == "ready"
    assert write_status.extra_state_attributes == {
        "brightness_read_supported": True,
        "brightness_write_supported": "confirmed",
        "brightness_write_ready": True,
        "behavior_read_supported": True,
        "behavior_write_supported": "confirmed",
        "behavior_write_ready": True,
        "mode_read_supported": True,
        "mode_write_supported": "confirmed",
        "mode_write_ready": True,
        "write_block_reason": None,
        "missing_confirmed_fields": [],
    }
    assert "behavior" not in candidates.extra_state_attributes
    assert "enabled" in candidates.extra_state_attributes
    assert "payload" not in candidates.extra_state_attributes
