"""Verified Breathing Mode control."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RuntimeData
from .const import CONTROL_UNIQUE_ID_SUFFIXES
from .entity import (
    EtherlightingDeviceControl,
    async_finish_verified_write,
    configured_device_ids,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: RuntimeData = entry.runtime_data
    async_add_entities(
        EtherlightingBreathingSwitch(runtime, entry, device_id)
        for device_id in configured_device_ids(entry)
    )


class EtherlightingBreathingSwitch(EtherlightingDeviceControl, SwitchEntity):
    """Map the confirmed steady/breath values to a switch."""

    _attr_translation_key = "breathing_mode"
    _unique_id_suffix = CONTROL_UNIQUE_ID_SUFFIXES["switch"]

    @property
    def is_on(self) -> bool | None:
        device = self._device
        if device is None or device.behavior is None:
            return None
        return device.behavior == "breath"

    @property
    def available(self) -> bool:
        device = self._device
        return bool(
            self.coordinator.last_update_success
            and device is not None
            and device.behavior_read_supported
            and device.behavior is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        device = self._device
        return {
            "behavior_read_supported": bool(
                device and device.behavior_read_supported
            ),
            "behavior_write_supported": (
                device.behavior_write_supported.value if device else "unsupported"
            ),
            "behavior_write_ready": bool(device and device.behavior_write_ready),
        }

    async def _async_set_behavior(self, behavior: str) -> None:
        device = self._device
        self._ensure_write_ready(device is not None and device.behavior_write_ready)
        await async_finish_verified_write(
            self,
            self._entry,
            "Breathing Mode",
            lambda: self._runtime.brightness_service.async_set_behavior(
                self._site, self._device_id, behavior
            ),
        )

    async def async_turn_on(self, **kwargs: object) -> None:
        await self._async_set_behavior("breath")

    async def async_turn_off(self, **kwargs: object) -> None:
        await self._async_set_behavior("steady")
