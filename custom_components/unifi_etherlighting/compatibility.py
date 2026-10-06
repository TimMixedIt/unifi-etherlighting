"""Runtime API-contract compatibility for UniFi Etherlighting."""

from __future__ import annotations

from collections.abc import Mapping
import re

from .const import BRIGHTNESS_MAXIMUM, BRIGHTNESS_MINIMUM

COMPATIBILITY_PROFILE = "unifi_os_network_v10"
MINIMUM_NETWORK_VERSION = (10, 5, 62)
MINIMUM_NETWORK_VERSION_TEXT = ".".join(str(part) for part in MINIMUM_NETWORK_VERSION)

CONFIG_NETWORK_WRITE_FIELDS = (
    "type",
    "ip",
    "netmask",
    "gateway",
    "dns1",
    "dns2",
    "dnssuffix",
    "bonding_enabled",
)
ETHER_LIGHTING_WRITE_FIELDS = ("mode", "brightness", "behavior", "led_mode")
TOP_LEVEL_WRITE_FIELDS = (
    "lcm_brightness",
    "lcm_brightness_override",
    "lcm_night_mode_begins",
    "lcm_night_mode_ends",
    "lcm_orientation_override",
    "mgmt_network_id",
    "name",
    "snmp_contact",
    "snmp_location",
    "stp_priority",
)
UI_DEFAULTED_TOP_LEVEL_FIELDS = {"lcm_night_mode_enabled": False}

_NETWORK_VERSION = re.compile(
    r"^(?P<major>[0-9]+)\.(?P<minor>[0-9]+)\.(?P<patch>[0-9]+)"
    r"(?:[-+.][0-9A-Za-z.-]+)?$"
)
_BEHAVIOR_VALUES = frozenset({"steady", "breath"})
_MODE_VALUES = frozenset({"network", "speed"})

# These labels describe contract *fields*, never controller-provided values.  They
# are deliberately shared with diagnostics so that a future caller cannot turn a
# diagnostic field into a raw Device-value echo.
READ_CONTRACT_MISMATCH_LABELS = frozenset(
    {
        "device",
        "type",
        "_id",
        "model",
        "version",
        "ether_lighting",
        "ether_lighting.brightness",
        "ether_lighting.behavior",
        "ether_lighting.mode",
    }
)


def _is_one_of(value: object, allowed: frozenset[str]) -> bool:
    """Membership test that tolerates unhashable controller values."""
    return isinstance(value, str) and value in allowed


def parse_network_version(value: object) -> tuple[int, int, int] | None:
    """Parse the numeric API generation without retaining a version suffix."""
    if not isinstance(value, str):
        return None
    match = _NETWORK_VERSION.fullmatch(value.strip())
    if match is None:
        return None
    return tuple(
        int(match.group(component)) for component in ("major", "minor", "patch")
    )


def network_version_is_supported(value: object) -> bool:
    """Accept the live-validated Network version and every newer release.

    There is deliberately no upper bound: a Network major bump does not by
    itself change the Etherlighting API. The real gate is the complete runtime
    Device/settings schema check plus the pre-write read and post-write
    read-back verification, all of which still fail closed on a changed API.
    """
    version = parse_network_version(value)
    return version is not None and version >= MINIMUM_NETWORK_VERSION


def device_identity_contract_is_supported(device: object) -> bool:
    """Recognize a real Etherlighting switch without model/firmware pinning."""
    if not isinstance(device, Mapping):
        return False
    return (
        device.get("type") == "usw"
        and isinstance(device.get("_id"), str)
        and bool(device["_id"])
        and isinstance(device.get("model"), str)
        and bool(device["model"])
        and isinstance(device.get("version"), str)
        and bool(device["version"])
        and isinstance(device.get("ether_lighting"), Mapping)
    )


def brightness_read_contract_is_supported(device: object) -> bool:
    """Validate the observed Brightness field by type and UI bounds."""
    if not device_identity_contract_is_supported(device):
        return False
    assert isinstance(device, Mapping)
    ether_lighting = device["ether_lighting"]
    assert isinstance(ether_lighting, Mapping)
    brightness = ether_lighting.get("brightness")
    return (
        isinstance(brightness, int)
        and not isinstance(brightness, bool)
        and BRIGHTNESS_MINIMUM <= brightness <= BRIGHTNESS_MAXIMUM
    )


def behavior_read_contract_is_supported(device: object) -> bool:
    """Validate the observed Breathing behavior contract."""
    if not device_identity_contract_is_supported(device):
        return False
    assert isinstance(device, Mapping)
    ether_lighting = device["ether_lighting"]
    assert isinstance(ether_lighting, Mapping)
    return _is_one_of(ether_lighting.get("behavior"), _BEHAVIOR_VALUES)


def mode_read_contract_is_supported(device: object) -> bool:
    """Validate the observed Etherlighting mode contract."""
    if not device_identity_contract_is_supported(device):
        return False
    assert isinstance(device, Mapping)
    ether_lighting = device["ether_lighting"]
    assert isinstance(ether_lighting, Mapping)
    return _is_one_of(ether_lighting.get("mode"), _MODE_VALUES)


