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
    BRIGHTNESS_MAXIMUM,
    BRIGHTNESS_MINIMUM,
    BRIGHTNESS_STEP,
    BRIGHTNESS_UNIT,
    CONF_SITE,
    DOMAIN,
)
from .repairs import async_sync_repairs


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: RuntimeData = entry.runtime_data
    async_add_entities(
        EtherlightingBrightnessNumber(runtime, entry, device.identifier)
        for device in runtime.coordinator.data.devices
        if device.brightness_confirmed
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
            and device.brightness_confirmed
            and device.brightness is not None
        )

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
