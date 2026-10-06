"""Bounded status and capability sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RuntimeData
from .const import VERSION
from .coordinator import EtherlightingCoordinatorData
from .entity import EtherlightingDiagnosticEntity
from .write_readiness import effective_write_ready, effective_write_readiness


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
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            # This is sourced from the loaded Python module, so it can reveal a
            # HACS update that has not yet been applied by a full HA reload.
            "runtime_integration_version": VERSION,
            **_capability_map(self.coordinator.data),
            "compatibility_profile": self.coordinator.data.compatibility_profile,
            "network_api_generation_supported": (
                self.coordinator.data.network_api_generation_supported
            ),
            "contract_compatible_device_count": (
                self.coordinator.data.contract_compatible_device_count
            ),
            "configured_device_count": self.coordinator.data.configured_device_count,
            "returned_device_count": self.coordinator.data.returned_device_count,
            "returned_switch_count": self.coordinator.data.returned_switch_count,
            "selected_device_count": self.coordinator.data.selected_device_count,
            "read_contract_compatible_device_count": (
                self.coordinator.data.read_contract_compatible_device_count
            ),
            "runtime_read_contract_reason": (
                self.coordinator.data.runtime_read_contract_reason
            ),
            "read_contract_mismatch_fields": list(
                self.coordinator.data.read_contract_mismatch_fields
            ),
        }


class EtherlightingVersionSensor(EtherlightingDiagnosticEntity, SensorEntity):
    _attr_translation_key = "network_application_version"

    def __init__(self, coordinator: Any, controller_unique_id: str) -> None:
        super().__init__(coordinator, controller_unique_id)
        self._attr_unique_id = f"{controller_unique_id}_network_application_version"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.network_application_version or "unknown"


class EtherlightingWriteCapabilitySensor(EtherlightingDiagnosticEntity, SensorEntity):
    """Expose effective runtime readiness separately from the release-wide gate."""

    _attr_translation_key = "brightness_write_capability"

    def __init__(self, coordinator: Any, controller_unique_id: str) -> None:
        super().__init__(coordinator, controller_unique_id)
        self._attr_unique_id = f"{controller_unique_id}_brightness_write_capability"

    @property
    def native_value(self) -> str:
        data = self.coordinator.data
        return effective_write_readiness(
            data.write_capability, data.devices, data.colors
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self.coordinator.data
        devices = data.devices
        write_states = {device.brightness_write_supported.value for device in devices}
        return {
            # ``write_capability`` used to be this sensor's state.  Keep the
            # release-wide gate visible, but do not present it as a per-device
            # permission to write.
            "global_write_capability": data.write_capability,
            "effective_write_ready": effective_write_ready(
                data.write_capability, devices, data.colors
            ),
            "brightness_read_supported": any(
                device.brightness_read_supported for device in devices
            ),
            "brightness_write_supported": (
                "confirmed"
                if "confirmed" in write_states
                else "candidate"
                if "candidate" in write_states
                else "unsupported"
            ),
            "brightness_write_ready": any(
                device.brightness_write_ready for device in devices
            ),
            "behavior_read_supported": any(
                device.behavior_read_supported for device in devices
            ),
            "behavior_write_supported": (
                "confirmed"
                if any(
                    device.behavior_write_supported.value == "confirmed"
                    for device in devices
                )
                else "unsupported"
            ),
            "behavior_write_ready": any(
                device.behavior_write_ready for device in devices
            ),
            "mode_read_supported": any(
                device.mode_read_supported for device in devices
            ),
            "mode_write_supported": (
                "confirmed"
                if any(
                    device.mode_write_supported.value == "confirmed"
                    for device in devices
                )
                else "unsupported"
            ),
            "mode_write_ready": any(device.mode_write_ready for device in devices),
            "write_block_reason": data.write_block_reason,
            "missing_confirmed_fields": list(
                data.missing_confirmed_fields
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