def device_read_contract_mismatches(device: object) -> tuple[str, ...]:
    """Name failed read-contract checks using fixed, non-controller labels.

    This is intentionally narrower than :func:`device_contract_mismatches`:
    missing write-only fields must not obscure why a selected Device cannot be
    read.  An empty result means all three supported Device controls have a
    valid read contract; it does not make any write claim.
    """
    if not isinstance(device, Mapping):
        return ("device",)
    found: list[str] = []

    def flag(label: str) -> None:
        if label not in found:
            found.append(label)

    if device.get("type") != "usw":
        flag("type")
    for field in ("_id", "model", "version"):
        value = device.get(field)
        if not isinstance(value, str) or not value:
            flag(field)

    ether_lighting = device.get("ether_lighting")
    if not isinstance(ether_lighting, Mapping):
        flag("ether_lighting")
        return tuple(found)

    brightness = ether_lighting.get("brightness")
    if not (
        isinstance(brightness, int)
        and not isinstance(brightness, bool)
        and BRIGHTNESS_MINIMUM <= brightness <= BRIGHTNESS_MAXIMUM
    ):
        flag("ether_lighting.brightness")
    if not _is_one_of(ether_lighting.get("behavior"), _BEHAVIOR_VALUES):
        flag("ether_lighting.behavior")
    if not _is_one_of(ether_lighting.get("mode"), _MODE_VALUES):
        flag("ether_lighting.mode")
    return tuple(found)


def device_write_contract_is_supported(device: object) -> bool:
    """Require every field needed to reproduce the confirmed UI Device write."""
    if not (
        brightness_read_contract_is_supported(device)
        and behavior_read_contract_is_supported(device)
        and mode_read_contract_is_supported(device)
    ):
        return False
    assert isinstance(device, Mapping)
    ether_lighting = device["ether_lighting"]
    config_network = device.get("config_network")
    if not isinstance(ether_lighting, Mapping) or not isinstance(
        config_network, Mapping
    ):
        return False
    if ether_lighting.get("led_mode") != "etherlighting":
        return False
    if not all(field in ether_lighting for field in ETHER_LIGHTING_WRITE_FIELDS):
        return False
    if not all(field in config_network for field in CONFIG_NETWORK_WRITE_FIELDS):
        return False
    if not all(field in device for field in TOP_LEVEL_WRITE_FIELDS):
        return False
    return all(
        field not in device or isinstance(device[field], bool)
        for field in UI_DEFAULTED_TOP_LEVEL_FIELDS
    )


def device_contract_mismatches(device: object) -> tuple[str, ...]:
    """Name every failed Device contract check using fixed labels only.

    Mirrors device_write_contract_is_supported(): the result is empty exactly
    when that function returns True. Labels are built from this module's field
    constants, never from controller values, so they are safe to log and show.
    """
    if not isinstance(device, Mapping):
        return ("device",)
    found: list[str] = []

    def flag(label: str) -> None:
        if label not in found:
            found.append(label)

    if device.get("type") != "usw":
        flag("type")
    for field in ("_id", "model", "version"):
        value = device.get(field)
        if not isinstance(value, str) or not value:
            flag(field)

    ether_lighting = device.get("ether_lighting")
    if not isinstance(ether_lighting, Mapping):
        flag("ether_lighting")
    else:
        brightness = ether_lighting.get("brightness")
        if not (
            isinstance(brightness, int)
            and not isinstance(brightness, bool)
            and BRIGHTNESS_MINIMUM <= brightness <= BRIGHTNESS_MAXIMUM
        ):
            flag("ether_lighting.brightness")
        if not _is_one_of(ether_lighting.get("behavior"), _BEHAVIOR_VALUES):
            flag("ether_lighting.behavior")
        if not _is_one_of(ether_lighting.get("mode"), _MODE_VALUES):
            flag("ether_lighting.mode")
        if ether_lighting.get("led_mode") != "etherlighting":
            flag("ether_lighting.led_mode")
        for field in ETHER_LIGHTING_WRITE_FIELDS:
            if field not in ether_lighting:
                flag(f"ether_lighting.{field}")

    config_network = device.get("config_network")
    if not isinstance(config_network, Mapping):
        flag("config_network")
    else:
        for field in CONFIG_NETWORK_WRITE_FIELDS:
            if field not in config_network:
                flag(f"config_network.{field}")

    for field in TOP_LEVEL_WRITE_FIELDS:
        if field not in device:
            flag(field)
    for field in UI_DEFAULTED_TOP_LEVEL_FIELDS:
        if field in device and not isinstance(device[field], bool):
            flag(field)
    return tuple(found)


def runtime_contract_is_supported(
    network_application_version: object, device: object
) -> bool:
    """Return whether the complete non-mutating runtime contract is compatible."""
    return network_version_is_supported(
        network_application_version
    ) and device_write_contract_is_supported(device)


def compatibility_reason(
    network_application_version: object, device: object
) -> str:
    """Return an allowlisted compatibility reason without controller values."""
    if not network_version_is_supported(network_application_version):
        return "unsupported_network_api_generation"
    if not device_identity_contract_is_supported(device):
        return "device_identity_contract_mismatch"
    if not device_write_contract_is_supported(device):
        return "device_write_contract_mismatch"
    return "compatible"
