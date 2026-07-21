from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import entity_registry as er

from custom_components.unifi_etherlighting.const import DOMAIN


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
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert write.await_count == 0
        entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        assert len([item for item in entries if item.domain == "number"]) == 1
        assert len([item for item in entries if item.domain == "select"]) == 1
        assert len([item for item in entries if item.domain == "switch"]) == 1
        assert not any(item.domain == "light" for item in entries)
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert write.await_count == 0
