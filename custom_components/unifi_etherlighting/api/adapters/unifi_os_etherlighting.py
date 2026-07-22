"""Confirmed site-wide Etherlighting color settings read and write adapter."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import quote

from ..client import UniFiApiClient
from ..errors import UniFiResponseError, UniFiSchemaError
from ..models import (
    CONFIRMED_ETHERLIGHTING_SETTINGS_READ_ENDPOINT,
    CONFIRMED_ETHERLIGHTING_SETTINGS_WRITE_ENDPOINT,
    CONFIRMED_NETWORK_CONFIGURATION_READ_ENDPOINT,
)
from .unifi_os_device import validate_unifi_write_response

_COLOR_HEX = re.compile(r"^[0-9A-Fa-f]{6}$")


@dataclass(frozen=True, slots=True)
class ColorMapping:
    """One controller color mapping with a normalized RGB hex value."""

    key: str
    raw_color_hex: str


@dataclass(frozen=True, slots=True)
class NetworkLabel:
    """A confirmed Network configuration identifier and display name."""

    key: str
    name: str


@dataclass(frozen=True, slots=True)
class EtherlightingColorSettings:
    """The exact color-setting fields observed in the Network UI."""

    network_defaults: tuple[ColorMapping, ...]
    network_overrides: tuple[ColorMapping, ...]
    speed_defaults: tuple[ColorMapping, ...]
    speed_overrides: tuple[ColorMapping, ...]

    def defaults(self, category: str) -> tuple[ColorMapping, ...]:
        if category == "network":
            return self.network_defaults
        if category == "speed":
            return self.speed_defaults
        raise ValueError("color category must be network or speed")

    def overrides(self, category: str) -> tuple[ColorMapping, ...]:
        if category == "network":
            return self.network_overrides
        if category == "speed":
            return self.speed_overrides
        raise ValueError("color category must be network or speed")

    def effective_color(self, category: str, key: str) -> str:
        defaults = {item.key: item.raw_color_hex for item in self.defaults(category)}
        if key not in defaults:
            raise KeyError("color key is not present in confirmed defaults")
        overrides = {
            item.key: item.raw_color_hex for item in self.overrides(category)
        }
        return overrides.get(key, defaults[key])


def normalize_color_hex(value: object) -> str:
    """Validate the UI's six-digit color format and normalize case."""
    if not isinstance(value, str) or not _COLOR_HEX.fullmatch(value):
        raise UniFiSchemaError("Etherlighting color was not a six-digit RGB hex")
    return value.upper()


def _parse_mapping_list(value: object, path: str) -> tuple[ColorMapping, ...]:
    if not isinstance(value, list):
        raise UniFiSchemaError(f"{path} was not an array")
    parsed: list[ColorMapping] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise UniFiSchemaError(f"{path} contained a non-object")
        key = item.get("key")
        if not isinstance(key, str) or not key or len(key) > 128:
            raise UniFiSchemaError(f"{path} contained an invalid key")
        if key in seen:
            raise UniFiSchemaError(f"{path} contained a duplicate key")
        seen.add(key)
        parsed.append(
            ColorMapping(key, normalize_color_hex(item.get("raw_color_hex")))
        )
    return tuple(parsed)


def parse_etherlighting_settings_response(
    response: object,
) -> EtherlightingColorSettings:
    """Select and validate only the live-observed Etherlighting setting object."""
    if not isinstance(response, dict):
        raise UniFiSchemaError("Settings response root was not an object")
    meta = response.get("meta")
    if not isinstance(meta, dict) or meta.get("rc") != "ok":
        raise UniFiSchemaError("Settings response did not report meta.rc=ok")
    data = response.get("data")
    if not isinstance(data, list) or not all(
        isinstance(item, dict) for item in data
    ):
        raise UniFiSchemaError("Settings response data was not an array of objects")
    matches = [item for item in data if item.get("key") == "ether_lighting"]
    if len(matches) != 1:
        raise UniFiSchemaError(
            "Settings response did not contain one Etherlighting object"
        )
    setting = matches[0]
    return EtherlightingColorSettings(
        network_defaults=_parse_mapping_list(
            setting.get("network_defaults"), "network_defaults"
        ),
        network_overrides=_parse_mapping_list(
            setting.get("network_overrides"), "network_overrides"
        ),
        speed_defaults=_parse_mapping_list(
            setting.get("speed_defaults"), "speed_defaults"
        ),
        speed_overrides=_parse_mapping_list(
            setting.get("speed_overrides"), "speed_overrides"
        ),
    )


