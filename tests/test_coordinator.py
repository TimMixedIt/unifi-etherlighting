from __future__ import annotations

import json
from pathlib import Path

from homeassistant.exceptions import ConfigEntryAuthFailed
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unifi_etherlighting.api.errors import (
    UniFiAuthenticationError,
    UniFiResponseError,
    UniFiSchemaError,
)
from custom_components.unifi_etherlighting.const import DOMAIN
from custom_components.unifi_etherlighting.coordinator import (
    EtherlightingDataUpdateCoordinator,
)
from custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting import (
    NetworkLabel,
    parse_etherlighting_settings_response,
)


class FakeController:
    async def async_read_network_application_version(self) -> str:
        return "10.5.62"


class Network11Controller:
    async def async_read_network_application_version(self) -> str:
        return "11.0.81"


class FailingAuthController:
    async def async_read_network_application_version(self) -> str:
        raise UniFiAuthenticationError("synthetic authentication failure")


class FakeDevices:
    def __init__(self) -> None:
        self.write_count = 0
        self.additional_devices: tuple[dict[str, object], ...] = ()
        self.device = json.loads(
            (
                Path(__file__).parent / "fixtures/device_read_brightness_30.json"
            ).read_text()
        )

    async def async_read_devices(self, site: str):
        return (self.device, *self.additional_devices)

    async def async_write_device(self, *args, **kwargs):
        self.write_count += 1
        raise AssertionError("Polling must never write")


class FakeService:
    last_verified_write = None
    last_error_code = None

    def is_write_blocked(self, device_id: str) -> bool:
        return False


class FakeColorSettings:
    async def async_read_settings(self, site: str):
        return parse_etherlighting_settings_response(
            json.loads(
                (
                    Path(__file__).parent
                    / "fixtures/etherlighting_settings_read.json"
                ).read_text()
            )
        )

    async def async_read_network_labels(self, site: str):
        data = json.loads(
            (Path(__file__).parent / "fixtures/networkconf_read.json").read_text()
        )["data"]
        return tuple(NetworkLabel(item["_id"], item["name"]) for item in data)


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
        FakeColorSettings(),  # type: ignore[arg-type]
        FakeService(),  # type: ignore[arg-type]
    )
    await coordinator.async_refresh()
    assert coordinator.data.controller_status == "online"
    assert coordinator.data.network_application_version == "10.5.62"
    assert coordinator.data.devices[0].brightness == 30
    assert coordinator.data.devices[0].brightness_read_supported
    assert coordinator.data.devices[0].brightness_write_supported.value == "confirmed"
    assert coordinator.data.devices[0].brightness_write_ready
    assert coordinator.data.devices[0].behavior == "steady"
    assert coordinator.data.devices[0].behavior_read_supported
    assert coordinator.data.devices[0].behavior_write_supported.value == "confirmed"
    assert coordinator.data.devices[0].behavior_write_ready
    assert coordinator.data.devices[0].mode == "network"
    assert coordinator.data.devices[0].mode_read_supported
    assert coordinator.data.devices[0].mode_write_supported.value == "confirmed"
    assert coordinator.data.devices[0].mode_write_ready
    assert len(coordinator.data.colors) == 10
    assert len(
        [color for color in coordinator.data.colors if color.category == "network"]
    ) == 5
    assert len(
        [color for color in coordinator.data.colors if color.category == "speed"]
    ) == 5
    assert coordinator.data.colors[0].raw_color_hex == "0544FF"
    assert any(
        item.capability == "brightness" and item.state.value == "confirmed"
        for item in coordinator.data.capabilities
    )
    assert any(
        item.capability == "behavior" and item.state.value == "confirmed"
        for item in coordinator.data.capabilities
    )
    assert any(
        item.capability == "mode" and item.state.value == "confirmed"
        for item in coordinator.data.capabilities
    )
    assert any(
        item.capability == "network_color" and item.state.value == "confirmed"
        for item in coordinator.data.capabilities
    )
    assert any(
        item.capability == "speed_color" and item.state.value == "confirmed"
        for item in coordinator.data.capabilities
    )
    assert coordinator.data.write_capability == "ready"
    assert coordinator.data.write_block_reason is None
    assert coordinator.data.missing_confirmed_fields == ()
    assert coordinator.data.configured_device_count == 1
    assert coordinator.data.returned_device_count == 1
    assert coordinator.data.returned_switch_count == 1
    assert coordinator.data.selected_device_count == 1
    assert coordinator.data.read_contract_compatible_device_count == 1
    assert coordinator.data.runtime_read_contract_reason == "read_contract_supported"
    assert coordinator.data.read_contract_mismatch_fields == ()
    assert devices.write_count == 0


