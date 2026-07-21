"""Read the Network Application version through the confirmed UI endpoint."""

from __future__ import annotations

import logging
import re
from typing import Any

from ..client import UniFiApiClient
from ..errors import (
    UniFiVersionSchemaError,
    VersionSchemaMismatchReason,
)
from ..models import CONFIRMED_CONTROLLER_VERSION_ENDPOINT

_LOGGER = logging.getLogger(__name__)
_SAFE_FIELD_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    return "unexpected"


def _safe_top_level_keys(value: Any) -> str:
    if not isinstance(value, dict):
        return "none"
    keys = sorted(
        key
        for key in value
        if isinstance(key, str) and _SAFE_FIELD_NAME.fullmatch(key)
    )
    return ",".join(keys) if keys else "none"


def _safe_version_candidates(value: Any) -> str:
    if not isinstance(value, dict):
        return "none"
    system = value.get("system")
    if not isinstance(system, dict) or "version" not in system:
        return "none"
    return f"$.system.version:{_json_type(system['version'])}"


def _raise_schema_mismatch(
    reason: VersionSchemaMismatchReason, response: Any
) -> None:
    _LOGGER.warning(
        "UniFi version schema mismatch: reason=%s root_type=%s "
        "top_level_keys=%s version_candidates=%s",
        reason.value,
        _json_type(response),
        _safe_top_level_keys(response),
        _safe_version_candidates(response),
    )
    raise UniFiVersionSchemaError(reason)


class UniFiOsControllerAdapter:
    def __init__(self, client: UniFiApiClient) -> None:
        self._client = client

    async def async_read_network_application_version(self) -> str:
        response = await self._client.async_request_json_value(
            CONFIRMED_CONTROLLER_VERSION_ENDPOINT.method,
            CONFIRMED_CONTROLLER_VERSION_ENDPOINT.path_template,
            retry_auth_once=True,
        )
        if not isinstance(response, dict):
            _raise_schema_mismatch(
                VersionSchemaMismatchReason.RESPONSE_ROOT_NOT_OBJECT, response
            )
        if "system" not in response:
            _raise_schema_mismatch(
                VersionSchemaMismatchReason.VERSION_FIELD_MISSING, response
            )
        system = response["system"]
        if not isinstance(system, dict):
            _raise_schema_mismatch(
                VersionSchemaMismatchReason.VERSION_RESPONSE_UNEXPECTED, response
            )
        if "version" not in system:
            _raise_schema_mismatch(
                VersionSchemaMismatchReason.VERSION_FIELD_MISSING, response
            )
        version = system["version"]
        if not isinstance(version, str):
            _raise_schema_mismatch(
                VersionSchemaMismatchReason.VERSION_WRONG_TYPE, response
            )
        if not version.strip():
            _raise_schema_mismatch(
                VersionSchemaMismatchReason.VERSION_EMPTY, response
            )
        return version.strip()
