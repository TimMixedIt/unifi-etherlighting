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
LCM_WRITE_FIELDS = (
    "lcm_brightness",
    "lcm_brightness_override",
    "lcm_night_mode_begins",
    "lcm_night_mode_ends",
    "lcm_orientation_override",
)
TOP_LEVEL_WRITE_FIELDS = LCM_WRITE_FIELDS + (
    "mgmt_network_id",
    "name",
    "snmp_contact",
    "snmp_location",
    "stp_priority",
)
UI_DEFAULTED_TOP_LEVEL_FIELDS = {"lcm_night_mode_enabled": False}


def network_write_fields(config_network: Mapping) -> tuple[str, ...]:
    """Preserve present DHCP companion fields; static fields remain required."""
    if config_network.get("type") == "dhcp":
        return tuple(
            field
            for field in CONFIG_NETWORK_WRITE_FIELDS
            if field in ("type", "bonding_enabled") or field in config_network
        )
    return CONFIG_NETWORK_WRITE_FIELDS


def top_level_write_fields(device: Mapping) -> tuple[str, ...]:
    """Omit the LCD group only when the entire group is absent."""
    if any(field in device for field in LCM_WRITE_FIELDS) or any(
        field in device for field in UI_DEFAULTED_TOP_LEVEL_FIELDS
    ):
        return TOP_LEVEL_WRITE_FIELDS
    return tuple(
        field for field in TOP_LEVEL_WRITE_FIELDS if field not in LCM_WRITE_FIELDS
    )


_NETWORK_VERSION = re.compile(
    r"^(?P<major>[0-9]+)\.(?P<minor>[0-9]+)\.(?P<patch>[0-9]+)"
    r"(?:[-+.][0-9A-Za-z.-]+)?$"
)
BEHAVIOR_VALUES = frozenset({"steady", "breath"})
MODE_VALUES = frozenset({"network", "speed"})
# Read-only Device fields that a verified write must leave unchanged; see the
# sanitized Network UI form-initialization capture.
STABLE_DEVICE_FIELDS = (
    "type",
    "model",
    "version",
    "lcm_brightness",
    "lcm_brightness_override",
    "flowctrl_enabled",
    "dot1x_portctrl_enabled",
    "jumboframe_enabled",
    "stp_version",
    "stp_priority",
)

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


def _brightness_is_valid(value: object) -> bool:
    """Accept only an integer Brightness within the UI bounds."""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and BRIGHTNESS_MINIMUM <= value <= BRIGHTNESS_MAXIMUM
    )


def _identified_ether_lighting(device: object) -> Mapping | None:
    """Return the ether_lighting object of a recognized switch, else None."""
    if not device_identity_contract_is_supported(device):
        return None
    assert isinstance(device, Mapping)
    return device["ether_lighting"]


def brightness_read_contract_is_supported(device: object) -> bool:
    """Validate the observed Brightness field by type and UI bounds."""
    ether_lighting = _identified_ether_lighting(device)
    return ether_lighting is not None and _brightness_is_valid(
        ether_lighting.get("brightness")
    )


def behavior_read_contract_is_supported(device: object) -> bool:
    """Validate the observed Breathing behavior contract."""
    ether_lighting = _identified_ether_lighting(device)
    return ether_lighting is not None and _is_one_of(
        ether_lighting.get("behavior"), BEHAVIOR_VALUES
    )


def mode_read_contract_is_supported(device: object) -> bool:
    """Validate the observed Etherlighting mode contract."""
    ether_lighting = _identified_ether_lighting(device)
    return ether_lighting is not None and _is_one_of(
        ether_lighting.get("mode"), MODE_VALUES
    )


def _read_mismatches(device: Mapping) -> dict[str, None]:
    """Collect failed read-contract labels in check order, without duplicates."""
    found: dict[str, None] = {}
    if device.get("type") != "usw":
        found["type"] = None
    for field in ("_id", "model", "version"):
        value = device.get(field)
        if not isinstance(value, str) or not value:
            found[field] = None

    ether_lighting = device.get("ether_lighting")
    if not isinstance(ether_lighting, Mapping):
        found["ether_lighting"] = None
        return found
    if not _brightness_is_valid(ether_lighting.get("brightness")):
        found["ether_lighting.brightness"] = None
    if not _is_one_of(ether_lighting.get("behavior"), BEHAVIOR_VALUES):
        found["ether_lighting.behavior"] = None
    if not _is_one_of(ether_lighting.get("mode"), MODE_VALUES):
        found["ether_lighting.mode"] = None
    return found


def device_read_contract_mismatches(device: object) -> tuple[str, ...]:
    """Name failed read-contract checks using fixed, non-controller labels.

    This is intentionally narrower than :func:`device_contract_mismatches`:
    missing write-only fields must not obscure why a selected Device cannot be
    read.  An empty result means all three supported Device controls have a
    valid read contract; it does not make any write claim.
    """
    if not isinstance(device, Mapping):
        return ("device",)
    return tuple(_read_mismatches(device))


def device_read_contract_is_supported(device: object) -> bool:
    """Return whether the bounded Etherlighting state can be read safely.

    This deliberately makes no claim about Device writes.  In particular, a
    Device that no longer supplies an old write-only companion field can still
    expose a valid brightness, behavior, and mode state.
    """
    return not device_read_contract_mismatches(device)


def device_write_contract_is_supported(device: object) -> bool:
    """Require every field needed to reproduce the confirmed UI Device write.

    Complete sources retain the established contract. Only the sparse DHCP
    shape needs additional evidence (a boolean ``bonding_enabled``) before
    its companion fields may be omitted; see device_contract_mismatches().
    """
    return not device_contract_mismatches(device)


def device_contract_mismatches(device: object) -> tuple[str, ...]:
    """Name every failed Device contract check using fixed labels only.

    device_write_contract_is_supported() is defined as "no mismatches", so
    the two can never disagree. Labels are built from this module's field
    constants, never from controller values, so they are safe to log and show.
    """
    if not isinstance(device, Mapping):
        return ("device",)
    found = _read_mismatches(device)

    ether_lighting = device.get("ether_lighting")
    if isinstance(ether_lighting, Mapping):
        if ether_lighting.get("led_mode") != "etherlighting":
            found["ether_lighting.led_mode"] = None
        for field in ETHER_LIGHTING_WRITE_FIELDS:
            if field not in ether_lighting:
                found[f"ether_lighting.{field}"] = None

    config_network = device.get("config_network")
    if not isinstance(config_network, Mapping):
        found["config_network"] = None
    else:
        if not all(field in config_network for field in CONFIG_NETWORK_WRITE_FIELDS):
            if config_network.get("type") != "dhcp":
                found["config_network.type"] = None
            if not isinstance(config_network.get("bonding_enabled"), bool):
                found["config_network.bonding_enabled"] = None
        for field in network_write_fields(config_network):
            if field not in config_network:
                found[f"config_network.{field}"] = None

    for field in top_level_write_fields(device):
        if field not in device:
            found[field] = None
    for field in UI_DEFAULTED_TOP_LEVEL_FIELDS:
        if field in device and not isinstance(device[field], bool):
            found[field] = None
    return tuple(found)


def runtime_contract_is_supported(
    network_application_version: object, device: object
) -> bool:
    """Return whether the complete non-mutating runtime contract is compatible."""
    return network_version_is_supported(
        network_application_version
    ) and device_write_contract_is_supported(device)
