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
    current_capture_capabilities,
    mode_capability_status,
    mode_read_is_supported,
)


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
    assert evidence["network_color"].state is CapabilityState.CANDIDATE
    assert [
        item.capability
        for item in evidence.values()
        if item.state is CapabilityState.CONFIRMED
    ] == ["brightness", "behavior", "mode"]


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


def test_runtime_compatibility_has_no_wildcards() -> None:
    exact = {
        "model": "USWED72",
        "version": "7.4.1.16850",
        "ether_lighting": {
            "brightness": 30,
            "behavior": "steady",
            "mode": "network",
        },
    }
    assert brightness_read_is_supported("10.5.62", exact)
    assert behavior_read_is_supported("10.5.62", exact)
    assert mode_read_is_supported("10.5.62", exact)
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
        ("10.5.63", "USWED72", "7.4.1.16850"),
        ("10.5.62", "USWED73", "7.4.1.16850"),
        ("10.5.62", "USWED72", "7.4.2"),
    ):
        changed = {**exact, "model": model, "version": firmware}
        assert not brightness_read_is_supported(version, changed)
        assert not behavior_read_is_supported(version, changed)
        assert not mode_read_is_supported(version, changed)
        runtime = {
            item.capability: item
            for item in capabilities_for_runtime(version, (changed,))
        }
        assert runtime["brightness"].state is CapabilityState.CANDIDATE
        assert runtime["behavior"].state is CapabilityState.CANDIDATE
        assert runtime["mode"].state is CapabilityState.CANDIDATE
