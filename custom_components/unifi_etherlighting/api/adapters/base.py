"""Adapter interface; no generic raw API methods are exposed."""

from __future__ import annotations

from typing import Any, Protocol


class EtherlightingControllerAdapter(Protocol):
    async def async_read_device(
        self, site_id: str, device_id: str
    ) -> dict[str, Any]: ...

    async def async_write_device(
        self, site_id: str, device_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    async def async_get_capabilities(self, device: dict[str, Any]) -> set[str]: ...
