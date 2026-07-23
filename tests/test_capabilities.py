from copy import deepcopy
import json
from pathlib import Path

from custom_components.unifi_etherlighting.api.models import (
    CapabilityEvidence,
    CapabilityState,
    ControllerCompatibilityKey,
    EvidenceLevel,
    behavior_capability_status,
    behavior_read_is_supported,
    brightness_capability_status,
    brightness_read_is_supported,
    capabilities_for_runtime,
    color_read_is_supported,
    current_capture_capabilities,
    mode_capability_status,
    mode_read_is_supported,
)
from custom_components.unifi_etherlighting.compatibility import (
    COMPATIBILITY_PROFILE,
    compatibility_reason,
    device_write_contract_is_supported,
    network_version_is_supported,
    parse_network_version,
    runtime_contract_is_supported,
)

FIXTURES = Path(__file__).parent / "fixtures"


def device() -> dict:
    return json.loads((FIXTURES / "device_read_brightness_30.json").read_text())


def test_brightness_write_is_confirmed_for_exact_capture() -> None:
    evidence = {item.capability: item for item in current_capture_capabilities()}
    assert evidence["device_write"].evidence is EvidenceLevel.WRITE_ACCEPTED
    assert evidence["brightness"].state is CapabilityState.CONFIRMED
    assert evidence["brightness"].evidence is EvidenceLevel.REVERSIBLE
    assert evidence["behavior"].state is CapabilityState.CONFIRMED
    assert evidence["behavior"].evidence is EvidenceLevel.REVERSIBLE
    assert evidence["mode"].state is CapabilityState.CONFIRMED
    assert evidence["mode"].evidence is EvidenceLevel.REVERSIBLE
    assert evidence["enabled"].evidence is EvidenceLevel.CAPTURED
    assert evidence["port_control"].state is CapabilityState.UNSUPPORTED
    assert evidence["network_color"].state is CapabilityState.CONFIRMED
    assert evidence["network_color"].evidence is EvidenceLevel.REVERSIBLE
    assert evidence["speed_color"].state is CapabilityState.CONFIRMED
    assert evidence["speed_color"].evidence is EvidenceLevel.REVERSIBLE
    assert [
        item.capability
        for item in evidence.values()
        if item.state is CapabilityState.CONFIRMED
    ] == ["brightness", "behavior", "mode", "network_color", "speed_color"]


def test_missing_network_application_version_prevents_confirmed() -> None:
    try:
        CapabilityEvidence(
            "brightness",
            CapabilityState.CONFIRMED,
            EvidenceLevel.READ_VERIFIED,
            ControllerCompatibilityKey("unifi_os", None, "USWED72", "7.4.1.16850"),
            "ether_lighting.brightness",
            (35,),
            (),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Missing Network-Application version must block CONFIRMED")

    compatible = ControllerCompatibilityKey(
        "unifi_os", "<captured-version>", "USWED72", "7.4.1.16850"
    )
    try:
        CapabilityEvidence(
            "brightness",
            CapabilityState.CONFIRMED,
            EvidenceLevel.WRITE_ACCEPTED,
            compatible,
            "ether_lighting.brightness",
            (35,),
            (),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Write acceptance alone must block CONFIRMED")


def test_runtime_compatibility_uses_version_family_and_complete_schema() -> None:
    exact = device()
    assert brightness_read_is_supported("10.5.62", exact)
    assert behavior_read_is_supported("10.5.62", exact)
    assert mode_read_is_supported("10.5.62", exact)
    assert color_read_is_supported("10.5.62", exact)
    exact_status = brightness_capability_status("10.5.62", exact)
    assert exact_status.read_supported
    assert exact_status.write_supported is CapabilityState.CONFIRMED
    assert exact_status.write_ready
    assert behavior_capability_status(
        "10.5.62", exact
    ).write_supported is CapabilityState.CONFIRMED
    assert mode_capability_status(
        "10.5.62", exact
    ).write_supported is CapabilityState.CONFIRMED
    for version, model, firmware in (
        ("10.5.66", "USWED72", "7.4.1.16850"),
        ("10.6.0", "USWED73", "7.4.1.16850"),
        ("10.99.1", "USWED72", "7.4.2"),
    ):
        changed = {**exact, "model": model, "version": firmware}
        assert brightness_read_is_supported(version, changed)
        assert behavior_read_is_supported(version, changed)
        assert mode_read_is_supported(version, changed)
        assert color_read_is_supported(version, changed)
        runtime = {
            item.capability: item
            for item in capabilities_for_runtime(version, (changed,))
        }
        assert runtime["brightness"].state is CapabilityState.CONFIRMED
        assert runtime["brightness"].evidence is EvidenceLevel.READ_VERIFIED
        assert runtime["behavior"].state is CapabilityState.CONFIRMED
        assert runtime["mode"].state is CapabilityState.CONFIRMED
        assert runtime["network_color"].state is CapabilityState.CONFIRMED
        assert runtime["speed_color"].state is CapabilityState.CONFIRMED


def test_network_version_profile_survives_patch_and_minor_updates() -> None:
    assert COMPATIBILITY_PROFILE == "unifi_os_network_v10"
    assert parse_network_version("10.5.66") == (10, 5, 66)
    assert parse_network_version("10.6.0-beta.1") == (10, 6, 0)
    for version in ("10.5.62", "10.5.66", "10.6.0", "10.99.99"):
        assert network_version_is_supported(version)
    for version in ("10.5.61", "9.9.9", "11.0.0", "", "unknown", None):
        assert not network_version_is_supported(version)


def test_incompatible_api_generation_or_schema_fails_closed() -> None:
    current = device()
    assert runtime_contract_is_supported("10.5.66", current)
    assert compatibility_reason("10.5.66", current) == "compatible"

    for version in ("10.5.61", "11.0.0", "unknown"):
        assert not brightness_read_is_supported(version, current)
        assert not color_read_is_supported(version, current)
        assert (
            compatibility_reason(version, current)
            == "unsupported_network_api_generation"
        )

    missing_write_field = deepcopy(current)
    missing_write_field["config_network"].pop("gateway")
    assert brightness_read_is_supported("10.5.66", missing_write_field)
    assert not device_write_contract_is_supported(missing_write_field)
    assert not color_read_is_supported("10.5.66", missing_write_field)
    status = brightness_capability_status("10.5.66", missing_write_field)
    assert status.read_supported
    assert status.write_supported is CapabilityState.UNSUPPORTED
    assert not status.write_ready

    wrong_led_mode = deepcopy(current)
    wrong_led_mode["ether_lighting"]["led_mode"] = "off"
    assert not device_write_contract_is_supported(wrong_led_mode)
    assert not runtime_contract_is_supported("10.5.66", wrong_led_mode)
