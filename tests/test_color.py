from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.unifi_etherlighting.api.adapters.unifi_os_etherlighting import (
    ColorMapping,
    UniFiOsEtherlightingSettingsAdapter,
    parse_etherlighting_settings_response,
)
from custom_components.unifi_etherlighting.api.errors import UniFiSchemaError
from custom_components.unifi_etherlighting.brightness import BrightnessWriteOutcome
from custom_components.unifi_etherlighting.color import EtherlightingColorService
from custom_components.unifi_etherlighting.coordinator import DiagnosticColor
from custom_components.unifi_etherlighting.light import (
    EtherlightingColorLight,
    _hex_to_rgb,
    _rgb_to_hex,
)
from custom_components.unifi_etherlighting.api.models import CapabilityState

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_confirmed_setting_schema_and_effective_colors() -> None:
    settings = parse_etherlighting_settings_response(
        fixture("etherlighting_settings_read.json")
    )
    assert settings.effective_color("network", "network_001") == "0544FF"
    assert settings.effective_color("network", "network_002") == "FF00EE"
    assert settings.effective_color("speed", "FE") == "FFC105"
    assert len(settings.speed_defaults) == 9
    assert settings.speed_overrides == ()


@pytest.mark.parametrize(
    "body",
    [
        [],
        {},
        {"meta": {"rc": "error"}, "data": []},
        {"meta": {"rc": "ok"}, "data": {}},
        {"meta": {"rc": "ok"}, "data": []},
        {
            "meta": {"rc": "ok"},
            "data": [
                {
                    "key": "ether_lighting",
                    "network_defaults": [],
                    "network_overrides": [],
                    "speed_defaults": [],
                    "speed_overrides": [{"key": "FE", "raw_color_hex": "bad"}],
                }
            ],
        },
    ],
)
def test_setting_schema_mismatches_fail_closed(body: object) -> None:
    with pytest.raises(UniFiSchemaError):
        parse_etherlighting_settings_response(body)


async def test_settings_adapter_uses_only_confirmed_paths_and_full_overrides() -> None:
    body = fixture("etherlighting_settings_read.json")
    client = SimpleNamespace(
        async_request_json_value=AsyncMock(return_value=body),
        async_request_json=AsyncMock(return_value=body),
    )
    adapter = UniFiOsEtherlightingSettingsAdapter(client)

    settings = await adapter.async_read_settings("site/name")
    client.async_request_json_value.assert_awaited_once_with(
        "GET",
        "/proxy/network/api/s/site%2Fname/get/setting",
        retry_auth_once=True,
    )
    await adapter.async_write_overrides(
        "site/name",
        network_overrides=settings.network_overrides,
        speed_overrides=(ColorMapping("FE", "FEC105"),),
    )
    call = client.async_request_json.await_args
    assert call.args == (
        "POST",
        "/proxy/network/api/s/site%2Fname/set/setting/ether_lighting",
    )
    assert call.kwargs["requires_csrf"] is True
    assert call.kwargs["payload"] == {
        "key": "ether_lighting",
        "network_overrides": [
            {"raw_color_hex": item.raw_color_hex, "key": item.key}
            for item in settings.network_overrides
        ],
        "speed_overrides": [{"raw_color_hex": "FEC105", "key": "FE"}],
    }


async def test_network_labels_use_confirmed_read_path() -> None:
    client = SimpleNamespace(
        async_request_json=AsyncMock(return_value=fixture("networkconf_read.json"))
    )
    adapter = UniFiOsEtherlightingSettingsAdapter(client)
    labels = await adapter.async_read_network_labels("site_001")
    assert labels[0].key == "network_001"
    assert labels[0].name == "Network 1"
    client.async_request_json.assert_awaited_once_with(
        "GET",
        "/proxy/network/api/s/site_001/rest/networkconf",
        retry_auth_once=True,
    )


