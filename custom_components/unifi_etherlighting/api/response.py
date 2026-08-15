"""Bounded JSON decoding for untrusted controller responses."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any, Protocol

from .errors import UniFiSchemaError

MAX_JSON_RESPONSE_BYTES = 16 * 1024 * 1024


class ResponseContent(Protocol):
    """The streaming response surface used by the controller clients."""

    def iter_chunked(self, size: int) -> AsyncIterator[bytes]: ...


class BoundedJsonResponse(Protocol):
    """Response fields required for bounded JSON decoding."""

    headers: Mapping[str, str]
    content: ResponseContent


async def async_read_json(response: BoundedJsonResponse) -> Any:
    """Decode JSON without allowing an unbounded controller response."""
    content_length = response.headers.get("Content-Length")
    if content_length and content_length.isdecimal():
        try:
            declared_length = int(content_length)
        except ValueError:
            raise UniFiSchemaError("Controller response size was invalid") from None
        if declared_length > MAX_JSON_RESPONSE_BYTES:
            raise UniFiSchemaError("Controller response exceeded the safe size limit")

    body = bytearray()
    async for chunk in response.content.iter_chunked(64 * 1024):
        body.extend(chunk)
        if len(body) > MAX_JSON_RESPONSE_BYTES:
            raise UniFiSchemaError("Controller response exceeded the safe size limit")
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
        raise UniFiSchemaError("Controller response was not valid JSON") from None
