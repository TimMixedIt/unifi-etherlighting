"""Fail-closed, independently verified Etherlighting color writes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .api.adapters.unifi_os_controller import UniFiOsControllerAdapter
from .api.adapters.unifi_os_device import (
    UniFiOsDeviceAdapter,
    validate_unifi_write_response,
)
from .api.adapters.unifi_os_etherlighting import (
    ColorMapping,
    EtherlightingColorSettings,
    UniFiOsEtherlightingSettingsAdapter,
    normalize_color_hex,
)
from .api.auth import UniFiAuthSession
from .api.errors import (
    UniFiAuthenticationError,
    UniFiEtherlightingError,
    UniFiPermissionError,
    UnsupportedCompatibilityError,
    WriteBlockedError,
)
from .api.models import color_read_is_supported
from .brightness import (
    BrightnessWriteOutcome,
    build_etherlighting_refresh_payload,
)

_STABLE_DEVICE_FIELDS = (
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


@dataclass(frozen=True, slots=True)
class VerifiedColorResult:
    """Result of a site-color write and independent read-back."""

    outcome: BrightnessWriteOutcome
    category: str
    key: str
    before: str
    requested: str
    observed: str | None
    verified_at: datetime | None
    error_code: str | None = None


def _effective_map(
    settings: EtherlightingColorSettings, category: str
) -> dict[str, str]:
    return {
        item.key: settings.effective_color(category, item.key)
        for item in settings.defaults(category)
    }


def _settings_preserved(
    before: EtherlightingColorSettings,
    after: EtherlightingColorSettings,
    category: str,
    key: str,
) -> bool:
    if before.network_defaults != after.network_defaults:
        return False
    if before.speed_defaults != after.speed_defaults:
        return False
    for checked_category in ("network", "speed"):
        before_overrides = {
            item.key: item.raw_color_hex
            for item in before.overrides(checked_category)
        }
        after_overrides = {
            item.key: item.raw_color_hex
            for item in after.overrides(checked_category)
        }
        for override_key in before_overrides.keys() | after_overrides.keys():
            if checked_category == category and override_key == key:
                continue
            if before_overrides.get(override_key) != after_overrides.get(
                override_key
            ):
                return False
        before_colors = _effective_map(before, checked_category)
        after_colors = _effective_map(after, checked_category)
        if before_colors.keys() != after_colors.keys():
            return False
        for checked_key, before_color in before_colors.items():
            if checked_category == category and checked_key == key:
                continue
            if after_colors[checked_key] != before_color:
                return False
    return True


def _replace_override(
    overrides: tuple[ColorMapping, ...], key: str, color: str
) -> tuple[ColorMapping, ...]:
    replaced = False
    result: list[ColorMapping] = []
    for item in overrides:
        if item.key == key:
            result.append(ColorMapping(key, color))
            replaced = True
        else:
            result.append(item)
    if not replaced:
        result.append(ColorMapping(key, color))
    return tuple(result)


def _device_preserved(before: object, after: object) -> bool:
    if not isinstance(before, dict) or not isinstance(after, dict):
        return False
    if before.get("ether_lighting") != after.get("ether_lighting"):
        return False
    return all(
        field not in before or after.get(field) == before[field]
        for field in _STABLE_DEVICE_FIELDS
    )


class EtherlightingColorService:
    """Change one confirmed site color and independently verify the result."""

    def __init__(
        self,
        auth: UniFiAuthSession,
        controller: UniFiOsControllerAdapter,
        devices: UniFiOsDeviceAdapter,
        settings: UniFiOsEtherlightingSettingsAdapter,
    ) -> None:
        self._auth = auth
        self._controller = controller
        self._devices = devices
        self._settings = settings
        self._blocked_sites: set[str] = set()
        self.last_verified_write: datetime | None = None
        self.last_error_code: str | None = None

    def is_write_blocked(self, site_id: str) -> bool:
        return site_id in self._blocked_sites

    async def _classify_after_failure(
        self,
        site_id: str,
        before_settings: EtherlightingColorSettings,
        before_device: dict[str, object],
        category: str,
        key: str,
        before: str,
        requested: str,
        *,
        reauthenticate: bool,
        error_code: str,
    ) -> VerifiedColorResult:
        try:
            if reauthenticate:
                self._auth.async_invalidate()
                await self._auth.async_login()
            observed_settings = await self._settings.async_read_settings(site_id)
            observed_device = await self._devices.async_read_device(
                site_id, before_device["_id"]
            )
            observed = observed_settings.effective_color(category, key)
            preserved = _settings_preserved(
                before_settings, observed_settings, category, key
            ) and _device_preserved(before_device, observed_device)
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
            self._blocked_sites.add(site_id)
        self.last_error_code = error_code
        return VerifiedColorResult(
            outcome,
            category,
            key,
            before,
            requested,
            observed,
            verified_at,
            error_code,
        )

    async def async_set_color(
        self,
        site_id: str,
        witness_device_id: str,
        category: str,
        key: str,
        color: str,
    ) -> VerifiedColorResult:
        if site_id in self._blocked_sites:
            raise WriteBlockedError(
                "Etherlighting color writes are blocked pending operator review"
            )
        requested = normalize_color_hex(color)
        await self._auth.async_ensure_authenticated()
        version = await self._controller.async_read_network_application_version()
        witness = await self._devices.async_read_device(
            site_id, witness_device_id
        )
        if not color_read_is_supported(version, witness):
            raise UnsupportedCompatibilityError(
                "Color control is unavailable because the runtime API contract did not match"
            )
        current = await self._settings.async_read_settings(site_id)
        before = current.effective_color(category, key)
        if before == requested:
            verified_at = datetime.now(UTC)
            self.last_verified_write = verified_at
            self.last_error_code = None
            return VerifiedColorResult(
                BrightnessWriteOutcome.APPLIED,
                category,
                key,
                before,
                requested,
                before,
                verified_at,
            )

        network_overrides = current.network_overrides
        speed_overrides = current.speed_overrides
        if category == "network":
            network_overrides = _replace_override(
                network_overrides, key, requested
            )
        elif category == "speed":
            speed_overrides = _replace_override(speed_overrides, key, requested)
        else:
            raise ValueError("color category must be network or speed")

        try:
            response_settings = await self._settings.async_write_overrides(
                site_id,
                network_overrides=network_overrides,
                speed_overrides=speed_overrides,
            )
            response_color = response_settings.effective_color(category, key)
            if response_color != requested or not _settings_preserved(
                current, response_settings, category, key
            ):
                return await self._classify_after_failure(
                    site_id,
                    current,
                    witness,
                    category,
                    key,
                    before,
                    requested,
                    reauthenticate=False,
                    error_code="write_response_verification_failed",
                )
            refresh_payload = build_etherlighting_refresh_payload(witness)
            device_response = await self._devices.async_write_device(
                site_id, witness_device_id, refresh_payload
            )
            validate_unifi_write_response(
                device_response,
                expected_json_path=("data", "0", "ether_lighting"),
                expected_value=witness["ether_lighting"],
            )
            verified_settings = await self._settings.async_read_settings(site_id)
            verified_device = await self._devices.async_read_device(
                site_id, witness_device_id
            )
            observed = verified_settings.effective_color(category, key)
            if observed != requested or not _settings_preserved(
                current, verified_settings, category, key
            ) or not _device_preserved(witness, verified_device):
                return await self._classify_after_failure(
                    site_id,
                    current,
                    witness,
                    category,
                    key,
                    before,
                    requested,
                    reauthenticate=False,
                    error_code="read_after_write_verification_failed",
                )
        except (UniFiAuthenticationError, UniFiPermissionError) as err:
            return await self._classify_after_failure(
                site_id,
                current,
                witness,
                category,
                key,
                before,
                requested,
                reauthenticate=True,
                error_code=type(err).__name__,
            )
        except UniFiEtherlightingError as err:
            return await self._classify_after_failure(
                site_id,
                current,
                witness,
                category,
                key,
                before,
                requested,
                reauthenticate=False,
                error_code=type(err).__name__,
            )

        verified_at = datetime.now(UTC)
        self.last_verified_write = verified_at
        self.last_error_code = None
        return VerifiedColorResult(
            BrightnessWriteOutcome.APPLIED,
            category,
            key,
            before,
            requested,
            observed,
            verified_at,
        )
