"""The sole productive control entity: verified Etherlighting brightness."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RuntimeData
from .brightness import BrightnessWriteOutcome
from .const import (
    ACTIVE_WRITE_BLOCK_REASON,
    BRIGHTNESS_MAXIMUM,
    BRIGHTNESS_MINIMUM,
    BRIGHTNESS_STEP,
    BRIGHTNESS_UNIT,
    CONF_SITE,
    DOMAIN,
    MISSING_CONFIRMED_WRITE_FIELDS,
    WRITE_CAPABILITY_ENABLED,
    WRITE_CAPABILITY_STATE,
    WRITE_DISABLED_MESSAGE,
)
from .repairs import async_sync_repairs


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: RuntimeData = entry.runtime_data
    async_add_entities(
        EtherlightingBrightnessNumber(runtime, entry, device.identifier)
        for device in runtime.coordinator.data.devices
        if device.brightness_read_supported
    )


class EtherlightingBrightnessNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "etherlighting_brightness"
    _attr_native_min_value = BRIGHTNESS_MINIMUM
    _attr_native_max_value = BRIGHTNESS_MAXIMUM
    _attr_native_step = BRIGHTNESS_STEP
    _attr_native_unit_of_measurement = BRIGHTNESS_UNIT

    def __init__(
        self, runtime: RuntimeData, entry: ConfigEntry, device_id: str
    ) -> None:
        super().__init__(runtime.coordinator)
        self._runtime = runtime
        self._entry = entry
        self._device_id = device_id
        self._attr_unique_id = (
            f"{runtime.controller_unique_id}_{device_id}_etherlighting_brightness"
        )

    @property
    def native_value(self) -> float | None:
        device = self.coordinator.device(self._device_id)
        return device.brightness if device is not None else None

    @property
    def available(self) -> bool:
        device = self.coordinator.device(self._device_id)
        return bool(
            self.coordinator.last_update_success
            and device is not None
            and device.brightness_read_supported
            and device.brightness is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        device = self.coordinator.device(self._device_id)
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

    @property
    def device_info(self) -> DeviceInfo:
        device = self.coordinator.device(self._device_id)
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

    async def async_set_native_value(self, value: float) -> None:
        if not WRITE_CAPABILITY_ENABLED:
            raise HomeAssistantError(WRITE_DISABLED_MESSAGE)
        target = int(value)
        if float(target) != float(value):
            raise HomeAssistantError("Brightness must use the confirmed integer step")
        try:
            result = await self._runtime.brightness_service.async_set_brightness(
                self._entry.data[CONF_SITE], self._device_id, target
            )
        except Exception as err:
            raise HomeAssistantError(
                "Etherlighting brightness write failed safely"
            ) from err

        await self.coordinator.async_request_refresh()
        await async_sync_repairs(self.hass, self._entry, self.coordinator.data)
        if result.outcome is not BrightnessWriteOutcome.APPLIED:
            raise HomeAssistantError(
                f"Brightness write was not verified ({result.outcome.value})"
            )
