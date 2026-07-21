from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from custom_components.unifi_etherlighting.api.errors import (
    CapabilityNotConfirmedError,
    ReadPathNotConfirmedError,
)
from custom_components.unifi_etherlighting.api.models import (
    CapabilityEvidence,
    CapabilityState,
    ControllerCompatibilityKey,
    EvidenceLevel,
    current_capture_capabilities,
)
from custom_components.unifi_etherlighting.read_modify_write import (
    async_update_confirmed_path,
    deep_copy_payload,
    diff_json_paths,
    get_json_path,
    set_json_path,
)

FIXTURES = Path(__file__).parent / "fixtures"


class GuardedAdapter:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data = data or {}
        self.reads = 0
        self.writes = 0

    async def async_read_device(self, site_id: str, device_id: str) -> dict[str, Any]:
        self.reads += 1
        raise ReadPathNotConfirmedError("read endpoint not captured")

    async def async_write_device(
        self, site_id: str, device_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.writes += 1
        return {}

    async def async_get_capabilities(self, device: dict[str, Any]) -> set[str]:
        return set()


def payload() -> dict[str, Any]:
    return json.loads((FIXTURES / "device_put_brightness_35.json").read_text())


def test_deep_copy_and_path_operations_preserve_unknown_fields() -> None:
    original = payload()
    copied = deep_copy_payload(original)
    changed = set_json_path(original, ("ether_lighting", "brightness"), 36)
    assert copied == original
    assert original["ether_lighting"]["brightness"] == 35
    assert changed["ether_lighting"]["brightness"] == 36
    assert changed["unknown_controller_field"] == original["unknown_controller_field"]
    assert get_json_path(changed, ("ether_lighting", "brightness")) == 36
    try:
        set_json_path(original, ("ether_lighting", "missing"), True)
    except KeyError:
        pass
    else:
        raise AssertionError("Missing paths must not be created")


def test_diff_detects_multiple_and_type_changes() -> None:
    before = {"a": {"value": 1}, "list": ["x"]}
    after = {"a": {"value": "1"}, "list": ["y"], "new": True}
    changes = diff_json_paths(before, after)
    assert ("a.value", 1, "1") in changes
    assert ("list.0", "x", "y") in changes
    assert ("new", None, True) in changes


def test_candidate_capability_cannot_trigger_a_write() -> None:
    candidate = next(
        item for item in current_capture_capabilities() if item.capability == "behavior"
    )
    adapter = GuardedAdapter()
    try:
        asyncio.run(
            async_update_confirmed_path(
                adapter,
                "site",
                "device",
                ("ether_lighting", "brightness"),
                36,
                candidate,
            )
        )
    except CapabilityNotConfirmedError:
        pass
    else:
        raise AssertionError("Candidate capability must stop before reading or writing")
    assert adapter.reads == 0
    assert adapter.writes == 0


def test_missing_read_path_stops_even_a_future_confirmed_record() -> None:
    capability = CapabilityEvidence(
        "brightness",
        CapabilityState.CONFIRMED,
        EvidenceLevel.READ_VERIFIED,
        ControllerCompatibilityKey(
            "unifi_os", "<captured-version>", "USWED72", "7.4.1.16850"
        ),
        "ether_lighting.brightness",
        (35,),
        (),
    )
    adapter = GuardedAdapter()
    try:
        asyncio.run(
            async_update_confirmed_path(
                adapter,
                "site",
                "device",
                ("ether_lighting", "brightness"),
                36,
                capability,
            )
        )
    except ReadPathNotConfirmedError:
        pass
    else:
        raise AssertionError("Missing adapter read path must stop before writing")
    assert adapter.reads == 1
    assert adapter.writes == 0


def test_capture_fixtures_prove_only_observed_fields() -> None:
    brightness_request = payload()["ether_lighting"]
    brightness_response = json.loads(
        (FIXTURES / "device_put_response_brightness_35.json").read_text()
    )["data"][0]["ether_lighting"]
    behavior_request = json.loads(
        (FIXTURES / "device_put_behavior_breath.json").read_text()
    )["ether_lighting"]
    behavior_response = json.loads(
        (FIXTURES / "device_put_response_behavior_breath.json").read_text()
    )["data"][0]["ether_lighting"]
    assert brightness_request["brightness"] == brightness_response["brightness"] == 35
    assert behavior_request["behavior"] == behavior_response["behavior"] == "breath"
    assert brightness_request["mode"] == "network"
    assert brightness_request["led_mode"] == "etherlighting"
