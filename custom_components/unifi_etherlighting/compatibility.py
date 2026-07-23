"""Runtime API-contract compatibility for UniFi Etherlighting."""

from __future__ import annotations

from collections.abc import Mapping
import re

from .const import BRIGHTNESS_MAXIMUM, BRIGHTNESS_MINIMUM

COMPATIBILITY_PROFILE = "unifi_os_network_v10"
MINIMUM_NETWORK_VERSION = (10, 5, 62)
SUPPORTED_NETWORK_MAJOR = 10

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
    """Accept compatible updates within the live-validated Network API major."""
    version = parse_network_version(value)
    return (
        version is not None
        and version[0] == SUPPORTED_NETWORK_MAJOR
        and version >= MINIMUM_NETWORK_VERSION
    )


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
    return ether_lighting.get("behavior") in _BEHAVIOR_VALUES


def mode_read_contract_is_supported(device: object) -> bool:
    """Validate the observed Etherlighting mode contract."""
    if not device_identity_contract_is_supported(device):
        return False
    assert isinstance(device, Mapping)
    ether_lighting = device["ether_lighting"]
    assert isinstance(ether_lighting, Mapping)
    return ether_lighting.get("mode") in _MODE_VALUES


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
