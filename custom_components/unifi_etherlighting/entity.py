"""Shared entity metadata and the verified write flow for all controls."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Protocol

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .brightness import WriteOutcome
from .const import (
    CONF_DEVICE_IDS,
    CONF_SITE,
    DOMAIN,
    WRITE_CAPABILITY_ENABLED,
    WRITE_DISABLED_MESSAGE,
    WRITE_NOT_READY_MESSAGE,
)
from .coordinator import DiagnosticDevice, EtherlightingDataUpdateCoordinator
from .repairs import async_sync_repairs

if TYPE_CHECKING:
    from . import RuntimeData


class _VerifiedResult(Protocol):
    outcome: WriteOutcome


def configured_device_ids(entry: ConfigEntry) -> list[str]:
    """Return the entry's saved Device IDs once each, in saved order."""
    return list(
        dict.fromkeys(
            device_id
            for device_id in entry.data.get(CONF_DEVICE_IDS, ())
            if isinstance(device_id, str)
        )
    )


def controller_device_info(controller_unique_id: str) -> DeviceInfo:
    """Return the controller device that holds entry-level entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, controller_unique_id)},
        name="UniFi Etherlighting Controller",
        manufacturer="Ubiquiti",
        model="UniFi OS",
    )


async def async_finish_verified_write(
    entity: CoordinatorEntity[Any],
    entry: ConfigEntry,
    label: str,
    write: Callable[[], Awaitable[_VerifiedResult]],
) -> None:
    """Run one service write, refresh, sync Repairs, and require APPLIED."""
    try:
        result = await write()
    except Exception as err:
        raise HomeAssistantError(
            f"Etherlighting {label} write failed safely"
        ) from err

    await entity.coordinator.async_request_refresh()
    await async_sync_repairs(
        entity.hass,
        entry,
        entity.coordinator.data,
        entity.coordinator.last_refresh_error,
    )
    if result.outcome is not WriteOutcome.APPLIED:
        raise HomeAssistantError(
            f"Etherlighting {label} write was not verified ({result.outcome.value})"
        )


class EtherlightingControllerEntity(
    CoordinatorEntity[EtherlightingDataUpdateCoordinator]
):
    """Attach an entry-level entity to the one controller device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: EtherlightingDataUpdateCoordinator, controller_unique_id: str
    ) -> None:
        super().__init__(coordinator)
        self._controller_unique_id = controller_unique_id

    @property
    def device_info(self) -> DeviceInfo:
        return controller_device_info(self._controller_unique_id)


class EtherlightingDeviceControl(
    CoordinatorEntity[EtherlightingDataUpdateCoordinator]
):
    """A control for one selected switch, written only through verified services."""

    _attr_has_entity_name = True
    _unique_id_suffix: str

    def __init__(
        self, runtime: RuntimeData, entry: ConfigEntry, device_id: str
    ) -> None:
        super().__init__(runtime.coordinator)
        self._runtime = runtime
        self._entry = entry
        self._device_id = device_id
        self._attr_unique_id = (
            f"{runtime.controller_unique_id}_{device_id}{self._unique_id_suffix}"
        )

    @property
    def _device(self) -> DiagnosticDevice | None:
        return self.coordinator.device(self._device_id)

    @property
    def _site(self) -> str:
        return self._entry.data[CONF_SITE]

    @property
    def device_info(self) -> DeviceInfo:
        device = self._device
        return DeviceInfo(
            identifiers={
                (DOMAIN, f"{self._runtime.controller_unique_id}:{self._device_id}")
            },
            name="UniFi Etherlighting Switch",
            manufacturer="Ubiquiti",
            model=device.model if device is not None else None,
            sw_version=device.firmware if device is not None else None,
            via_device=(DOMAIN, self._runtime.controller_unique_id),
        )

    @staticmethod
    def _ensure_write_ready(write_ready: bool) -> None:
        """Fail before any controller call unless the gate and contract allow it."""
        if not WRITE_CAPABILITY_ENABLED:
            raise HomeAssistantError(WRITE_DISABLED_MESSAGE)
        if not write_ready:
            raise HomeAssistantError(WRITE_NOT_READY_MESSAGE)
