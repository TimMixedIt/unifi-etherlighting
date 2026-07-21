"""Shared diagnostic entity metadata."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EtherlightingDataUpdateCoordinator


class EtherlightingDiagnosticEntity(
    CoordinatorEntity[EtherlightingDataUpdateCoordinator]
):
    """Attach all entry-level diagnostics to one controller device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: EtherlightingDataUpdateCoordinator, controller_unique_id: str
    ) -> None:
        super().__init__(coordinator)
        self._controller_unique_id = controller_unique_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._controller_unique_id)},
            name="UniFi Etherlighting Controller",
            manufacturer="Ubiquiti",
            model="UniFi OS",
        )
