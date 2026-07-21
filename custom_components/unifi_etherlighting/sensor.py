"""Bounded status and capability sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RuntimeData
from .coordinator import EtherlightingCoordinatorData
from .entity import EtherlightingDiagnosticEntity


def _capability_map(
    data: EtherlightingCoordinatorData, state: str | None = None
) -> dict[str, str]:
    return {
        evidence.capability: evidence.evidence.value
        if state is None
        else evidence.state.value
        for evidence in data.capabilities
        if state is None or evidence.state.value == state
    }


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add entry-level diagnostics backed by the coordinator's safe projection."""
    runtime: RuntimeData = entry.runtime_data
    if not entry.options.get("diagnostic_sensors", True):
        return
    async_add_entities(
        [
            EtherlightingStatusSensor(
                runtime.coordinator, runtime.controller_unique_id
            ),
            EtherlightingVersionSensor(
                runtime.coordinator, runtime.controller_unique_id
            ),
            EtherlightingCapabilitySensor(
                runtime.coordinator, runtime.controller_unique_id, "confirmed"
            ),
            EtherlightingCapabilitySensor(
                runtime.coordinator, runtime.controller_unique_id, "candidate"
            ),
            EtherlightingCapabilitySensor(
                runtime.coordinator, runtime.controller_unique_id, "unsupported"
            ),
            EtherlightingWriteCapabilitySensor(
                runtime.coordinator, runtime.controller_unique_id
            ),
        ]
    )


class EtherlightingStatusSensor(EtherlightingDiagnosticEntity, SensorEntity):
    _attr_translation_key = "integration_status"

    def __init__(self, coordinator: Any, controller_unique_id: str) -> None:
        super().__init__(coordinator, controller_unique_id)
        self._attr_unique_id = f"{controller_unique_id}_integration_status"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.controller_status

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return _capability_map(self.coordinator.data)


class EtherlightingVersionSensor(EtherlightingDiagnosticEntity, SensorEntity):
    _attr_translation_key = "network_application_version"

    def __init__(self, coordinator: Any, controller_unique_id: str) -> None:
        super().__init__(coordinator, controller_unique_id)
        self._attr_unique_id = f"{controller_unique_id}_network_application_version"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.network_application_version or "unknown"


class EtherlightingWriteCapabilitySensor(EtherlightingDiagnosticEntity, SensorEntity):
    """Expose only the bounded central write-lock state and reason."""

    _attr_translation_key = "brightness_write_capability"

    def __init__(self, coordinator: Any, controller_unique_id: str) -> None:
        super().__init__(coordinator, controller_unique_id)
        self._attr_unique_id = f"{controller_unique_id}_brightness_write_capability"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.write_capability

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        devices = self.coordinator.data.devices
        return {
            "brightness_read_supported": any(
                device.brightness_read_supported for device in devices
            ),
            "brightness_write_supported": (
                "candidate"
                if any(
                    device.brightness_write_supported.value == "candidate"
                    for device in devices
                )
                else "unsupported"
            ),
            "brightness_write_ready": any(
                device.brightness_write_ready for device in devices
            ),
            "write_block_reason": self.coordinator.data.write_block_reason,
            "missing_confirmed_fields": list(
                self.coordinator.data.missing_confirmed_fields
            ),
        }


class EtherlightingCapabilitySensor(EtherlightingDiagnosticEntity, SensorEntity):
    def __init__(
        self, coordinator: Any, controller_unique_id: str, capability_state: str
    ) -> None:
        super().__init__(coordinator, controller_unique_id)
        self._capability_state = capability_state
        self._attr_translation_key = f"{capability_state}_capabilities"
        self._attr_unique_id = f"{controller_unique_id}_{capability_state}_capabilities"

    @property
    def native_value(self) -> str:
        capabilities = _capability_map(self.coordinator.data, self._capability_state)
        return self._capability_state if capabilities else "none"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return _capability_map(self.coordinator.data, self._capability_state)
