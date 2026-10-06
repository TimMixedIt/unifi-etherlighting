from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unifi_etherlighting.const import DOMAIN, VERSION
from custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting import (
    NetworkLabel,
    parse_etherlighting_settings_response,
)
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
        FakeColorSettings(),  # type: ignore[arg-type]
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
    assert status.extra_state_attributes == {
        "runtime_integration_version": VERSION,
        "brightness": "reversible",
        "behavior": "reversible",
        "mode": "reversible",
        "network_color": "reversible",
        "speed_color": "reversible",
        "device_write": "write_accepted",
        "enabled": "captured",
        "port_control": "unknown",
        "compatibility_profile": "unifi_os_network_v10",
        "network_api_generation_supported": True,
        "contract_compatible_device_count": 1,
        "configured_device_count": 1,
        "returned_device_count": 1,
        "returned_switch_count": 1,
        "selected_device_count": 1,
        "read_contract_compatible_device_count": 1,
        "runtime_read_contract_reason": "read_contract_supported",
        "read_contract_mismatch_fields": [],
    }
    assert confirmed.extra_state_attributes == {
        "brightness": "confirmed",
        "behavior": "confirmed",
        "mode": "confirmed",
        "network_color": "confirmed",
        "speed_color": "confirmed",
    }
    assert write_status.native_value == "ready"
    assert write_status.extra_state_attributes == {
        "global_write_capability": "ready",
        "effective_write_ready": True,
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

    coordinator.data = replace(
        coordinator.data,
        devices=tuple(
            replace(
                device,
                brightness_write_ready=False,
                behavior_write_ready=False,
                mode_write_ready=False,
            )
            for device in coordinator.data.devices
        ),
        colors=(),
    )
    assert write_status.native_value == "not_ready"
    assert write_status.extra_state_attributes["global_write_capability"] == "ready"
    assert not write_status.extra_state_attributes["effective_write_ready"]

    coordinator.data = replace(coordinator.data, write_capability="blocked")
    assert write_status.native_value == "blocked"
