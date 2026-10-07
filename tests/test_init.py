from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import STATE_UNAVAILABLE
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from custom_components.unifi_etherlighting.const import DOMAIN
from custom_components.unifi_etherlighting.api.errors import UniFiSchemaError
from custom_components.unifi_etherlighting.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting import (
    NetworkLabel,
    parse_etherlighting_settings_response,
)


async def test_setup_and_unload_never_write_controller(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "controller.invalid",
            "port": 443,
            "use_ssl": True,
            "verify_ssl": True,
            "username": "user",
            "password": "secret",
            "site": "site_001",
            "device_ids": ["device_001"],
        },
        options={},
        version=2,
    )
    entry.add_to_hass(hass)
    device = json.loads(
        (Path(__file__).parent / "fixtures/device_read_brightness_30.json").read_text()
    )
    settings = json.loads(
        (Path(__file__).parent / "fixtures/etherlighting_settings_read.json").read_text()
    )
    networkconf = json.loads(
        (Path(__file__).parent / "fixtures/networkconf_read.json").read_text()
    )
    parsed_settings = parse_etherlighting_settings_response(settings)
    parsed_labels = tuple(
        NetworkLabel(item["_id"], item["name"]) for item in networkconf["data"]
    )
    with (
        patch(
            "custom_components.unifi_etherlighting.async_create_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_controller.UniFiOsControllerAdapter.async_read_network_application_version",
            new=AsyncMock(return_value="10.5.62"),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_device.UniFiOsDeviceAdapter.async_read_devices",
            new=AsyncMock(return_value=(device,)),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_device.UniFiOsDeviceAdapter.async_write_device",
            new=AsyncMock(),
        ) as write,
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting.UniFiOsEtherlightingSettingsAdapter.async_read_settings",
            new=AsyncMock(return_value=parsed_settings),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting.UniFiOsEtherlightingSettingsAdapter.async_read_network_labels",
            new=AsyncMock(return_value=parsed_labels),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting.UniFiOsEtherlightingSettingsAdapter.async_write_overrides",
            new=AsyncMock(),
        ) as color_write,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert write.await_count == 0
        entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        assert len([item for item in entries if item.domain == "number"]) == 1
        assert len([item for item in entries if item.domain == "select"]) == 1
        assert len([item for item in entries if item.domain == "switch"]) == 1
        assert len([item for item in entries if item.domain == "light"]) == 10
        runtime = entry.runtime_data
        assert (
            runtime.brightness_service._write_lock
            is runtime.color_service._write_lock
        )
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert write.await_count == 0
        assert color_write.await_count == 0


