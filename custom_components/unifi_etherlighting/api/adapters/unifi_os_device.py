"""Capture-confirmed UniFi OS Device read and write endpoints."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ..client import UniFiApiClient
from ...const import WRITE_BLOCK_REASON, WRITE_CAPABILITY_ENABLED
from ..errors import (
    DeviceNotFoundError,
    UniFiResponseError,
    UniFiSchemaError,
    WriteCapabilityUnavailableError,
)
from ..models import CONFIRMED_DEVICE_READ_ENDPOINT, CONFIRMED_DEVICE_WRITE_ENDPOINT


def _get_response_path(data: Any, path: tuple[str, ...]) -> Any:
    current = data
    for segment in path:
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif (
            isinstance(current, list)
            and segment.isdecimal()
            and int(segment) < len(current)
        ):
            current = current[int(segment)]
        else:
            raise UniFiResponseError(
                f"Controller response is missing expected path: {'.'.join(path)}"
            )
    return current


def validate_unifi_write_response(
    response: dict[str, Any],
    *,
    expected_json_path: tuple[str, ...] | None = None,
    expected_value: Any | None = None,
) -> None:
    """Accept only the exact success envelope observed in the real capture."""
    if not isinstance(response, dict):
        raise UniFiResponseError("Controller write response was not an object")
    meta = response.get("meta")
    if not isinstance(meta, dict) or "rc" not in meta:
        raise UniFiResponseError("Controller write response is missing meta.rc")
    if meta["rc"] != "ok":
        raise UniFiResponseError("Controller write response did not report meta.rc=ok")
    if expected_json_path is not None:
        observed = _get_response_path(response, expected_json_path)
        if observed != expected_value:
            raise UniFiResponseError(
                "Controller write response did not return the expected value"
            )


class UniFiOsDeviceAdapter:
    """Read Devices and send only an explicit, projected Device payload."""

    def __init__(self, client: UniFiApiClient) -> None:
        self._client = client

    @staticmethod
    def device_write_path(site_id: str, device_id: str) -> str:
        if not site_id or not device_id:
            raise ValueError("site_id and device_id are required")
        site = quote(site_id, safe="")
        device = quote(device_id, safe="")
        return CONFIRMED_DEVICE_WRITE_ENDPOINT.path_template.format(
            site=site, device=device
        )

    @staticmethod
    def device_read_path(site_id: str) -> str:
        if not site_id:
            raise ValueError("site_id is required")
        return CONFIRMED_DEVICE_READ_ENDPOINT.path_template.format(
            site=quote(site_id, safe="")
        )

    async def async_read_devices(self, site_id: str) -> tuple[dict[str, Any], ...]:
        response = await self._client.async_request_json(
            CONFIRMED_DEVICE_READ_ENDPOINT.method,
            self.device_read_path(site_id),
            retry_auth_once=True,
        )
        meta = response.get("meta")
        if not isinstance(meta, dict) or meta.get("rc") != "ok":
            raise UniFiSchemaError("Device read response did not report meta.rc=ok")
        data = response.get("data")
        if not isinstance(data, list) or not all(
            isinstance(item, dict) for item in data
        ):
            raise UniFiSchemaError(
                "Device read response $.data was not an array of objects"
            )
        return tuple(data)

    async def async_read_device(self, site_id: str, device_id: str) -> dict[str, Any]:
        if not device_id:
            raise ValueError("device_id is required")
        matches = [
            device
            for device in await self.async_read_devices(site_id)
            if device.get("_id") == device_id
        ]
        if len(matches) != 1:
            qualifier = "not found" if not matches else "not unique"
            raise DeviceNotFoundError(f"Selected Device was {qualifier}")
        return matches[0]

    async def async_write_device(
        self, site_id: str, device_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if not WRITE_CAPABILITY_ENABLED:
            raise WriteCapabilityUnavailableError(WRITE_BLOCK_REASON)
        if not isinstance(payload, dict) or not payload:
            raise ValueError(
                "A non-empty, caller-provided complete device payload is required"
            )
        response = await self._client.async_request_json(
            CONFIRMED_DEVICE_WRITE_ENDPOINT.method,
            self.device_write_path(site_id, device_id),
            payload=payload,
            requires_csrf=CONFIRMED_DEVICE_WRITE_ENDPOINT.requires_csrf,
        )
        validate_unifi_write_response(response)
        return response

    async def async_get_capabilities(self, device: dict[str, Any]) -> set[str]:
        if not isinstance(device, dict):
            return set()
        ether_lighting = device.get("ether_lighting")
        if (
            device.get("model") == "USWED72"
            and device.get("version") == "7.4.1.16850"
            and isinstance(ether_lighting, dict)
            and isinstance(ether_lighting.get("brightness"), int)
        ):
            return {"brightness"}
        return set()
