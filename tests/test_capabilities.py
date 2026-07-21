from custom_components.unifi_etherlighting.api.models import (
    CapabilityEvidence,
    CapabilityState,
    ControllerCompatibilityKey,
    EvidenceLevel,
    brightness_is_confirmed,
    capabilities_for_runtime,
    current_capture_capabilities,
)


def test_only_brightness_is_confirmed_for_exact_capture() -> None:
    evidence = {item.capability: item for item in current_capture_capabilities()}
    assert evidence["device_write"].evidence is EvidenceLevel.WRITE_ACCEPTED
    assert evidence["brightness"].state is CapabilityState.CONFIRMED
    assert evidence["brightness"].evidence is EvidenceLevel.REVERSIBLE
    assert evidence["behavior"].state is CapabilityState.CANDIDATE
    assert evidence["behavior"].evidence is EvidenceLevel.WRITE_ACCEPTED
    assert evidence["mode"].evidence is EvidenceLevel.CAPTURED
    assert evidence["enabled"].evidence is EvidenceLevel.CAPTURED
    assert evidence["port_control"].state is CapabilityState.UNSUPPORTED
    assert evidence["network_color"].state is CapabilityState.CANDIDATE
    assert [
        item.capability
        for item in evidence.values()
        if item.state is CapabilityState.CONFIRMED
    ] == ["brightness"]


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
        "ether_lighting": {"brightness": 30},
    }
    assert brightness_is_confirmed("10.5.62", exact)
    for version, model, firmware in (
        ("10.5.63", "USWED72", "7.4.1.16850"),
        ("10.5.62", "USWED73", "7.4.1.16850"),
        ("10.5.62", "USWED72", "7.4.2"),
    ):
        changed = {**exact, "model": model, "version": firmware}
        assert not brightness_is_confirmed(version, changed)
        runtime = {
            item.capability: item
            for item in capabilities_for_runtime(version, (changed,))
        }
        assert runtime["brightness"].state is CapabilityState.CANDIDATE
