"""Evidence and compatibility models; they do not describe unobserved API fields."""

from __future__ import annotations

from dataclasses import dataclass

try:  # Python 3.11+ (the Home Assistant target) provides StrEnum.
    from enum import StrEnum
except ImportError:  # pragma: no cover - enables local validation on older Python.
    from enum import Enum

    class StrEnum(str, Enum):
        pass


from typing import Any


class EvidenceLevel(StrEnum):
    UNKNOWN = "unknown"
    MODEL_ONLY = "model_only"
    CAPTURED = "captured"
    WRITE_ACCEPTED = "write_accepted"
    READ_VERIFIED = "read_verified"
    REVERSIBLE = "reversible"


class CapabilityState(StrEnum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    UNSUPPORTED = "unsupported"


_EVIDENCE_RANK = {
    EvidenceLevel.UNKNOWN: 0,
    EvidenceLevel.MODEL_ONLY: 1,
    EvidenceLevel.CAPTURED: 2,
    EvidenceLevel.WRITE_ACCEPTED: 3,
    EvidenceLevel.READ_VERIFIED: 4,
    EvidenceLevel.REVERSIBLE: 5,
}


def evidence_at_least(actual: EvidenceLevel, required: EvidenceLevel) -> bool:
    """Compare evidence explicitly instead of relying on string ordering."""
    return _EVIDENCE_RANK[actual] >= _EVIDENCE_RANK[required]


@dataclass(frozen=True, slots=True)
class ControllerCompatibilityKey:
    controller_type: str
    network_application_version: str | None
    device_model: str
    device_firmware: str


@dataclass(frozen=True, slots=True)
class EndpointDefinition:
    operation: str
    method: str
    path_template: str
    evidence: EvidenceLevel
    requires_csrf: bool
    response_success_path: str | None
    response_success_value: Any | None


@dataclass(frozen=True, slots=True)
class CapabilityEvidence:
    capability: str
    state: CapabilityState
    evidence: EvidenceLevel
    compatibility: ControllerCompatibilityKey
    observed_json_path: str | None
    observed_values: tuple[Any, ...]
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            self.state is CapabilityState.CONFIRMED
            and self.compatibility.network_application_version is None
        ):
            raise ValueError(
                "A missing Network-Application version cannot produce CONFIRMED"
            )
        if self.state is CapabilityState.CONFIRMED and not evidence_at_least(
            self.evidence, EvidenceLevel.READ_VERIFIED
        ):
            raise ValueError("CONFIRMED requires read-verified evidence")


CURRENT_COMPATIBILITY = ControllerCompatibilityKey(
    controller_type="unifi_os",
    network_application_version="10.5.62",
    device_model="USWED72",
    device_firmware="7.4.1.16850",
)

CONFIRMED_LOGIN_ENDPOINT = EndpointDefinition(
    operation="login",
    method="POST",
    path_template="/api/auth/login",
    evidence=EvidenceLevel.CAPTURED,
    requires_csrf=False,
    response_success_path=None,
    response_success_value=None,
)

CONFIRMED_LOGOUT_ENDPOINT = EndpointDefinition(
    operation="logout",
    method="POST",
    path_template="/api/auth/logout",
    evidence=EvidenceLevel.CAPTURED,
    requires_csrf=False,
    response_success_path=None,
    response_success_value=None,
)

CONFIRMED_CONTROLLER_VERSION_ENDPOINT = EndpointDefinition(
    operation="network_application_version_read",
    method="GET",
    path_template="/proxy/network/v2/api/info",
    evidence=EvidenceLevel.READ_VERIFIED,
    requires_csrf=False,
    response_success_path="system.version",
    response_success_value=None,
)

CONFIRMED_DEVICE_READ_ENDPOINT = EndpointDefinition(
    operation="device_read",
    method="GET",
    path_template="/proxy/network/api/s/{site}/stat/device",
    evidence=EvidenceLevel.READ_VERIFIED,
    requires_csrf=False,
    response_success_path="meta.rc",
    response_success_value="ok",
)

CONFIRMED_DEVICE_WRITE_ENDPOINT = EndpointDefinition(
    operation="device_write",
    method="PUT",
    path_template="/proxy/network/api/s/{site}/rest/device/{device}",
    evidence=EvidenceLevel.WRITE_ACCEPTED,
    requires_csrf=True,
    response_success_path="meta.rc",
    response_success_value="ok",
)


