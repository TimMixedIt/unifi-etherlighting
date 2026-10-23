"""Verified Etherlighting display mode control."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RuntimeData
from .const import CONTROL_UNIQUE_ID_SUFFIXES
from .entity import (
    EtherlightingDeviceControl,
    async_finish_verified_write,
    configured_device_ids,
)

MODE_OPTIONS = ["speed", "network"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: RuntimeData = entry.runtime_data
    async_add_entities(
        EtherlightingModeSelect(runtime, entry, device_id)
        for device_id in configured_device_ids(entry)
    )


class EtherlightingModeSelect(EtherlightingDeviceControl, SelectEntity):
    """Expose the two live-confirmed Etherlighting modes."""

    _attr_translation_key = "etherlighting_mode"
    _attr_options = MODE_OPTIONS
    _unique_id_suffix = CONTROL_UNIQUE_ID_SUFFIXES["select"]

    @property
    def current_option(self) -> str | None:
        device = self._device
        return device.mode if device is not None else None

    @property
    def available(self) -> bool:
        device = self._device
        return bool(
            self.coordinator.last_update_success
            and device is not None
            and device.mode_read_supported
            and device.mode in MODE_OPTIONS
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        device = self._device
        return {
            "mode_read_supported": bool(device and device.mode_read_supported),
            "mode_write_supported": (
                device.mode_write_supported.value if device else "unsupported"
            ),
            "mode_write_ready": bool(device and device.mode_write_ready),
        }

    async def async_select_option(self, option: str) -> None:
        if option not in MODE_OPTIONS:
            raise HomeAssistantError("Unsupported Etherlighting mode")
        device = self._device
        self._ensure_write_ready(device is not None and device.mode_write_ready)
        await async_finish_verified_write(
            self,
            self._entry,
            "mode",
            lambda: self._runtime.brightness_service.async_set_mode(
                self._site, self._device_id, option
            ),
        )
