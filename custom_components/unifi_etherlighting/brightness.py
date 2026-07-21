"""Bounded payload projection and verified Etherlighting brightness writes."""

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
)
from .api.models import brightness_is_confirmed
from .const import BRIGHTNESS_MAXIMUM, BRIGHTNESS_MINIMUM

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
    "lcm_night_mode_enabled",
    "lcm_night_mode_ends",
    "lcm_orientation_override",
    "mgmt_network_id",
    "name",
    "snmp_contact",
    "snmp_location",
    "stp_priority",
)
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


def _project_required_fields(
    source: Mapping[str, Any], fields: tuple[str, ...], label: str
) -> dict[str, Any]:
    missing = [field for field in fields if field not in source]
    if missing:
        raise VerificationError(f"Current Device is missing confirmed {label} fields")
    return {field: deepcopy(source[field]) for field in fields}


def build_brightness_write_payload(
    current_device: Mapping[str, Any], brightness: int
) -> dict[str, Any]:
    """Project exactly the fields sent by the captured UI brightness write."""
    if not isinstance(current_device, Mapping):
        raise TypeError("current_device must be a mapping")
    if isinstance(brightness, bool) or not isinstance(brightness, int):
        raise ValueError("brightness must be an integer")
    if not BRIGHTNESS_MINIMUM <= brightness <= BRIGHTNESS_MAXIMUM:
        raise ValueError(
            f"brightness must be between {BRIGHTNESS_MINIMUM} and {BRIGHTNESS_MAXIMUM}"
        )

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
    if isinstance(projected_ether["brightness"], bool) or not isinstance(
        projected_ether["brightness"], int
    ):
        raise VerificationError("Current Device brightness is not an integer")
    projected_ether["brightness"] = brightness

    payload = _project_required_fields(
        current_device, _TOP_LEVEL_FIELDS, "top-level write"
    )
    payload["config_network"] = _project_required_fields(
        config_network, _CONFIG_NETWORK_FIELDS, "config_network"
    )
    payload["ether_lighting"] = projected_ether
    return payload


class BrightnessWriteOutcome(StrEnum):
    APPLIED = "applied"
    NOT_APPLIED = "not_applied"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class VerifiedBrightnessResult:
    outcome: BrightnessWriteOutcome
    before: int
    requested: int
    observed: int | None
    verified_at: datetime | None
    error_code: str | None = None


def _brightness(device: Mapping[str, Any]) -> int:
    ether_lighting = device.get("ether_lighting")
    if not isinstance(ether_lighting, Mapping):
        raise VerificationError("Device is missing ether_lighting")
    value = ether_lighting.get("brightness")
    if isinstance(value, bool) or not isinstance(value, int):
        raise VerificationError("Device brightness is not an integer")
    return value


def _configuration_preserved(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> bool:
    before_ether = before.get("ether_lighting")
    after_ether = after.get("ether_lighting")
    if not isinstance(before_ether, Mapping) or not isinstance(after_ether, Mapping):
        return False
    for key, value in before_ether.items():
        if key != "brightness" and after_ether.get(key) != value:
            return False
    for field in _STABLE_READ_FIELDS:
        if field in before and after.get(field) != before[field]:
            return False
    return True


class BrightnessService:
    """Write once, read back, and classify every ambiguous result."""

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
        before: int,
        requested: int,
        *,
        reauthenticate: bool,
        error_code: str,
    ) -> VerifiedBrightnessResult:
        try:
            if reauthenticate:
                self._auth.async_invalidate()
                await self._auth.async_login()
            observed_device = await self._devices.async_read_device(site, device_id)
            observed = _brightness(observed_device)
            preserved = _configuration_preserved(before_device, observed_device)
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
        return VerifiedBrightnessResult(
            outcome, before, requested, observed, verified_at, error_code
        )

    async def async_set_brightness(
        self, site: str, device_id: str, brightness: int
    ) -> VerifiedBrightnessResult:
        if device_id in self._blocked_devices:
            raise WriteBlockedError(
                "Brightness writes are blocked pending operator review"
            )
        if isinstance(brightness, bool) or not isinstance(brightness, int):
            raise ValueError("brightness must be an integer")
        if not BRIGHTNESS_MINIMUM <= brightness <= BRIGHTNESS_MAXIMUM:
            raise ValueError("brightness is outside the confirmed UI range")

        await self._auth.async_ensure_authenticated()
        network_version = (
            await self._controller.async_read_network_application_version()
        )
        current = await self._devices.async_read_device(site, device_id)
        if not brightness_is_confirmed(network_version, current):
            raise UnsupportedCompatibilityError(
                "Brightness is not confirmed for this exact runtime compatibility tuple"
            )
        before = _brightness(current)
        payload = build_brightness_write_payload(current, brightness)

        try:
            response = await self._devices.async_write_device(site, device_id, payload)
            validate_unifi_write_response(
                response,
                expected_json_path=("data", "0", "ether_lighting", "brightness"),
                expected_value=brightness,
            )
            verified = await self._devices.async_read_device(site, device_id)
            observed = _brightness(verified)
            if observed != brightness or not _configuration_preserved(
                current, verified
            ):
                return await self._classify_after_failure(
                    site,
                    device_id,
                    current,
                    before,
                    brightness,
                    reauthenticate=False,
                    error_code="write_verification_failed",
                )
        except (UniFiAuthenticationError, UniFiPermissionError) as err:
            return await self._classify_after_failure(
                site,
                device_id,
                current,
                before,
                brightness,
                reauthenticate=True,
                error_code=type(err).__name__,
            )
        except UniFiResponseError as err:
            return await self._classify_after_failure(
                site,
                device_id,
                current,
                before,
                brightness,
                reauthenticate=False,
                error_code=type(err).__name__,
            )

        verified_at = datetime.now(UTC)
        self.last_verified_write = verified_at
        self.last_error_code = None
        return VerifiedBrightnessResult(
            BrightnessWriteOutcome.APPLIED,
            before,
            brightness,
            observed,
            verified_at,
        )
