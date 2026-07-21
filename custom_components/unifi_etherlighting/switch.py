"""Verified Breathing Mode control."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RuntimeData
from .brightness import BrightnessWriteOutcome
from .const import CONF_SITE, DOMAIN, WRITE_CAPABILITY_ENABLED
from .repairs import async_sync_repairs


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: RuntimeData = entry.runtime_data
    async_add_entities(
        EtherlightingBreathingSwitch(runtime, entry, device.identifier)
        for device in runtime.coordinator.data.devices
        if device.behavior_read_supported
    )


class EtherlightingBreathingSwitch(CoordinatorEntity, SwitchEntity):
    """Map the confirmed steady/breath values to a switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "breathing_mode"

    def __init__(
        self, runtime: RuntimeData, entry: ConfigEntry, device_id: str
    ) -> None:
        super().__init__(runtime.coordinator)
        self._runtime = runtime
        self._entry = entry
        self._device_id = device_id
        self._attr_unique_id = (
            f"{runtime.controller_unique_id}_{device_id}_etherlighting_breathing"
        )

    @property
    def is_on(self) -> bool | None:
        device = self.coordinator.device(self._device_id)
        if device is None or device.behavior is None:
            return None
        return device.behavior == "breath"

    @property
    def available(self) -> bool:
        device = self.coordinator.device(self._device_id)
        return bool(
            self.coordinator.last_update_success
            and device is not None
            and device.behavior_read_supported
            and device.behavior is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        device = self.coordinator.device(self._device_id)
        return {
            "behavior_read_supported": bool(
                device and device.behavior_read_supported
            ),
            "behavior_write_supported": (
                device.behavior_write_supported.value if device else "unsupported"
            ),
            "behavior_write_ready": bool(device and device.behavior_write_ready),
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

    async def _async_set_behavior(self, behavior: str) -> None:
        if not WRITE_CAPABILITY_ENABLED:
            raise HomeAssistantError("Etherlighting writes are not ready")
        try:
            result = await self._runtime.brightness_service.async_set_behavior(
                self._entry.data[CONF_SITE], self._device_id, behavior
            )
        except Exception as err:
            raise HomeAssistantError(
                "Etherlighting Breathing Mode write failed safely"
            ) from err

        await self.coordinator.async_request_refresh()
        await async_sync_repairs(self.hass, self._entry, self.coordinator.data)
        if result.outcome is not BrightnessWriteOutcome.APPLIED:
            raise HomeAssistantError(
                f"Breathing Mode write was not verified ({result.outcome.value})"
            )

    async def async_turn_on(self, **kwargs: object) -> None:
        await self._async_set_behavior("breath")

    async def async_turn_off(self, **kwargs: object) -> None:
        await self._async_set_behavior("steady")