@pytest.mark.parametrize(
    "failing_method",
    ("async_read_settings", "async_read_network_labels"),
)
async def test_optional_color_metadata_failure_keeps_device_controls_live(
    hass, monkeypatch, failing_method: str
) -> None:
    """A color-only read failure must not make current Device data stale."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"site": "site_001", "device_ids": ["device_001"]},
        options={},
    )
    devices = FakeDevices()
    color_settings = FakeColorSettings()

    async def fail_optional_color_read(*args, **kwargs):
        raise UniFiSchemaError("synthetic optional color schema change")

    monkeypatch.setattr(color_settings, failing_method, fail_optional_color_read)
    coordinator = EtherlightingDataUpdateCoordinator(
        hass,
        entry,
        FakeController(),
        devices,
        FakeService(),  # type: ignore[arg-type]
        color_settings,  # type: ignore[arg-type]
        FakeService(),  # type: ignore[arg-type]
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.last_refresh_error is None
    assert coordinator.data.controller_status == "online"
    assert coordinator.data.devices[0].brightness == 30
    assert coordinator.data.devices[0].brightness_read_supported
    assert coordinator.data.devices[0].brightness_write_ready
    assert coordinator.data.colors == ()
    assert coordinator.data.color_metadata_status == "unavailable"
    assert coordinator.data.color_metadata_error == "schema"
    assert devices.write_count == 0


async def test_core_device_read_failure_remains_a_failed_refresh(hass) -> None:
    """Only optional color metadata is isolated from the core Device read."""

    class FailingDevices(FakeDevices):
        async def async_read_devices(self, site: str):
            raise UniFiResponseError("synthetic Device response failure")

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"site": "site_001", "device_ids": ["device_001"]},
        options={},
    )
    coordinator = EtherlightingDataUpdateCoordinator(
        hass,
        entry,
        FakeController(),
        FailingDevices(),
        FakeService(),  # type: ignore[arg-type]
        FakeColorSettings(),  # type: ignore[arg-type]
        FakeService(),  # type: ignore[arg-type]
    )

    await coordinator.async_refresh()

    assert not coordinator.last_update_success
    assert coordinator.last_refresh_error == "response"


async def test_coordinator_keeps_v11_read_only_switch_observable(hass) -> None:
    """A missing write-only field preserves state reads, never a write path."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"site": "site_001", "device_ids": ["device_001"]},
        options={},
    )
    devices = FakeDevices()
    devices.device["ether_lighting"].pop("led_mode")
    coordinator = EtherlightingDataUpdateCoordinator(
        hass,
        entry,
        Network11Controller(),
        devices,
        FakeService(),  # type: ignore[arg-type]
        FakeColorSettings(),  # type: ignore[arg-type]
        FakeService(),  # type: ignore[arg-type]
    )

    await coordinator.async_refresh()

    assert coordinator.data.controller_status == "online"
    assert coordinator.data.network_application_version == "11.0.81"
    assert coordinator.data.read_contract_compatible_device_count == 1
    assert coordinator.data.contract_compatible_device_count == 0
    assert coordinator.data.runtime_read_contract_reason == "read_contract_supported"
    device = coordinator.data.devices[0]
    assert device.brightness == 30
    assert device.brightness_read_supported
    assert not device.brightness_write_ready
    assert device.behavior_read_supported
    assert not device.behavior_write_ready
    assert device.mode_read_supported
    assert not device.mode_write_ready
    assert coordinator.data.colors == ()
    assert devices.write_count == 0


