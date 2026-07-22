"""Native Home Assistant color pickers for confirmed Etherlighting palettes."""

from __future__ import annotations

from homeassistant.components.light import ATTR_RGB_COLOR, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RuntimeData
from .brightness import BrightnessWriteOutcome
from .const import CONF_SITE, DOMAIN
from .repairs import async_sync_repairs


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    if len(value) != 6:
        raise ValueError("Color must contain six hexadecimal digits")
    try:
        return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError as err:
        raise ValueError("Color must contain six hexadecimal digits") from err


def _rgb_to_hex(value: object) -> str:
    if (
        not isinstance(value, (tuple, list))
        or len(value) != 3
        or any(
            isinstance(channel, bool)
            or not isinstance(channel, (int, float))
            or int(channel) != channel
            or not 0 <= int(channel) <= 255
            for channel in value
        )
    ):
        raise HomeAssistantError("RGB color must contain three integer channels")
    return "".join(f"{int(channel):02X}" for channel in value)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: RuntimeData = entry.runtime_data
    async_add_entities(
        EtherlightingColorLight(runtime, entry, color.category, color.key)
        for color in runtime.coordinator.data.colors
        if color.read_supported
    )


class EtherlightingColorLight(CoordinatorEntity, LightEntity):
    """An always-on color swatch; only RGB changes are writable."""

    _attr_has_entity_name = True
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_icon = "mdi:palette"

    def __init__(
        self,
        runtime: RuntimeData,
        entry: ConfigEntry,
        category: str,
        key: str,
    ) -> None:
        super().__init__(runtime.coordinator)
        self._runtime = runtime
        self._entry = entry
        self._category = category
        self._key = key
        color = runtime.coordinator.color(category, key)
        label = color.name if color is not None else key
        prefix = "VLAN color" if category == "network" else "Link speed color"
        self._attr_name = f"{prefix} {label}"
        self._attr_unique_id = (
            f"{runtime.controller_unique_id}_etherlighting_color_{category}_{key}"
        )

    @property
    def is_on(self) -> bool | None:
        return True if self.available else None

    @property
    def color_mode(self) -> ColorMode | None:
        return ColorMode.RGB if self.available else None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        color = self.coordinator.color(self._category, self._key)
        if color is None:
            return None
        try:
            return _hex_to_rgb(color.raw_color_hex)
        except ValueError:
            return None

    @property
    def available(self) -> bool:
        color = self.coordinator.color(self._category, self._key)
        return bool(
            self.coordinator.last_update_success
            and color is not None
            and color.read_supported
            and self.rgb_color is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        color = self.coordinator.color(self._category, self._key)
        return {
            "color_category": self._category,
            "color_read_supported": bool(color and color.read_supported),
            "color_write_supported": (
                color.write_supported.value if color else "unsupported"
            ),
            "color_write_ready": bool(
                color and color.write_ready and not color.write_blocked
            ),
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._runtime.controller_unique_id)},
            name="UniFi Etherlighting Controller",
            manufacturer="Ubiquiti",
            model="UniFi OS",
        )

    async def async_turn_on(self, **kwargs: object) -> None:
        if ATTR_RGB_COLOR not in kwargs:
            raise HomeAssistantError(
                "This entity accepts only an RGB color selection"
            )
        unexpected = set(kwargs) - {ATTR_RGB_COLOR, "transition"}
        if unexpected:
            raise HomeAssistantError(
                "Brightness and other light attributes are not supported"
            )
        color = self.coordinator.color(self._category, self._key)
        if color is None or not color.write_ready or color.write_blocked:
            raise HomeAssistantError("Etherlighting color writes are not ready")
        requested = _rgb_to_hex(kwargs[ATTR_RGB_COLOR])
        try:
            result = await self._runtime.color_service.async_set_color(
                self._entry.data[CONF_SITE],
                color.witness_device_id,
                self._category,
                self._key,
                requested,
            )
        except Exception as err:
            raise HomeAssistantError(
                "Etherlighting color write failed safely"
            ) from err

        await self.coordinator.async_request_refresh()
        await async_sync_repairs(self.hass, self._entry, self.coordinator.data)
        if result.outcome is not BrightnessWriteOutcome.APPLIED:
            raise HomeAssistantError(
                f"Etherlighting color write was not verified ({result.outcome.value})"
            )

    async def async_turn_off(self, **kwargs: object) -> None:
        raise HomeAssistantError(
            "Etherlighting color swatches cannot be turned off"
        )
