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
from .api.errors import UniFiEtherlightingError
from .api.models import (
    CapabilityState,
    CapabilityEvidence,
    brightness_capability_status,
    capabilities_for_runtime,
)
from .brightness import BrightnessService
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
    write_blocked: bool


@dataclass(frozen=True, slots=True)
class EtherlightingCoordinatorData:
    controller_status: str
    controller_type: str | None
    network_application_version: str | None
    devices: tuple[DiagnosticDevice, ...]
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
            capability = brightness_capability_status(network_version, device)
            diagnostic_devices_list.append(
                DiagnosticDevice(
                    identifier=str(device["_id"]),
                    model=str(device.get("model", "unknown")),
                    firmware=str(device.get("version", "unknown")),
                    brightness=_device_brightness(device),
                    brightness_read_supported=capability.read_supported,
                    brightness_write_supported=capability.write_supported,
                    brightness_write_ready=capability.write_ready,
                    write_blocked=self._brightness_service.is_write_blocked(
                        str(device["_id"])
                    ),
                )
            )
        diagnostic_devices = tuple(diagnostic_devices_list)
        status = (
            CONTROLLER_STATUS_ONLINE
            if any(device.brightness_read_supported for device in diagnostic_devices)
            else CONTROLLER_STATUS_UNSUPPORTED
        )
        return EtherlightingCoordinatorData(
            controller_status=status,
            controller_type="unifi_os",
            network_application_version=network_version,
            devices=diagnostic_devices,
            capabilities=capabilities_for_runtime(network_version, selected),
            last_successful_update=datetime.now(UTC),
            last_verified_write=self._brightness_service.last_verified_write,
            last_error=self._brightness_service.last_error_code,
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
