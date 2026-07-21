from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from custom_components.unifi_etherlighting.api.errors import (
    UniFiTransportError,
    UnsupportedCompatibilityError,
    VerificationError,
    WriteBlockedError,
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
    original = device()
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
        current = device()
        current.pop(mutation)
        with pytest.raises(VerificationError):
            build_brightness_write_payload(current, 31)
    current = device()
    current["ether_lighting"].pop("brightness")
    with pytest.raises(VerificationError):
        build_brightness_write_payload(current, 31)
    for value in (0, 101, 1.5, True):
        with pytest.raises(ValueError):
            build_brightness_write_payload(device(), value)  # type: ignore[arg-type]


def test_successful_write_is_sent_once_and_read_back() -> None:
    devices = FakeDevices([device(30), device(31)])
    service = BrightnessService(FakeAuth(), FakeController(), devices)  # type: ignore[arg-type]
    result = asyncio.run(service.async_set_brightness("site_001", "device_001", 31))
    assert result.outcome is BrightnessWriteOutcome.APPLIED
    assert result.observed == 31
    assert len(devices.writes) == 1
    assert devices.writes[0]["ether_lighting"]["brightness"] == 31
    assert service.last_verified_write is not None


def test_other_runtime_version_blocks_before_write() -> None:
    devices = FakeDevices([device(30)])
    service = BrightnessService(
        FakeAuth(),
        FakeController("10.5.63"),
        devices,  # type: ignore[arg-type]
    )
    with pytest.raises(UnsupportedCompatibilityError):
        asyncio.run(service.async_set_brightness("site_001", "device_001", 31))
    assert devices.writes == []


def test_timeout_is_not_retried_and_is_classified_by_read() -> None:
    devices = FakeDevices(
        [device(30), device(31)],
        write_error=UniFiTransportError("timeout", request_may_have_been_sent=True),
    )
    service = BrightnessService(FakeAuth(), FakeController(), devices)  # type: ignore[arg-type]
    result = asyncio.run(service.async_set_brightness("site_001", "device_001", 31))
    assert result.outcome is BrightnessWriteOutcome.APPLIED
    assert len(devices.writes) == 1


def test_unchanged_state_is_not_applied_and_mixed_state_blocks_writes() -> None:
    unchanged = FakeDevices(
        [device(30), device(30)],
        write_error=UniFiTransportError("timeout", request_may_have_been_sent=True),
    )
    service = BrightnessService(FakeAuth(), FakeController(), unchanged)  # type: ignore[arg-type]
    result = asyncio.run(service.async_set_brightness("site_001", "device_001", 31))
    assert result.outcome is BrightnessWriteOutcome.NOT_APPLIED

    mixed = device(30)
    mixed["ether_lighting"]["behavior"] = "changed"
    uncertain = FakeDevices(
        [device(30), mixed],
        write_error=UniFiTransportError("timeout", request_may_have_been_sent=True),
    )
    blocked = BrightnessService(FakeAuth(), FakeController(), uncertain)  # type: ignore[arg-type]
    result = asyncio.run(blocked.async_set_brightness("site_001", "device_001", 31))
    assert result.outcome is BrightnessWriteOutcome.INDETERMINATE
    with pytest.raises(WriteBlockedError):
        asyncio.run(blocked.async_set_brightness("site_001", "device_001", 31))
    assert len(uncertain.writes) == 1
