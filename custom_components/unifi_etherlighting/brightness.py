"""Bounded payload projection and verified Etherlighting control writes."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from .api.adapters.unifi_os_controller import UniFiOsControllerAdapter
from .api.adapters.unifi_os_device import (
    UniFiOsDeviceAdapter,
    validate_unifi_write_response,
)
from .api.auth import UniFiAuthSession
from .api.errors import (
    UniFiAuthenticationError,
    UniFiPermissionError,
    UniFiResponseError,
    UnsupportedCompatibilityError,
    VerificationError,
    WriteBlockedError,
    WriteCapabilityUnavailableError,
)
from .api.models import (
    behavior_read_is_supported,
    brightness_read_is_supported,
    mode_read_is_supported,
)
from .const import (
    BRIGHTNESS_MAXIMUM,
    BRIGHTNESS_MINIMUM,
    WRITE_BLOCK_REASON,
    WRITE_CAPABILITY_ENABLED,
)

_CONFIG_NETWORK_FIELDS = (
    "type",
    "ip",
    "netmask",
    "gateway",
    "dns1",
    "dns2",
    "dnssuffix",
    "bonding_enabled",
)
_ETHER_LIGHTING_FIELDS = ("mode", "brightness", "behavior", "led_mode")
_TOP_LEVEL_FIELDS = (
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
# Live-confirmed Network UI form initialization; see the sanitized source capture.
_UI_DEFAULTED_TOP_LEVEL_FIELDS = {"lcm_night_mode_enabled": False}
_STABLE_READ_FIELDS = (
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
_BEHAVIOR_VALUES = frozenset({"steady", "breath"})
_MODE_VALUES = frozenset({"network", "speed"})
_CONTROL_FIELDS = frozenset({"brightness", "behavior", "mode"})


def _project_required_fields(
    source: Mapping[str, Any], fields: tuple[str, ...], label: str
) -> dict[str, Any]:
    missing = [field for field in fields if field not in source]
    if missing:
        raise VerificationError(f"Current Device is missing confirmed {label} fields")
    return {field: deepcopy(source[field]) for field in fields}


def _validate_requested_value(field: str, value: object) -> int | str:
    if field == "brightness":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("brightness must be an integer")
        if not BRIGHTNESS_MINIMUM <= value <= BRIGHTNESS_MAXIMUM:
            raise ValueError(
                f"brightness must be between {BRIGHTNESS_MINIMUM} and "
                f"{BRIGHTNESS_MAXIMUM}"
            )
        return value
    if field == "behavior":
        if not isinstance(value, str) or value not in _BEHAVIOR_VALUES:
            raise ValueError("behavior must be steady or breath")
        return value
    if field == "mode":
        if not isinstance(value, str) or value not in _MODE_VALUES:
            raise ValueError("mode must be network or speed")
        return value
    raise ValueError("unsupported Etherlighting control field")


def build_etherlighting_write_payload(
    current_device: Mapping[str, Any], changes: Mapping[str, object]
) -> dict[str, Any]:
    """Project the exact UI payload and change exactly one confirmed field."""
    if not isinstance(current_device, Mapping):
        raise TypeError("current_device must be a mapping")
    if not isinstance(changes, Mapping) or len(changes) != 1:
        raise ValueError("exactly one Etherlighting field must change")
    field, raw_value = next(iter(changes.items()))
    if field not in _CONTROL_FIELDS:
        raise ValueError("unsupported Etherlighting control field")
    value = _validate_requested_value(field, raw_value)

    config_network = current_device.get("config_network")
    ether_lighting = current_device.get("ether_lighting")
    if not isinstance(config_network, Mapping):
        raise VerificationError(
            "Current Device is missing the confirmed config_network object"
        )
    if not isinstance(ether_lighting, Mapping):
        raise VerificationError(
            "Current Device is missing the confirmed ether_lighting object"
        )

    projected_ether = _project_required_fields(
        ether_lighting, _ETHER_LIGHTING_FIELDS, "ether_lighting"
    )
    for observed_field in _CONTROL_FIELDS:
        _etherlighting_value(current_device, observed_field)
    if projected_ether["led_mode"] != "etherlighting":
        raise VerificationError("Current Device led_mode is not confirmed")
    projected_ether[field] = value

    payload = _project_required_fields(
        current_device, _TOP_LEVEL_FIELDS, "top-level write"
    )
    for ui_field, ui_default in _UI_DEFAULTED_TOP_LEVEL_FIELDS.items():
        ui_value = current_device[ui_field] if ui_field in current_device else ui_default
        if not isinstance(ui_value, bool):
            raise VerificationError(
                "Current Device UI-defaulted write field is not a boolean"
            )
        payload[ui_field] = ui_value
    payload["config_network"] = _project_required_fields(
        config_network, _CONFIG_NETWORK_FIELDS, "config_network"
    )
    payload["ether_lighting"] = projected_ether
    return payload


def build_brightness_write_payload(
    current_device: Mapping[str, Any], brightness: int
) -> dict[str, Any]:
    return build_etherlighting_write_payload(
        current_device, {"brightness": brightness}
    )


def build_behavior_write_payload(
    current_device: Mapping[str, Any], behavior: str
) -> dict[str, Any]:
    return build_etherlighting_write_payload(current_device, {"behavior": behavior})


def build_mode_write_payload(
    current_device: Mapping[str, Any], mode: str
) -> dict[str, Any]:
    return build_etherlighting_write_payload(current_device, {"mode": mode})


class BrightnessWriteOutcome(StrEnum):
    """Outcome shared by all verified Etherlighting control writes."""

    APPLIED = "applied"
    NOT_APPLIED = "not_applied"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class VerifiedEtherlightingResult:
    outcome: BrightnessWriteOutcome
    field: str
    before: int | str
    requested: int | str
    observed: int | str | None
    verified_at: datetime | None
    error_code: str | None = None


VerifiedBrightnessResult = VerifiedEtherlightingResult


def _etherlighting_value(device: Mapping[str, Any], field: str) -> int | str:
    ether_lighting = device.get("ether_lighting")
    if not isinstance(ether_lighting, Mapping):
        raise VerificationError("Device is missing ether_lighting")
    value = ether_lighting.get(field)
    try:
        return _validate_requested_value(field, value)
    except ValueError as err:
        raise VerificationError(f"Device {field} is not confirmed") from err


def _configuration_preserved(
    before: Mapping[str, Any], after: Mapping[str, Any], changed_field: str
) -> bool:
    before_ether = before.get("ether_lighting")
    after_ether = after.get("ether_lighting")
    if not isinstance(before_ether, Mapping) or not isinstance(after_ether, Mapping):
        return False
    for key, value in before_ether.items():
        if key != changed_field and after_ether.get(key) != value:
            return False
    for field in _STABLE_READ_FIELDS:
        if field in before and after.get(field) != before[field]:
            return False
    return True


class BrightnessService:
    """Write one confirmed field once, read it back, and fail closed."""

    def __init__(
        self,
        auth: UniFiAuthSession,
        controller: UniFiOsControllerAdapter,
        devices: UniFiOsDeviceAdapter,
    ) -> None:
        self._auth = auth
        self._controller = controller
        self._devices = devices
        self._blocked_devices: set[str] = set()
        self.last_verified_write: datetime | None = None
        self.last_error_code: str | None = None

    def is_write_blocked(self, device_id: str) -> bool:
        return device_id in self._blocked_devices

    async def _classify_after_failure(
        self,
        site: str,
        device_id: str,
        before_device: Mapping[str, Any],
        field: str,
        before: int | str,
        requested: int | str,
        *,
        reauthenticate: bool,
        error_code: str,
    ) -> VerifiedEtherlightingResult:
        try:
            if reauthenticate:
                self._auth.async_invalidate()
                await self._auth.async_login()
            observed_device = await self._devices.async_read_device(site, device_id)
            observed = _etherlighting_value(observed_device, field)
            preserved = _configuration_preserved(
                before_device, observed_device, field
            )
        except Exception:
            observed = None
            preserved = False

        if preserved and observed == requested:
            outcome = BrightnessWriteOutcome.APPLIED
            verified_at = datetime.now(UTC)
            self.last_verified_write = verified_at
        elif preserved and observed == before:
            outcome = BrightnessWriteOutcome.NOT_APPLIED
            verified_at = datetime.now(UTC)
        else:
            outcome = BrightnessWriteOutcome.INDETERMINATE
            verified_at = None
            self._blocked_devices.add(device_id)
        self.last_error_code = error_code
        return VerifiedEtherlightingResult(
            outcome,
            field,
            before,
            requested,
            observed,
            verified_at,
            error_code,
        )

    async def _async_set_value(
        self, site: str, device_id: str, field: str, requested_value: object
    ) -> VerifiedEtherlightingResult:
        if not WRITE_CAPABILITY_ENABLED:
            self.last_error_code = WRITE_BLOCK_REASON
            raise WriteCapabilityUnavailableError(WRITE_BLOCK_REASON)
        if device_id in self._blocked_devices:
            raise WriteBlockedError(
                "Etherlighting writes are blocked pending operator review"
            )
        requested = _validate_requested_value(field, requested_value)

        await self._auth.async_ensure_authenticated()
        network_version = (
            await self._controller.async_read_network_application_version()
        )
        current = await self._devices.async_read_device(site, device_id)
        support_check = {
            "brightness": brightness_read_is_supported,
            "behavior": behavior_read_is_supported,
            "mode": mode_read_is_supported,
        }[field]
        if not support_check(network_version, current):
            raise UnsupportedCompatibilityError(
                f"{field} is not confirmed for this exact runtime compatibility tuple"
            )
        before = _etherlighting_value(current, field)
        if before == requested:
            verified_at = datetime.now(UTC)
            self.last_verified_write = verified_at
            self.last_error_code = None
            return VerifiedEtherlightingResult(
                BrightnessWriteOutcome.APPLIED,
                field,
                before,
                requested,
                before,
                verified_at,
            )
        payload = build_etherlighting_write_payload(current, {field: requested})

        try:
            response = await self._devices.async_write_device(site, device_id, payload)
            validate_unifi_write_response(
                response,
                expected_json_path=("data", "0", "ether_lighting", field),
                expected_value=requested,
            )
            verified = await self._devices.async_read_device(site, device_id)
            observed = _etherlighting_value(verified, field)
            if observed != requested or not _configuration_preserved(
                current, verified, field
            ):
                return await self._classify_after_failure(
                    site,
                    device_id,
                    current,
                    field,
                    before,
                    requested,
                    reauthenticate=False,
                    error_code="write_verification_failed",
                )
        except (UniFiAuthenticationError, UniFiPermissionError) as err:
            return await self._classify_after_failure(
                site,
                device_id,
                current,
                field,
                before,
                requested,
                reauthenticate=True,
                error_code=type(err).__name__,
            )
        except (UniFiResponseError, VerificationError) as err:
            return await self._classify_after_failure(
                site,
                device_id,
                current,
                field,
                before,
                requested,
                reauthenticate=False,
                error_code=type(err).__name__,
            )

        verified_at = datetime.now(UTC)
        self.last_verified_write = verified_at
        self.last_error_code = None
        return VerifiedEtherlightingResult(
            BrightnessWriteOutcome.APPLIED,
            field,
            before,
            requested,
            observed,
            verified_at,
        )

    async def async_set_brightness(
        self, site: str, device_id: str, brightness: int
    ) -> VerifiedEtherlightingResult:
        return await self._async_set_value(site, device_id, "brightness", brightness)

    async def async_set_behavior(
        self, site: str, device_id: str, behavior: str
    ) -> VerifiedEtherlightingResult:
        return await self._async_set_value(site, device_id, "behavior", behavior)

    async def async_set_mode(
        self, site: str, device_id: str, mode: str
    ) -> VerifiedEtherlightingResult:
        return await self._async_set_value(site, device_id, "mode", mode)
