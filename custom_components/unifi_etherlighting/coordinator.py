"""Read-only coordinator for controller version and selected Etherlighting Devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.adapters.unifi_os_controller import UniFiOsControllerAdapter
from .api.adapters.unifi_os_device import UniFiOsDeviceAdapter
from .api.adapters.unifi_os_etherlighting import (
    UniFiOsEtherlightingSettingsAdapter,
)
from .api.errors import (
    UniFiAuthenticationError,
    UniFiEtherlightingError,
    UniFiPermissionError,
    UniFiResponseError,
    UniFiSchemaError,
    UniFiTransportError,
)
from .api.models import (
    CapabilityEvidence,
    CapabilityState,
    behavior_capability_status,
    brightness_capability_status,
    capabilities_for_runtime,
    color_read_is_supported,
    mode_capability_status,
)
from .brightness import DeviceControlService
from .color import EtherlightingColorService
from .compatibility import (
    BEHAVIOR_VALUES,
    COMPATIBILITY_PROFILE,
    MODE_VALUES,
    device_read_contract_mismatches,
    network_version_is_supported,
    runtime_contract_is_supported,
)
from .const import (
    ACTIVE_WRITE_BLOCK_REASON,
    CONF_DEVICE_IDS,
    CONF_POLL_INTERVAL,
    CONF_SITE,
    CONTROLLER_STATUS_ONLINE,
    CONTROLLER_STATUS_SELECTED_DEVICES_NOT_RETURNED,
    CONTROLLER_STATUS_UNSUPPORTED,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DOMAIN,
    MISSING_CONFIRMED_WRITE_FIELDS,
    SUPPORTED_SPEED_COLOR_KEYS,
    WRITE_CAPABILITY_STATE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DiagnosticDevice:
    identifier: str
    model: str
    firmware: str
    brightness: int | None
    brightness_read_supported: bool
    brightness_write_supported: CapabilityState
    brightness_write_ready: bool
    behavior: str | None
    behavior_read_supported: bool
    behavior_write_supported: CapabilityState
    behavior_write_ready: bool
    mode: str | None
    mode_read_supported: bool
    mode_write_supported: CapabilityState
    mode_write_ready: bool
    write_blocked: bool
    read_contract_mismatches: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DiagnosticColor:
    """One live-read, site-wide network or speed color."""

    category: str
    key: str
    name: str
    raw_color_hex: str
    witness_device_id: str
    read_supported: bool
    write_supported: CapabilityState
    write_ready: bool
    write_blocked: bool


@dataclass(frozen=True, slots=True)
class EtherlightingCoordinatorData:
    controller_status: str
    controller_type: str | None
    network_application_version: str | None
    devices: tuple[DiagnosticDevice, ...]
    colors: tuple[DiagnosticColor, ...]
    capabilities: tuple[CapabilityEvidence, ...]
    last_successful_update: datetime | None
    last_verified_write: datetime | None
    last_error: str | None
    write_capability: str
    write_block_reason: str | None
    missing_confirmed_fields: tuple[str, ...]
    compatibility_profile: str = COMPATIBILITY_PROFILE
    network_api_generation_supported: bool = False
    contract_compatible_device_count: int = 0
    configured_device_count: int = 0
    returned_device_count: int = 0
    returned_switch_count: int = 0
    selected_device_count: int = 0
    read_contract_compatible_device_count: int = 0
    runtime_read_contract_reason: str = "unknown"
    read_contract_mismatch_fields: tuple[str, ...] = ()
    color_metadata_status: str = "not_applicable"
    color_metadata_error: str | None = None


def _safe_refresh_error_category(error: UniFiEtherlightingError) -> str:
    """Classify a controller error without retaining controller-provided text."""
    if isinstance(error, UniFiAuthenticationError):
        return "authentication"
    if isinstance(error, UniFiPermissionError):
        return "permission"
    if isinstance(error, UniFiTransportError):
        return f"transport_{error.reason.value}"
    if isinstance(error, UniFiSchemaError):
        return "schema"
    if isinstance(error, UniFiResponseError):
        return "response"
    return "unknown"


def _device_brightness(device: dict[str, Any]) -> int | None:
    ether_lighting = device.get("ether_lighting")
    if not isinstance(ether_lighting, dict):
        return None
    value = ether_lighting.get("brightness")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _device_choice(
    device: dict[str, Any], field: str, allowed: frozenset[str]
) -> str | None:
    ether_lighting = device.get("ether_lighting")
    if not isinstance(ether_lighting, dict):
        return None
    value = ether_lighting.get(field)
    return value if isinstance(value, str) and value in allowed else None


def _runtime_read_contract_reason(
    network_version: str,
    selected_ids: tuple[object, ...],
    all_devices: tuple[dict[str, Any], ...],
    read_contract_compatible_device_count: int,
) -> str:
    """Return the allowlisted reason for the current read-contract state."""
    returned_ids = {
        device.get("_id")
        for device in all_devices
        if isinstance(device.get("_id"), str)
    }
    if not network_version_is_supported(network_version):
        return "unsupported_network_api_generation"
    if not selected_ids:
        return "no_configured_devices"
    if any(
        not isinstance(device_id, str) or device_id not in returned_ids
        for device_id in selected_ids
    ):
        return "selected_devices_not_returned"
    if not read_contract_compatible_device_count:
        return "selected_devices_read_contract_mismatch"
    return "read_contract_supported"


def _controller_status(
    read_contract_compatible_device_count: int, runtime_read_contract_reason: str
) -> str:
    if read_contract_compatible_device_count:
        return CONTROLLER_STATUS_ONLINE
    if runtime_read_contract_reason == "selected_devices_not_returned":
        # None of the selected Devices provides a usable read contract and
        # at least one saved identifier is no longer in the current read
        # response. This is distinct from a Network-version or Device-
        # schema incompatibility and must not imply either one.
        return CONTROLLER_STATUS_SELECTED_DEVICES_NOT_RETURNED
    return CONTROLLER_STATUS_UNSUPPORTED


class EtherlightingDataUpdateCoordinator(
    DataUpdateCoordinator[EtherlightingCoordinatorData]
):
    """Poll only confirmed read endpoints; polling can never write."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        controller: UniFiOsControllerAdapter,
        devices: UniFiOsDeviceAdapter,
        control_service: DeviceControlService,
        color_settings: UniFiOsEtherlightingSettingsAdapter,
        color_service: EtherlightingColorService,
    ) -> None:
        interval = int(
            entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL_SECONDS)
        )
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
            config_entry=entry,
        )
        self._entry = entry
        self._controller = controller
        self._devices = devices
        self._control_service = control_service
        self._color_settings = color_settings
        self._color_service = color_service
        self._last_refresh_error: str | None = None

    @property
    def last_refresh_error(self) -> str | None:
        """Return an allowlisted category for the most recent failed refresh."""
        return self._last_refresh_error

    async def _async_update_data(self) -> EtherlightingCoordinatorData:
        site = self._entry.data[CONF_SITE]
        selected_ids = tuple(self._entry.data[CONF_DEVICE_IDS])
        self._last_refresh_error = None
        try:
            network_version = (
                await self._controller.async_read_network_application_version()
            )
            all_devices = await self._devices.async_read_devices(site)
        except UniFiAuthenticationError as err:
            self._last_refresh_error = _safe_refresh_error_category(err)
            raise ConfigEntryAuthFailed from err
        except UniFiEtherlightingError as err:
            self._last_refresh_error = _safe_refresh_error_category(err)
            raise UpdateFailed(type(err).__name__) from err

        selected = tuple(
            device for device in all_devices if device.get("_id") in selected_ids
        )
        diagnostic_devices = tuple(
            self._diagnostic_device(network_version, device)
            for device in selected
            if isinstance(device.get("_id"), str)
        )
        colors, color_metadata_status, color_metadata_error = (
            await self._async_read_colors(site, network_version, selected)
        )
        read_contract_compatible_device_count = sum(
            device.brightness_read_supported
            or device.behavior_read_supported
            or device.mode_read_supported
            for device in diagnostic_devices
        )
        runtime_read_contract_reason = _runtime_read_contract_reason(
            network_version,
            selected_ids,
            all_devices,
            read_contract_compatible_device_count,
        )
        read_contract_mismatch_fields = tuple(
            dict.fromkeys(
                label
                for device in diagnostic_devices
                for label in device.read_contract_mismatches
            )
        )
        return EtherlightingCoordinatorData(
            controller_status=_controller_status(
                read_contract_compatible_device_count, runtime_read_contract_reason
            ),
            controller_type="unifi_os",
            network_application_version=network_version,
            devices=diagnostic_devices,
            colors=colors,
            capabilities=capabilities_for_runtime(network_version, selected),
            last_successful_update=datetime.now(UTC),
            last_verified_write=max(
                (
                    value
                    for value in (
                        self._control_service.last_verified_write,
                        self._color_service.last_verified_write,
                    )
                    if value is not None
                ),
                default=None,
            ),
            last_error=(
                self._color_service.last_error_code
                or self._control_service.last_error_code
            ),
            write_capability=WRITE_CAPABILITY_STATE,
            write_block_reason=ACTIVE_WRITE_BLOCK_REASON,
            missing_confirmed_fields=MISSING_CONFIRMED_WRITE_FIELDS,
            compatibility_profile=COMPATIBILITY_PROFILE,
            network_api_generation_supported=network_version_is_supported(
                network_version
            ),
            contract_compatible_device_count=sum(
                runtime_contract_is_supported(network_version, device)
                for device in selected
            ),
            configured_device_count=len(selected_ids),
            returned_device_count=len(all_devices),
            returned_switch_count=sum(
                device.get("type") == "usw" for device in all_devices
            ),
            selected_device_count=len(selected),
            read_contract_compatible_device_count=read_contract_compatible_device_count,
            runtime_read_contract_reason=runtime_read_contract_reason,
            read_contract_mismatch_fields=read_contract_mismatch_fields,
            color_metadata_status=color_metadata_status,
            color_metadata_error=color_metadata_error,
        )

    def _diagnostic_device(
        self, network_version: str, device: dict[str, Any]
    ) -> DiagnosticDevice:
        """Project one selected Device into bounded read and write state."""
        brightness = brightness_capability_status(network_version, device)
        behavior = behavior_capability_status(network_version, device)
        mode = mode_capability_status(network_version, device)
        return DiagnosticDevice(
            identifier=str(device["_id"]),
            model=str(device.get("model", "unknown")),
            firmware=str(device.get("version", "unknown")),
            brightness=_device_brightness(device),
            brightness_read_supported=brightness.read_supported,
            brightness_write_supported=brightness.write_supported,
            brightness_write_ready=brightness.write_ready,
            behavior=_device_choice(device, "behavior", BEHAVIOR_VALUES),
            behavior_read_supported=behavior.read_supported,
            behavior_write_supported=behavior.write_supported,
            behavior_write_ready=behavior.write_ready,
            mode=_device_choice(device, "mode", MODE_VALUES),
            mode_read_supported=mode.read_supported,
            mode_write_supported=mode.write_supported,
            mode_write_ready=mode.write_ready,
            write_blocked=self._control_service.is_write_blocked(str(device["_id"])),
            read_contract_mismatches=device_read_contract_mismatches(device),
        )

    async def _async_read_colors(
        self,
        site: str,
        network_version: str,
        selected: tuple[dict[str, Any], ...],
    ) -> tuple[tuple[DiagnosticColor, ...], str, str | None]:
        """Return site colors, metadata status and error category.

        Colors need one selected witness Device with a complete no-op write
        contract; without one, color metadata is not applicable.
        """
        witness = next(
            (
                device
                for device in selected
                if isinstance(device.get("_id"), str)
                and color_read_is_supported(network_version, device)
            ),
            None,
        )
        if witness is None:
            return (), "not_applicable", None
        try:
            settings = await self._color_settings.async_read_settings(site)
            labels = await self._color_settings.async_read_network_labels(site)
        except UniFiAuthenticationError as err:
            # Authentication is required for every confirmed endpoint. Do
            # not hide a reauthentication condition behind optional color
            # metadata just because Device state was read earlier.
            self._last_refresh_error = _safe_refresh_error_category(err)
            raise ConfigEntryAuthFailed from err
        except UniFiEtherlightingError as err:
            # Color metadata is an optional, site-wide extension. A
            # failed metadata read must never make the independently
            # confirmed Device controls unavailable. Returning no colors
            # also keeps every color write path closed until a later
            # successful refresh rebuilds the metadata.
            error = _safe_refresh_error_category(err)
            _LOGGER.debug(
                "Optional Etherlighting color metadata refresh failed: %s", error
            )
            return (), "unavailable", error

        witness_id = str(witness["_id"])
        write_blocked = self._color_service.is_write_blocked(site)

        def color(category: str, key: str, name: str) -> DiagnosticColor:
            return DiagnosticColor(
                category=category,
                key=key,
                name=name,
                raw_color_hex=settings.effective_color(category, key),
                witness_device_id=witness_id,
                read_supported=True,
                write_supported=CapabilityState.CONFIRMED,
                write_ready=True,
                write_blocked=write_blocked,
            )

        label_map = {label.key: label.name for label in labels}
        speed_defaults = {item.key for item in settings.speed_defaults}
        return (
            tuple(
                color("network", item.key, label_map[item.key])
                for item in settings.network_defaults
                if item.key != "none" and item.key in label_map
            )
            + tuple(
                color("speed", key, key)
                for key in SUPPORTED_SPEED_COLOR_KEYS
                if key in speed_defaults
            ),
            "ready",
            None,
        )

    def device(self, device_id: str) -> DiagnosticDevice | None:
        if self.data is None:
            return None
        return next(
            (device for device in self.data.devices if device.identifier == device_id),
            None,
        )

    def color(self, category: str, key: str) -> DiagnosticColor | None:
        if self.data is None:
            return None
        return next(
            (
                color
                for color in self.data.colors
                if color.category == category and color.key == key
            ),
            None,
        )
