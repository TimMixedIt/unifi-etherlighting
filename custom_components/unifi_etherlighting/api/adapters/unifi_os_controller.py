"""Read the Network Application version through the confirmed UI endpoint."""

from __future__ import annotations

from ..client import UniFiApiClient
from ..errors import UniFiSchemaError
from ..models import CONFIRMED_CONTROLLER_VERSION_ENDPOINT


class UniFiOsControllerAdapter:
    def __init__(self, client: UniFiApiClient) -> None:
        self._client = client

    async def async_read_network_application_version(self) -> str:
        response = await self._client.async_request_json(
            CONFIRMED_CONTROLLER_VERSION_ENDPOINT.method,
            CONFIRMED_CONTROLLER_VERSION_ENDPOINT.path_template,
            retry_auth_once=True,
        )
        version = response.get("version")
        if not isinstance(version, str) or not version.strip():
            raise UniFiSchemaError("Controller response is missing a valid $.version")
        return version.strip()