def _setting_with_speed_color(value: str) -> object:
    body = deepcopy(fixture("etherlighting_settings_read.json"))
    setting = body["data"][0]
    setting["speed_overrides"] = [{"raw_color_hex": value, "key": "FE"}]
    return parse_etherlighting_settings_response(body)


async def test_color_service_writes_one_override_and_reads_it_back() -> None:
    before = parse_etherlighting_settings_response(
        fixture("etherlighting_settings_read.json")
    )
    after = _setting_with_speed_color("FEC105")
    auth = SimpleNamespace(async_ensure_authenticated=AsyncMock())
    controller = SimpleNamespace(
        async_read_network_application_version=AsyncMock(return_value="10.5.62")
    )
    device = fixture("device_read_brightness_30.json")
    devices = SimpleNamespace(
        async_read_device=AsyncMock(return_value=device),
        async_write_device=AsyncMock(
            return_value={"meta": {"rc": "ok"}, "data": [device]}
        ),
    )
    settings = SimpleNamespace(
        async_read_settings=AsyncMock(side_effect=[before, after]),
        async_write_overrides=AsyncMock(return_value=after),
    )
    service = EtherlightingColorService(auth, controller, devices, settings)

    result = await service.async_set_color(
        "site_001", "device_001", "speed", "FE", "FEC105"
    )

    assert result.outcome is BrightnessWriteOutcome.APPLIED
    assert result.before == "FFC105"
    assert result.observed == "FEC105"
    kwargs = settings.async_write_overrides.await_args.kwargs
    assert kwargs["network_overrides"] == before.network_overrides
    assert kwargs["speed_overrides"] == (ColorMapping("FE", "FEC105"),)
    devices.async_write_device.assert_awaited_once()
    assert (
        devices.async_write_device.await_args.args[2]["ether_lighting"]
        == device["ether_lighting"]
    )
    settings.async_read_settings.assert_awaited()


def test_rgb_conversion_is_strict() -> None:
    assert _hex_to_rgb("0544FF") == (5, 68, 255)
    assert _rgb_to_hex((5, 68, 255)) == "0544FF"
    with pytest.raises(HomeAssistantError):
        _rgb_to_hex((1, 2))
    with pytest.raises(HomeAssistantError):
        _rgb_to_hex((1, 2, 300))


def _diagnostic_color() -> DiagnosticColor:
    return DiagnosticColor(
        category="speed",
        key="FE",
        name="FE",
        raw_color_hex="FFC105",
        witness_device_id="device_001",
        read_supported=True,
        write_supported=CapabilityState.CONFIRMED,
        write_ready=True,
        write_blocked=False,
    )


async def test_light_entity_uses_verified_color_service(monkeypatch) -> None:
    color = _diagnostic_color()
    coordinator = SimpleNamespace(
        last_update_success=True,
        color=lambda category, key: color,
        async_request_refresh=AsyncMock(),
        data=SimpleNamespace(),
    )
    service = SimpleNamespace(
        async_set_color=AsyncMock(
            return_value=SimpleNamespace(outcome=BrightnessWriteOutcome.APPLIED)
        )
    )
    entity = object.__new__(EtherlightingColorLight)
    entity._category = "speed"
    entity._key = "FE"
    entity._entry = SimpleNamespace(data={"site": "site_001"})
    entity._runtime = SimpleNamespace(color_service=service)
    entity.coordinator = coordinator
    entity.hass = object()
    sync_repairs = AsyncMock()
    monkeypatch.setattr(
        "custom_components.unifi_etherlighting.light.async_sync_repairs",
        sync_repairs,
    )

    await entity.async_turn_on(rgb_color=(254, 193, 5))

    service.async_set_color.assert_awaited_once_with(
        "site_001", "device_001", "speed", "FE", "FEC105"
    )
    coordinator.async_request_refresh.assert_awaited_once()
    assert entity.rgb_color == (255, 193, 5)


async def test_light_rejects_power_and_brightness_actions() -> None:
    entity = object.__new__(EtherlightingColorLight)
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_off()
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_on(brightness=100)
