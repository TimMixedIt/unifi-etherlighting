from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from custom_components.unifi_etherlighting import brightness as brightness_module
from custom_components.unifi_etherlighting.api.errors import (
    UniFiTransportError,
    UnsupportedCompatibilityError,
    VerificationError,
    WriteBlockedError,
    WriteCapabilityUnavailableError,
)
from custom_components.unifi_etherlighting.brightness import (
    BrightnessService,
    BrightnessWriteOutcome,
    build_brightness_write_payload,
)

FIXTURES = Path(__file__).parent / "fixtures"


def device(brightness: int = 30) -> dict[str, Any]:
    value = json.loads((FIXTURES / "device_read_brightness_30.json").read_text())
    value["ether_lighting"]["brightness"] = brightness
    return value


def complete_write_source(brightness: int = 30) -> dict[str, Any]:
    """Add only the value observed in the confirmed UI write request."""
    value = device(brightness)
    value["lcm_night_mode_enabled"] = False
    return value


class FakeAuth:
    def __init__(self) -> None:
        self.logins = 0

    async def async_ensure_authenticated(self) -> None:
        return None

    def async_invalidate(self) -> None:
        return None

    async def async_login(self) -> None:
        self.logins += 1


class FakeController:
    def __init__(self, version: str = "10.5.62") -> None:
        self.version = version

    async def async_read_network_application_version(self) -> str:
        return self.version


