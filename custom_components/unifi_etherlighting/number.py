"""Verified Etherlighting brightness control."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RuntimeData
from .const import (
    ACTIVE_WRITE_BLOCK_REASON,
    BRIGHTNESS_MAXIMUM,
    BRIGHTNESS_MINIMUM,
    BRIGHTNESS_STEP,
    BRIGHTNESS_UNIT,
    CONTROL_UNIQUE_ID_SUFFIXES,
    MISSING_CONFIRMED_WRITE_FIELDS,
    WRITE_CAPABILITY_STATE,
)
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
        EtherlightingBrightnessNumber(runtime, entry, device_id)
        for device_id in configured_device_ids(entry)
    )


class EtherlightingBrightnessNumber(EtherlightingDeviceControl, NumberEntity):
    _attr_translation_key = "etherlighting_brightness"
    _attr_native_min_value = BRIGHTNESS_MINIMUM
    _attr_native_max_value = BRIGHTNESS_MAXIMUM
    _attr_native_step = BRIGHTNESS_STEP
    _attr_native_unit_of_measurement = BRIGHTNESS_UNIT
    _unique_id_suffix = CONTROL_UNIQUE_ID_SUFFIXES["number"]

    @property
    def native_value(self) -> float | None:
        device = self._device
        return device.brightness if device is not None else None

    @property
    def available(self) -> bool:
        device = self._device
        return bool(
            self.coordinator.last_update_success
            and device is not None
            and device.brightness_read_supported
            and device.brightness is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        device = self._device
        return {
            "brightness_read_supported": bool(
                device and device.brightness_read_supported
            ),
            "brightness_write_supported": (
                device.brightness_write_supported.value if device else "unsupported"
            ),
            "brightness_write_ready": bool(
                device and device.brightness_write_ready
            ),
            "write_capability": WRITE_CAPABILITY_STATE,
            "write_block_reason": ACTIVE_WRITE_BLOCK_REASON,
            "missing_confirmed_fields": list(MISSING_CONFIRMED_WRITE_FIELDS),
        }

    async def async_set_native_value(self, value: float) -> None:
        device = self._device
        self._ensure_write_ready(device is not None and device.brightness_write_ready)
        target = int(value)
        if float(target) != float(value):
            raise HomeAssistantError("Brightness must use the confirmed integer step")
        await async_finish_verified_write(
            self,
            self._entry,
            "brightness",
            lambda: self._runtime.control_service.async_set_brightness(
                self._site, self._device_id, target
            ),
        )