async def test_coordinator_reports_bounded_read_contract_failure(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"site": "site_001", "device_ids": ["device_001"]},
        options={},
    )
    devices = FakeDevices()
    devices.device["ether_lighting"].pop("brightness")
    devices.device["ether_lighting"]["behavior"] = []
    devices.device["ether_lighting"]["mode"] = "unexpected"
    coordinator = EtherlightingDataUpdateCoordinator(
        hass,
        entry,
        FakeController(),
        devices,
        FakeService(),  # type: ignore[arg-type]
        FakeColorSettings(),  # type: ignore[arg-type]
        FakeService(),  # type: ignore[arg-type]
    )

    await coordinator.async_refresh()

    assert coordinator.data.controller_status == "unsupported_version_combination"
    assert coordinator.data.network_api_generation_supported
    assert coordinator.data.configured_device_count == 1
    assert coordinator.data.returned_device_count == 1
    assert coordinator.data.returned_switch_count == 1
    assert coordinator.data.selected_device_count == 1
    assert coordinator.data.read_contract_compatible_device_count == 0
    assert (
        coordinator.data.runtime_read_contract_reason
        == "selected_devices_read_contract_mismatch"
    )
    assert coordinator.data.read_contract_mismatch_fields == (
        "ether_lighting.brightness",
        "ether_lighting.behavior",
        "ether_lighting.mode",
    )
    assert devices.write_count == 0


async def test_coordinator_reports_selected_device_not_returned(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"site": "site_001", "device_ids": ["different_device"]},
        options={},
    )
    devices = FakeDevices()
    devices.additional_devices = ({"_id": "ap_001", "type": "uap"},)
    coordinator = EtherlightingDataUpdateCoordinator(
        hass,
        entry,
        FakeController(),
        devices,
        FakeService(),  # type: ignore[arg-type]
        FakeColorSettings(),  # type: ignore[arg-type]
        FakeService(),  # type: ignore[arg-type]
    )

    await coordinator.async_refresh()

    assert coordinator.data.controller_status == "selected_devices_not_returned"
    assert coordinator.data.network_api_generation_supported
    assert coordinator.data.configured_device_count == 1
    assert coordinator.data.returned_device_count == 2
    assert coordinator.data.returned_switch_count == 1
    assert coordinator.data.selected_device_count == 0
    assert coordinator.data.read_contract_compatible_device_count == 0
    assert (
        coordinator.data.runtime_read_contract_reason
        == "selected_devices_not_returned"
    )
    assert coordinator.data.read_contract_mismatch_fields == ()
    assert devices.write_count == 0


async def test_coordinator_reports_partially_missing_selected_devices(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"site": "site_001", "device_ids": ["device_001", "missing_device"]},
        options={},
    )
    devices = FakeDevices()
    coordinator = EtherlightingDataUpdateCoordinator(
        hass,
        entry,
        FakeController(),
        devices,
        FakeService(),  # type: ignore[arg-type]
        FakeColorSettings(),  # type: ignore[arg-type]
        FakeService(),  # type: ignore[arg-type]
    )

    await coordinator.async_refresh()

    # The returned Device remains usable, but Home Assistant must surface the
    # missing saved identifier instead of silently treating the selection as
    # fully healthy.
    assert coordinator.data.controller_status == "online"
    assert coordinator.data.configured_device_count == 2
    assert coordinator.data.selected_device_count == 1
    assert coordinator.data.read_contract_compatible_device_count == 1
    assert (
        coordinator.data.runtime_read_contract_reason
        == "selected_devices_not_returned"
    )
    assert devices.write_count == 0


async def test_coordinator_authentication_failure_starts_reauth(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"site": "site_001", "device_ids": ["device_001"]},
        options={},
    )
    coordinator = EtherlightingDataUpdateCoordinator(
        hass,
        entry,
        FailingAuthController(),  # type: ignore[arg-type]
        FakeDevices(),
        FakeService(),  # type: ignore[arg-type]
        FakeColorSettings(),  # type: ignore[arg-type]
        FakeService(),  # type: ignore[arg-type]
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