class FakeDevices:
    def __init__(
        self,
        reads: list[dict[str, Any]],
        *,
        write_error: Exception | None = None,
        response_brightness: int = 31,
    ) -> None:
        self.reads = reads
        self.write_error = write_error
        self.response_brightness = response_brightness
        self.writes: list[dict[str, Any]] = []

    async def async_read_device(self, site: str, device_id: str) -> dict[str, Any]:
        return deepcopy(self.reads.pop(0))

    async def async_write_device(
        self, site: str, device_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.writes.append(deepcopy(payload))
        if self.write_error:
            raise self.write_error
        return {
            "meta": {"rc": "ok"},
            "data": [{"ether_lighting": {"brightness": self.response_brightness}}],
        }


def test_payload_builder_projects_exact_ui_shape_and_preserves_original() -> None:
    original = complete_write_source()
    snapshot = deepcopy(original)
    payload = build_brightness_write_payload(original, 31)
    assert original == snapshot
    assert payload["ether_lighting"]["brightness"] == 31
    assert payload["ether_lighting"]["mode"] == "network"
    assert payload["ether_lighting"]["behavior"] == "steady"
    assert payload["ether_lighting"]["led_mode"] == "etherlighting"
    assert set(payload) == {
        "config_network",
        "ether_lighting",
        "lcm_brightness",
        "lcm_brightness_override",
        "lcm_night_mode_begins",
        "lcm_night_mode_enabled",
        "lcm_night_mode_ends",
        "lcm_orientation_override",
        "mgmt_network_id",
        "name",
        "snmp_contact",
        "snmp_location",
        "stp_priority",
    }
    assert "_id" not in payload
    assert "flowctrl_enabled" not in payload


def test_payload_builder_rejects_missing_fields_paths_and_limits() -> None:
    for mutation in ("name", "config_network", "ether_lighting"):
        current = complete_write_source()
        current.pop(mutation)
        with pytest.raises(VerificationError):
            build_brightness_write_payload(current, 31)
    current = complete_write_source()
    current["ether_lighting"].pop("brightness")
    with pytest.raises(VerificationError):
        build_brightness_write_payload(current, 31)
    for value in (0, 101, 1.5, True):
        with pytest.raises(ValueError):
            build_brightness_write_payload(
                complete_write_source(), value  # type: ignore[arg-type]
            )


def test_live_read_shape_cannot_build_complete_write_payload() -> None:
    with pytest.raises(VerificationError) as caught:
        build_brightness_write_payload(device(), 31)
    assert "top-level write fields" in str(caught.value)
    assert "lcm_night_mode_enabled" not in str(caught.value)


def test_successful_write_is_sent_once_and_read_back(monkeypatch) -> None:
    monkeypatch.setattr(brightness_module, "WRITE_CAPABILITY_ENABLED", True)
    devices = FakeDevices([complete_write_source(30), complete_write_source(31)])
    service = BrightnessService(FakeAuth(), FakeController(), devices)  # type: ignore[arg-type]
    result = asyncio.run(service.async_set_brightness("site_001", "device_001", 31))
    assert result.outcome is BrightnessWriteOutcome.APPLIED
    assert result.observed == 31
    assert len(devices.writes) == 1
    assert devices.writes[0]["ether_lighting"]["brightness"] == 31
    assert service.last_verified_write is not None


def test_other_runtime_version_blocks_before_write(monkeypatch) -> None:
    monkeypatch.setattr(brightness_module, "WRITE_CAPABILITY_ENABLED", True)
    devices = FakeDevices([complete_write_source(30)])
    service = BrightnessService(
        FakeAuth(),
        FakeController("10.5.63"),
        devices,  # type: ignore[arg-type]
    )
    with pytest.raises(UnsupportedCompatibilityError):
        asyncio.run(service.async_set_brightness("site_001", "device_001", 31))
    assert devices.writes == []


def test_timeout_is_not_retried_and_is_classified_by_read(monkeypatch) -> None:
    monkeypatch.setattr(brightness_module, "WRITE_CAPABILITY_ENABLED", True)
    devices = FakeDevices(
        [complete_write_source(30), complete_write_source(31)],
        write_error=UniFiTransportError("timeout", request_may_have_been_sent=True),
    )
    service = BrightnessService(FakeAuth(), FakeController(), devices)  # type: ignore[arg-type]
    result = asyncio.run(service.async_set_brightness("site_001", "device_001", 31))
    assert result.outcome is BrightnessWriteOutcome.APPLIED
    assert len(devices.writes) == 1


def test_unchanged_state_is_not_applied_and_mixed_state_blocks_writes(
    monkeypatch,
) -> None:
    monkeypatch.setattr(brightness_module, "WRITE_CAPABILITY_ENABLED", True)
    unchanged = FakeDevices(
        [complete_write_source(30), complete_write_source(30)],
        write_error=UniFiTransportError("timeout", request_may_have_been_sent=True),
    )
    service = BrightnessService(FakeAuth(), FakeController(), unchanged)  # type: ignore[arg-type]
    result = asyncio.run(service.async_set_brightness("site_001", "device_001", 31))
    assert result.outcome is BrightnessWriteOutcome.NOT_APPLIED

    mixed = complete_write_source(30)
    mixed["ether_lighting"]["behavior"] = "changed"
    uncertain = FakeDevices(
        [complete_write_source(30), mixed],
        write_error=UniFiTransportError("timeout", request_may_have_been_sent=True),
    )
    blocked = BrightnessService(FakeAuth(), FakeController(), uncertain)  # type: ignore[arg-type]
    result = asyncio.run(blocked.async_set_brightness("site_001", "device_001", 31))
    assert result.outcome is BrightnessWriteOutcome.INDETERMINATE
    with pytest.raises(WriteBlockedError):
        asyncio.run(blocked.async_set_brightness("site_001", "device_001", 31))
    assert len(uncertain.writes) == 1


async def test_central_write_gate_stops_before_every_network_operation(
    monkeypatch,
) -> None:
    auth = AsyncMock()
    controller = AsyncMock()
    devices = AsyncMock()
    payload_builder = AsyncMock()
    monkeypatch.setattr(
        brightness_module, "build_brightness_write_payload", payload_builder
    )
    service = BrightnessService(auth, controller, devices)

    with pytest.raises(WriteCapabilityUnavailableError) as caught:
        await service.async_set_brightness("site_001", "device_001", 31)

    assert caught.value.reason == "confirmed_write_configuration_incomplete"
    assert str(caught.value) == (
        "Etherlighting brightness writes are temporarily disabled because the "
        "complete confirmed write configuration is unavailable."
    )
    assert service.last_error_code == "confirmed_write_configuration_incomplete"
    auth.async_ensure_authenticated.assert_not_awaited()
    auth.async_login.assert_not_awaited()
    controller.async_read_network_application_version.assert_not_awaited()
    devices.async_read_device.assert_not_awaited()
    devices.async_write_device.assert_not_awaited()
    payload_builder.assert_not_awaited()
    assert not any(
        method in repr(devices.mock_calls).upper()
        for method in ("PUT", "PATCH", "POST")
    )