async def test_v11_read_only_switch_exposes_state_without_write_paths(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "controller.invalid",
            "port": 443,
            "use_ssl": True,
            "verify_ssl": True,
            "username": "user",
            "password": "secret",
            "site": "site_001",
            "device_ids": ["device_001"],
        },
        options={},
        version=2,
    )
    entry.add_to_hass(hass)
    device = json.loads(
        (Path(__file__).parent / "fixtures/device_read_brightness_30.json").read_text()
    )
    device["ether_lighting"].pop("led_mode")

    with (
        patch(
            "custom_components.unifi_etherlighting.async_create_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_controller.UniFiOsControllerAdapter.async_read_network_application_version",
            new=AsyncMock(return_value="11.0.81"),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_device.UniFiOsDeviceAdapter.async_read_devices",
            new=AsyncMock(return_value=(device,)),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_device.UniFiOsDeviceAdapter.async_write_device",
            new=AsyncMock(),
        ) as write,
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting.UniFiOsEtherlightingSettingsAdapter.async_read_settings",
            new=AsyncMock(),
        ) as color_read,
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting.UniFiOsEtherlightingSettingsAdapter.async_write_overrides",
            new=AsyncMock(),
        ) as color_write,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        assert len([item for item in entries if item.domain == "number"]) == 1
        assert len([item for item in entries if item.domain == "select"]) == 1
        assert len([item for item in entries if item.domain == "switch"]) == 1
        assert len([item for item in entries if item.domain == "light"]) == 0
        runtime = entry.runtime_data
        assert runtime.coordinator.data.controller_status == "online"
        assert runtime.coordinator.data.contract_compatible_device_count == 0
        assert runtime.coordinator.data.read_contract_compatible_device_count == 1
        write.assert_not_awaited()
        color_read.assert_not_awaited()
        color_write.assert_not_awaited()
        assert ir.async_get(hass).async_get_issue(
            DOMAIN, f"{entry.entry_id}_write_contract_incomplete"
        ) is not None

        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_optional_color_metadata_failure_keeps_switch_controls_available(
    hass,
) -> None:
    """A color-only poll failure must not make brightness unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "controller.invalid",
            "port": 443,
            "use_ssl": True,
            "verify_ssl": True,
            "username": "user",
            "password": "secret",
            "site": "site_001",
            "device_ids": ["device_001"],
        },
        options={},
        version=2,
    )
    entry.add_to_hass(hass)
    device = json.loads(
        (Path(__file__).parent / "fixtures/device_read_brightness_30.json").read_text()
    )
    settings = json.loads(
        (Path(__file__).parent / "fixtures/etherlighting_settings_read.json").read_text()
    )
    networkconf = json.loads(
        (Path(__file__).parent / "fixtures/networkconf_read.json").read_text()
    )
    parsed_settings = parse_etherlighting_settings_response(settings)
    parsed_labels = tuple(
        NetworkLabel(item["_id"], item["name"]) for item in networkconf["data"]
    )
    with (
        patch(
            "custom_components.unifi_etherlighting.async_create_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_controller.UniFiOsControllerAdapter.async_read_network_application_version",
            new=AsyncMock(return_value="11.0.81"),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_device.UniFiOsDeviceAdapter.async_read_devices",
            new=AsyncMock(return_value=(device,)),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_device.UniFiOsDeviceAdapter.async_write_device",
            new=AsyncMock(),
        ) as write,
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting.UniFiOsEtherlightingSettingsAdapter.async_read_settings",
            new=AsyncMock(
                side_effect=(
                    UniFiSchemaError("synthetic color settings schema change"),
                    parsed_settings,
                )
            ),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting.UniFiOsEtherlightingSettingsAdapter.async_read_network_labels",
            new=AsyncMock(return_value=parsed_labels),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)
        number_entry = next(
            item
            for item in er.async_entries_for_config_entry(registry, entry.entry_id)
            if item.domain == "number"
        )
        assert hass.states.get(number_entry.entity_id).state == "30"
        assert entry.runtime_data.coordinator.last_update_success
        assert entry.runtime_data.coordinator.data.color_metadata_status == "unavailable"
        assert len(
            [
                item
                for item in er.async_entries_for_config_entry(registry, entry.entry_id)
                if item.domain == "light"
            ]
        ) == 0
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
        assert diagnostics["coordinator_last_update_success"] is True
        assert diagnostics["coordinator_refresh_error"] is None
        assert diagnostics["color_metadata_status"] == "unavailable"
        assert diagnostics["color_metadata_error"] == "schema"
        assert ir.async_get(hass).async_get_issue(
            DOMAIN, f"{entry.entry_id}_color_metadata_unavailable"
        ) is not None

        await entry.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()

        assert entry.runtime_data.coordinator.last_update_success
        assert entry.runtime_data.coordinator.data.color_metadata_status == "ready"
        assert hass.states.get(number_entry.entity_id).state == "30"
        assert len(
            [
                item
                for item in er.async_entries_for_config_entry(registry, entry.entry_id)
                if item.domain == "light"
            ]
        ) == 10
        assert ir.async_get(hass).async_get_issue(
            DOMAIN, f"{entry.entry_id}_color_metadata_unavailable"
        ) is None
        write.assert_not_awaited()

        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_configured_controls_recover_after_an_incomplete_initial_poll(hass) -> None:
    """Configured controls stay registered if a later poll restores a field."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "controller.invalid",
            "port": 443,
            "use_ssl": True,
            "verify_ssl": True,
            "username": "user",
            "password": "secret",
            "site": "site_001",
            "device_ids": ["device_001"],
        },
        options={},
        version=2,
    )
    entry.add_to_hass(hass)
    device = json.loads(
        (Path(__file__).parent / "fixtures/device_read_brightness_30.json").read_text()
    )
    incomplete_device = json.loads(json.dumps(device))
    incomplete_device["ether_lighting"].pop("brightness")
    settings = json.loads(
        (Path(__file__).parent / "fixtures/etherlighting_settings_read.json").read_text()
    )
    networkconf = json.loads(
        (Path(__file__).parent / "fixtures/networkconf_read.json").read_text()
    )
    parsed_settings = parse_etherlighting_settings_response(settings)
    parsed_labels = tuple(
        NetworkLabel(item["_id"], item["name"]) for item in networkconf["data"]
    )
    with (
        patch(
            "custom_components.unifi_etherlighting.async_create_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_controller.UniFiOsControllerAdapter.async_read_network_application_version",
            new=AsyncMock(return_value="11.0.81"),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_device.UniFiOsDeviceAdapter.async_read_devices",
            new=AsyncMock(side_effect=((incomplete_device,), (device,))),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_device.UniFiOsDeviceAdapter.async_write_device",
            new=AsyncMock(),
        ) as write,
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting.UniFiOsEtherlightingSettingsAdapter.async_read_settings",
            new=AsyncMock(return_value=parsed_settings),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting.UniFiOsEtherlightingSettingsAdapter.async_read_network_labels",
            new=AsyncMock(return_value=parsed_labels),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)
        number_entry = next(
            item
            for item in er.async_entries_for_config_entry(registry, entry.entry_id)
            if item.domain == "number"
        )
        assert hass.states.get(number_entry.entity_id).state == STATE_UNAVAILABLE

        await entry.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()

        assert entry.runtime_data.coordinator.last_update_success
        assert hass.states.get(number_entry.entity_id).state == "30"
        write.assert_not_awaited()

        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_successful_coordinator_refresh_synchronizes_repairs(hass) -> None:
    """A controller schema change between polls must surface as a Repair."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "controller.invalid",
            "port": 443,
            "use_ssl": True,
            "verify_ssl": True,
            "username": "user",
            "password": "secret",
            "site": "site_001",
            "device_ids": ["device_001"],
        },
        options={},
        version=2,
    )
    entry.add_to_hass(hass)
    device = json.loads(
        (Path(__file__).parent / "fixtures/device_read_brightness_30.json").read_text()
    )
    settings = json.loads(
        (Path(__file__).parent / "fixtures/etherlighting_settings_read.json").read_text()
    )
    networkconf = json.loads(
        (Path(__file__).parent / "fixtures/networkconf_read.json").read_text()
    )
    parsed_settings = parse_etherlighting_settings_response(settings)
    parsed_labels = tuple(
        NetworkLabel(item["_id"], item["name"]) for item in networkconf["data"]
    )
    with (
        patch(
            "custom_components.unifi_etherlighting.async_create_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_controller.UniFiOsControllerAdapter.async_read_network_application_version",
            new=AsyncMock(return_value="11.0.81"),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_device.UniFiOsDeviceAdapter.async_read_devices",
            new=AsyncMock(return_value=(device,)),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting.UniFiOsEtherlightingSettingsAdapter.async_read_settings",
            new=AsyncMock(return_value=parsed_settings),
        ),
        patch(
            "custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting.UniFiOsEtherlightingSettingsAdapter.async_read_network_labels",
            new=AsyncMock(return_value=parsed_labels),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # This is a read-only simulation of a future UniFi API schema change.
        ether_lighting = device.pop("ether_lighting")
        await entry.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()

        registry = ir.async_get(hass)
        issue_id = f"{entry.entry_id}_unsupported_combination"
        assert registry.async_get_issue(DOMAIN, issue_id) is not None

        # The same listener also removes the Repair after a later valid poll.
        device["ether_lighting"] = ether_lighting
        await entry.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()
        assert entry.runtime_data.coordinator.data.controller_status == "online"
        assert registry.async_get_issue(DOMAIN, issue_id) is None