def current_capture_capabilities() -> tuple[CapabilityEvidence, ...]:
    """Evidence records for the exact live-validated compatibility tuple."""
    return (
        CapabilityEvidence(
            "device_write",
            CapabilityState.CANDIDATE,
            EvidenceLevel.WRITE_ACCEPTED,
            CURRENT_COMPATIBILITY,
            None,
            (),
            ("The endpoint is confirmed but is not a raw capability.",),
        ),
        CapabilityEvidence(
            "brightness",
            CapabilityState.CONFIRMED,
            EvidenceLevel.REVERSIBLE,
            CURRENT_COMPATIBILITY,
            "ether_lighting.brightness",
            (30, 31),
            (
                "UI write, independent read-back, reversal, and final read are confirmed.",
            ),
        ),
        CapabilityEvidence(
            "behavior",
            CapabilityState.CANDIDATE,
            EvidenceLevel.WRITE_ACCEPTED,
            CURRENT_COMPATIBILITY,
            "ether_lighting.behavior",
            ("steady", "breath"),
            (
                "Write response matched captured values; reversal/read verification is absent.",
            ),
        ),
        CapabilityEvidence(
            "mode",
            CapabilityState.CANDIDATE,
            EvidenceLevel.CAPTURED,
            CURRENT_COMPATIBILITY,
            "ether_lighting.mode",
            ("network",),
            ("Observed as an unchanged accompanying value, not a tested mode change.",),
        ),
        CapabilityEvidence(
            "enabled",
            CapabilityState.CANDIDATE,
            EvidenceLevel.CAPTURED,
            CURRENT_COMPATIBILITY,
            "ether_lighting.led_mode",
            ("etherlighting",),
            (
                "Observed as an unchanged accompanying value, not a tested enable change.",
            ),
        ),
        CapabilityEvidence(
            "network_color",
            CapabilityState.CANDIDATE,
            EvidenceLevel.CAPTURED,
            CURRENT_COMPATIBILITY,
            None,
            (),
            ("Network color is outside the confirmed Device brightness contract.",),
        ),
        CapabilityEvidence(
            "port_control",
            CapabilityState.UNSUPPORTED,
            EvidenceLevel.UNKNOWN,
            CURRENT_COMPATIBILITY,
            None,
            (),
            ("Out of scope: no port-specific controller capability is evidenced.",),
        ),
    )


def compatibility_key_for_device(
    network_application_version: str, device: dict[str, Any]
) -> ControllerCompatibilityKey:
    """Build a key only from fields present in the confirmed runtime reads."""
    return ControllerCompatibilityKey(
        controller_type="unifi_os",
        network_application_version=network_application_version,
        device_model=str(device.get("model", "")),
        device_firmware=str(device.get("version", "")),
    )


def brightness_is_confirmed(
    network_application_version: str, device: dict[str, Any]
) -> bool:
    """Release brightness only for the one exact validated tuple and field path."""
    ether_lighting = device.get("ether_lighting")
    return (
        compatibility_key_for_device(network_application_version, device)
        == CURRENT_COMPATIBILITY
        and isinstance(ether_lighting, dict)
        and isinstance(ether_lighting.get("brightness"), int)
        and not isinstance(ether_lighting.get("brightness"), bool)
    )


def capabilities_for_runtime(
    network_application_version: str, devices: tuple[dict[str, Any], ...]
) -> tuple[CapabilityEvidence, ...]:
    """Downgrade brightness unless at least one selected Device matches exactly."""
    capabilities = list(current_capture_capabilities())
    if any(
        brightness_is_confirmed(network_application_version, device)
        for device in devices
    ):
        return tuple(capabilities)
    brightness_index = next(
        index
        for index, capability in enumerate(capabilities)
        if capability.capability == "brightness"
    )
    confirmed = capabilities[brightness_index]
    capabilities[brightness_index] = CapabilityEvidence(
        capability="brightness",
        state=CapabilityState.CANDIDATE,
        evidence=EvidenceLevel.CAPTURED,
        compatibility=ControllerCompatibilityKey(
            "unifi_os", network_application_version or None, "unknown", "unknown"
        ),
        observed_json_path=confirmed.observed_json_path,
        observed_values=(),
        notes=("Runtime compatibility does not match the exact confirmed tuple.",),
    )
    return tuple(capabilities)
