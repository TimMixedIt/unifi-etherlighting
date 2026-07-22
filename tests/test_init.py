from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import entity_registry as er

from custom_components.unifi_etherlighting.const import DOMAIN
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
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert write.await_count == 0
        assert color_write.await_count == 0
