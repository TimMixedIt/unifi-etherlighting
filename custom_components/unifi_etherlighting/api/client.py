"""Narrow JSON transport for capture-confirmed UniFi OS endpoints."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Any, Optional, Protocol
from urllib.parse import urlsplit, urlunsplit

from .errors import (
    UniFiAuthenticationError,
    UniFiPermissionError,
    UniFiResponseError,
    UniFiSchemaError,
    UniFiTransportError,
)

if TYPE_CHECKING:
    from .auth import UniFiAuthSession

_LOGGER = logging.getLogger(__name__)


class HttpResponse(Protocol):
    status: int
    headers: Mapping[str, str]

    async def json(self, *, content_type: str | None = None) -> Any: ...


class HomeAssistantHttpSession(Protocol):
    def request(
        self, method: str, url: str, **kwargs: Any
    ) -> AbstractAsyncContextManager[HttpResponse]: ...


CsrfTokenProvider = Callable[[], Awaitable[Optional[str]]]


class UniFiApiClient:
    """Authenticated transport with one safe read reauthentication attempt."""

    def __init__(
        self,
        session: HomeAssistantHttpSession,
        controller_base_url: str,
        csrf_token_provider: CsrfTokenProvider,
        timeout_seconds: float = 15.0,
        *,
        auth_session: UniFiAuthSession | None = None,
    ) -> None:
        parsed = urlsplit(controller_base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                "controller_base_url must be an absolute HTTP(S) controller URL"
            )
        self._session = session
        self._base_url = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")
        )
        self._csrf_token_provider = csrf_token_provider
        self._timeout_seconds = timeout_seconds
        self._auth = auth_session

    def _url_for_relative_path(self, relative_path: str) -> str:
        parsed = urlsplit(relative_path)
        if (
            not relative_path.startswith("/")
            or relative_path.startswith("//")
            or parsed.scheme
            or parsed.netloc
        ):
            raise ValueError("Only a relative controller path is allowed")
        return f"{self._base_url}{relative_path}"

    async def _async_request_once(
        self,
        method: str,
        relative_path: str,
        *,
        payload: dict[str, Any] | None,
        requires_csrf: bool,
    ) -> Any:
        headers: dict[str, str] = {"Accept": "application/json"}
        if requires_csrf:
            token = await self._csrf_token_provider()
            if not token:
                raise UniFiAuthenticationError(
                    "A CSRF token is required for this operation"
                )
            headers["X-CSRF-Token"] = token

        try:
            async with self._session.request(
                method,
                self._url_for_relative_path(relative_path),
                headers=headers,
                json=payload,
                timeout=self._timeout_seconds,
            ) as response:
                if self._auth is not None:
                    self._auth.observe_response_headers(response.headers)
                status = response.status
                if status == 401:
                    raise UniFiAuthenticationError(
                        "Controller authentication failed (401)"
                    )
                if status == 403:
                    raise UniFiPermissionError("Controller permission denied (403)")
                if not 200 <= status < 300:
                    raise UniFiResponseError(f"Controller returned HTTP {status}")
                try:
                    response_data = await response.json(content_type=None)
                except Exception as err:
                    raise UniFiSchemaError(
                        "Controller response was not valid JSON"
                    ) from err
        except (UniFiAuthenticationError, UniFiPermissionError, UniFiResponseError):
            raise
        except TimeoutError as err:
            raise UniFiTransportError(
                "Controller request timed out",
                request_may_have_been_sent=method.upper() not in {"GET", "HEAD"},
            ) from err
        except OSError as err:
            raise UniFiTransportError(
                "Controller connection failed",
                request_may_have_been_sent=method.upper() not in {"GET", "HEAD"},
            ) from err

        _LOGGER.debug(
            "UniFi controller request succeeded: %s (HTTP %s)", method, status
        )
        return response_data

    async def async_request_json_value(
        self,
        method: str,
        relative_path: str,
        *,
        payload: dict[str, Any] | None = None,
        requires_csrf: bool = False,
        authenticated: bool = True,
        retry_auth_once: bool = False,
    ) -> Any:
        """Request a JSON value without trying alternate routes."""
        if authenticated and self._auth is not None:
            await self._auth.async_ensure_authenticated()
        try:
            return await self._async_request_once(
                method, relative_path, payload=payload, requires_csrf=requires_csrf
            )
        except (UniFiAuthenticationError, UniFiPermissionError):
            if (
                not retry_auth_once
                or method.upper() not in {"GET", "HEAD"}
                or self._auth is None
            ):
                raise
            self._auth.async_invalidate()
            await self._auth.async_login()
            return await self._async_request_once(
                method, relative_path, payload=payload, requires_csrf=requires_csrf
            )

    async def async_request_json(
        self,
        method: str,
        relative_path: str,
        *,
        payload: dict[str, Any] | None = None,
        requires_csrf: bool = False,
        authenticated: bool = True,
        retry_auth_once: bool = False,
    ) -> dict[str, Any]:
        """Request a JSON object without retrying writes or alternate routes."""
        response_data = await self.async_request_json_value(
            method,
            relative_path,
            payload=payload,
            requires_csrf=requires_csrf,
            authenticated=authenticated,
            retry_auth_once=retry_auth_once,
        )
        if not isinstance(response_data, dict):
            raise UniFiSchemaError("Controller response root was not an object")
        return response_data
