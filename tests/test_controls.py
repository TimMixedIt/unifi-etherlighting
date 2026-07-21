from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unifi_etherlighting import select as select_module
from custom_components.unifi_etherlighting import switch as switch_module
from custom_components.unifi_etherlighting.api.models import CapabilityState
from custom_components.unifi_etherlighting.brightness import BrightnessWriteOutcome
from custom_components.unifi_etherlighting.const import CONF_SITE, DOMAIN
from custom_components.unifi_etherlighting.coordinator import DiagnosticDevice
from custom_components.unifi_etherlighting.select import EtherlightingModeSelect
from custom_components.unifi_etherlighting.switch import EtherlightingBreathingSwitch


def ready_device(
    *, behavior: str = "steady", mode: str = "network"
) -> DiagnosticDevice:
    return DiagnosticDevice(
        identifier="device_001",
        model="USWED72",
        firmware="7.4.1.16850",
        brightness=30,
        brightness_read_supported=True,
        brightness_write_supported=CapabilityState.CONFIRMED,
        brightness_write_ready=True,
        behavior=behavior,
        behavior_read_supported=True,
        behavior_write_supported=CapabilityState.CONFIRMED,
        behavior_write_ready=True,
        mode=mode,
        mode_read_supported=True,
        mode_write_supported=CapabilityState.CONFIRMED,
        mode_write_ready=True,
        write_blocked=False,
    )


def coordinator(device: DiagnosticDevice) -> SimpleNamespace:
    return SimpleNamespace(
        last_update_success=True,
        device=lambda device_id: device if device_id == "device_001" else None,
        async_request_refresh=AsyncMock(),
        data=SimpleNamespace(),
    )


def test_switch_and_select_expose_confirmed_read_state() -> None:
    breathing = object.__new__(EtherlightingBreathingSwitch)
    breathing._device_id = "device_001"
    breathing.coordinator = coordinator(ready_device())
    assert breathing.is_on is False
    assert breathing.available
    assert breathing.extra_state_attributes == {
        "behavior_read_supported": True,
        "behavior_write_supported": "confirmed",
        "behavior_write_ready": True,
    }

    mode = object.__new__(EtherlightingModeSelect)
    mode._device_id = "device_001"
    mode.coordinator = coordinator(ready_device())
    assert mode.current_option == "network"
    assert mode.options == ["speed", "network"]
    assert mode.available
    assert mode.extra_state_attributes == {
        "mode_read_supported": True,
        "mode_write_supported": "confirmed",
        "mode_write_ready": True,
    }


@pytest.mark.parametrize(
    ("turn_method", "behavior"),
    (("async_turn_on", "breath"), ("async_turn_off", "steady")),
)
async def test_switch_uses_verified_behavior_service(
    monkeypatch, turn_method: str, behavior: str
) -> None:
    entity = object.__new__(EtherlightingBreathingSwitch)
    entity._device_id = "device_001"
    entity.coordinator = coordinator(ready_device())
    service = AsyncMock()
    service.async_set_behavior.return_value = SimpleNamespace(
        outcome=BrightnessWriteOutcome.APPLIED
    )
    entity._runtime = SimpleNamespace(brightness_service=service)
    entity._entry = SimpleNamespace(data={CONF_SITE: "site_001"})
    entity.hass = object()
    sync_repairs = AsyncMock()
    monkeypatch.setattr(switch_module, "async_sync_repairs", sync_repairs)

    await getattr(entity, turn_method)()

    service.async_set_behavior.assert_awaited_once_with(
        "site_001", "device_001", behavior
    )
    entity.coordinator.async_request_refresh.assert_awaited_once()
    sync_repairs.assert_awaited_once()


async def test_select_uses_verified_mode_service(monkeypatch) -> None:
    entity = object.__new__(EtherlightingModeSelect)
    entity._device_id = "device_001"
    entity.coordinator = coordinator(ready_device())
    service = AsyncMock()
    service.async_set_mode.return_value = SimpleNamespace(
        outcome=BrightnessWriteOutcome.APPLIED
    )
    entity._runtime = SimpleNamespace(brightness_service=service)
    entity._entry = SimpleNamespace(data={CONF_SITE: "site_001"})
    entity.hass = object()
    sync_repairs = AsyncMock()
    monkeypatch.setattr(select_module, "async_sync_repairs", sync_repairs)

    await entity.async_select_option("speed")

    service.async_set_mode.assert_awaited_once_with(
        "site_001", "device_001", "speed"
    )
    entity.coordinator.async_request_refresh.assert_awaited_once()
    sync_repairs.assert_awaited_once()


async def test_select_rejects_unconfirmed_option_before_service_call() -> None:
    entity = object.__new__(EtherlightingModeSelect)
    entity._runtime = SimpleNamespace(brightness_service=AsyncMock())
    with pytest.raises(HomeAssistantError):
        await entity.async_select_option("color")
    entity._runtime.brightness_service.async_set_mode.assert_not_awaited()


async def test_unsupported_device_creates_no_control_entities(hass) -> None:
    unsupported = ready_device()
    unsupported = replace(
        unsupported,
        behavior_read_supported=False,
        mode_read_supported=False,
    )
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = SimpleNamespace(
        coordinator=SimpleNamespace(data=SimpleNamespace(devices=(unsupported,)))
    )
    switches: list[object] = []
    selects: list[object] = []
    await switch_module.async_setup_entry(
        hass, entry, lambda entities: switches.extend(entities)
    )
    await select_module.async_setup_entry(
        hass, entry, lambda entities: selects.extend(entities)
    )
    assert switches == []
    assert selects == []