def _mapping_payload(items: tuple[ColorMapping, ...]) -> list[dict[str, str]]:
    return [
        {"raw_color_hex": item.raw_color_hex, "key": item.key} for item in items
    ]


class UniFiOsEtherlightingSettingsAdapter:
    """Read and write only the confirmed site-wide color-setting resource."""

    def __init__(self, client: UniFiApiClient) -> None:
        self._client = client

    @staticmethod
    def _path(template: str, site_id: str) -> str:
        if not site_id:
            raise ValueError("site_id is required")
        return template.format(site=quote(site_id, safe=""))

    async def async_read_settings(
        self, site_id: str
    ) -> EtherlightingColorSettings:
        response = await self._client.async_request_json_value(
            CONFIRMED_ETHERLIGHTING_SETTINGS_READ_ENDPOINT.method,
            self._path(
                CONFIRMED_ETHERLIGHTING_SETTINGS_READ_ENDPOINT.path_template,
                site_id,
            ),
            retry_auth_once=True,
        )
        return parse_etherlighting_settings_response(response)

    async def async_read_network_labels(
        self, site_id: str
    ) -> tuple[NetworkLabel, ...]:
        response = await self._client.async_request_json(
            CONFIRMED_NETWORK_CONFIGURATION_READ_ENDPOINT.method,
            self._path(
                CONFIRMED_NETWORK_CONFIGURATION_READ_ENDPOINT.path_template,
                site_id,
            ),
            retry_auth_once=True,
        )
        meta = response.get("meta")
        if not isinstance(meta, dict) or meta.get("rc") != "ok":
            raise UniFiSchemaError(
                "Network configuration response did not report meta.rc=ok"
            )
        data = response.get("data")
        if not isinstance(data, list) or not all(
            isinstance(item, dict) for item in data
        ):
            raise UniFiSchemaError(
                "Network configuration data was not an array of objects"
            )
        labels: list[NetworkLabel] = []
        seen: set[str] = set()
        for item in data:
            key = item.get("_id")
            name = item.get("name")
            if not isinstance(key, str) or not key:
                raise UniFiSchemaError("Network configuration contained an invalid ID")
            if not isinstance(name, str) or not name.strip():
                raise UniFiSchemaError(
                    "Network configuration contained an invalid name"
                )
            if key in seen:
                raise UniFiSchemaError(
                    "Network configuration contained a duplicate ID"
                )
            seen.add(key)
            labels.append(NetworkLabel(key, name.strip()))
        return tuple(labels)

    async def async_write_overrides(
        self,
        site_id: str,
        *,
        network_overrides: tuple[ColorMapping, ...],
        speed_overrides: tuple[ColorMapping, ...],
    ) -> EtherlightingColorSettings:
        payload = {
            "key": "ether_lighting",
            "network_overrides": _mapping_payload(network_overrides),
            "speed_overrides": _mapping_payload(speed_overrides),
        }
        response = await self._client.async_request_json(
            CONFIRMED_ETHERLIGHTING_SETTINGS_WRITE_ENDPOINT.method,
            self._path(
                CONFIRMED_ETHERLIGHTING_SETTINGS_WRITE_ENDPOINT.path_template,
                site_id,
            ),
            payload=payload,
            requires_csrf=(
                CONFIRMED_ETHERLIGHTING_SETTINGS_WRITE_ENDPOINT.requires_csrf
            ),
        )
        validate_unifi_write_response(response)
        try:
            return parse_etherlighting_settings_response(response)
        except UniFiSchemaError as err:
            raise UniFiResponseError(
                "Etherlighting settings write response schema was not confirmed"
            ) from err
