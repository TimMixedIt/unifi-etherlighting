"""Read-only coordinator for controller version and selected Etherlighting Devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.adapters.unifi_os_controller import UniFiOsControllerAdapter
from .api.adapters.unifi_os_device import UniFiOsDeviceAdapter
from .api.adapters.unifi_os_etherlighting import (
    UniFiOsEtherlightingSettingsAdapter,
)
from .api.errors import UniFiEtherlightingError
from .api.models import (
    CapabilityEvidence,
    CapabilityState,
    behavior_capability_status,
    brightness_capability_status,
    capabilities_for_runtime,
    color_read_is_supported,
    mode_capability_status,
)
from .brightness import BrightnessService
from .color import EtherlightingColorService
from .const import (
    ACTIVE_WRITE_BLOCK_REASON,
    CONF_DEVICE_IDS,
    CONF_POLL_INTERVAL,
    CONF_SITE,
    CONTROLLER_STATUS_ONLINE,
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
        brightness_service: BrightnessService,
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
        self._brightness_service = brightness_service
        self._color_settings = color_settings
        self._color_service = color_service

    async def _async_update_data(self) -> EtherlightingCoordinatorData:
        site = self._entry.data[CONF_SITE]
        selected_ids = tuple(self._entry.data[CONF_DEVICE_IDS])
        try:
            network_version = (
                await self._controller.async_read_network_application_version()
            )
            all_devices = await self._devices.async_read_devices(site)
        except UniFiEtherlightingError as err:
            raise UpdateFailed(type(err).__name__) from err

        selected = tuple(
            device for device in all_devices if device.get("_id") in selected_ids
        )
        diagnostic_devices_list: list[DiagnosticDevice] = []
        for device in selected:
            if not isinstance(device.get("_id"), str):
                continue
            brightness_capability = brightness_capability_status(
                network_version, device
            )
            behavior_capability = behavior_capability_status(network_version, device)
            mode_capability = mode_capability_status(network_version, device)
            diagnostic_devices_list.append(
                DiagnosticDevice(
                    identifier=str(device["_id"]),
                    model=str(device.get("model", "unknown")),
                    firmware=str(device.get("version", "unknown")),
                    brightness=_device_brightness(device),
                    brightness_read_supported=brightness_capability.read_supported,
                    brightness_write_supported=brightness_capability.write_supported,
                    brightness_write_ready=brightness_capability.write_ready,
                    behavior=_device_choice(
                        device, "behavior", frozenset({"steady", "breath"})
                    ),
                    behavior_read_supported=behavior_capability.read_supported,
                    behavior_write_supported=behavior_capability.write_supported,
                    behavior_write_ready=behavior_capability.write_ready,
                    mode=_device_choice(
                        device, "mode", frozenset({"network", "speed"})
                    ),
                    mode_read_supported=mode_capability.read_supported,
                    mode_write_supported=mode_capability.write_supported,
                    mode_write_ready=mode_capability.write_ready,
                    write_blocked=self._brightness_service.is_write_blocked(
                        str(device["_id"])
                    ),
                )
            )
        diagnostic_devices = tuple(diagnostic_devices_list)
        colors: tuple[DiagnosticColor, ...] = ()
        witness = next(
            (
                device
                for device in selected
                if isinstance(device.get("_id"), str)
                and color_read_is_supported(network_version, device)
            ),
            None,
        )
        if witness is not None:
            try:
                settings = await self._color_settings.async_read_settings(site)
                labels = await self._color_settings.async_read_network_labels(site)
            except UniFiEtherlightingError as err:
                raise UpdateFailed(type(err).__name__) from err
            label_map = {label.key: label.name for label in labels}
            witness_id = str(witness["_id"])
            color_items: list[DiagnosticColor] = []
            for item in settings.network_defaults:
                if item.key == "none" or item.key not in label_map:
                    continue
                color_items.append(
                    DiagnosticColor(
                        category="network",
                        key=item.key,
                        name=label_map[item.key],
                        raw_color_hex=settings.effective_color(
                            "network", item.key
                        ),
                        witness_device_id=witness_id,
                        read_supported=True,
                        write_supported=CapabilityState.CONFIRMED,
                        write_ready=True,
                        write_blocked=self._color_service.is_write_blocked(site),
                    )
                )
            speed_defaults = {item.key for item in settings.speed_defaults}
            for speed_key in SUPPORTED_SPEED_COLOR_KEYS:
                if speed_key not in speed_defaults:
                    continue
                color_items.append(
                    DiagnosticColor(
                        category="speed",
                        key=speed_key,
                        name=speed_key,
                        raw_color_hex=settings.effective_color("speed", speed_key),
                        witness_device_id=witness_id,
                        read_supported=True,
                        write_supported=CapabilityState.CONFIRMED,
                        write_ready=True,
                        write_blocked=self._color_service.is_write_blocked(site),
                    )
                )
            colors = tuple(color_items)
        status = (
            CONTROLLER_STATUS_ONLINE
            if any(
                device.brightness_read_supported
                or device.behavior_read_supported
                or device.mode_read_supported
                for device in diagnostic_devices
            )
            else CONTROLLER_STATUS_UNSUPPORTED
        )
        return EtherlightingCoordinatorData(
            controller_status=status,
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
                        self._brightness_service.last_verified_write,
                        self._color_service.last_verified_write,
                    )
                    if value is not None
                ),
                default=None,
            ),
            last_error=(
                self._color_service.last_error_code
                or self._brightness_service.last_error_code
            ),
            write_capability=WRITE_CAPABILITY_STATE,
            write_block_reason=ACTIVE_WRITE_BLOCK_REASON,
            missing_confirmed_fields=MISSING_CONFIRMED_WRITE_FIELDS,
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
