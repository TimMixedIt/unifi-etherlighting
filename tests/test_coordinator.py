from __future__ import annotations

import json
from pathlib import Path

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unifi_etherlighting.const import DOMAIN
from custom_components.unifi_etherlighting.coordinator import (
    EtherlightingDataUpdateCoordinator,
)


class FakeController:
    async def async_read_network_application_version(self) -> str:
        return "10.5.62"


class FakeDevices:
    def __init__(self) -> None:
        self.write_count = 0
        self.device = json.loads(
            (
                Path(__file__).parent / "fixtures/device_read_brightness_30.json"
            ).read_text()
        )

    async def async_read_devices(self, site: str):
        return (self.device,)

    async def async_write_device(self, *args, **kwargs):
        self.write_count += 1
        raise AssertionError("Polling must never write")


class FakeService:
    last_verified_write = None
    last_error_code = None

    def is_write_blocked(self, device_id: str) -> bool:
        return False


async def test_coordinator_reads_version_and_devices_without_writing(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"site": "site_001", "device_ids": ["device_001"]},
        options={},
    )
    devices = FakeDevices()
    coordinator = EtherlightingDataUpdateCoordinator(
        hass,
        entry,
        FakeController(),
        devices,
        FakeService(),  # type: ignore[arg-type]
    )
    await coordinator.async_refresh()
    assert coordinator.data.controller_status == "online"
    assert coordinator.data.network_application_version == "10.5.62"
    assert coordinator.data.devices[0].brightness == 30
    assert coordinator.data.devices[0].brightness_read_supported
    assert coordinator.data.devices[0].brightness_write_supported.value == "candidate"
    assert not coordinator.data.devices[0].brightness_write_ready
    assert any(
        item.capability == "brightness" and item.state.value == "candidate"
        for item in coordinator.data.capabilities
    )
    assert coordinator.data.write_capability == "blocked"
    assert (
        coordinator.data.write_block_reason
        == "confirmed_write_configuration_incomplete"
    )
    assert coordinator.data.missing_confirmed_fields == (
        "lcm_night_mode_enabled",
    )
    assert devices.write_count == 0
