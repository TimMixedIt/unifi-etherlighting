"""Capture-confirmed local UniFi OS authentication and in-memory session state."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

from .errors import (
    UniFiAuthenticationError,
    UniFiPermissionError,
    UniFiSchemaError,
    UniFiTransportError,
)
from .models import CONFIRMED_LOGIN_ENDPOINT, CONFIRMED_LOGOUT_ENDPOINT

CSRF_HEADER_NAME = "X-CSRF-Token"
SESSION_COOKIE_NAME = "TOKEN"


class AuthHttpResponse(Protocol):
    status: int
    headers: Mapping[str, str]

    async def json(self, *, content_type: str | None = None) -> Any: ...


class AuthHttpSession(Protocol):
    def request(
        self, method: str, url: str, **kwargs: Any
    ) -> AbstractAsyncContextManager[AuthHttpResponse]: ...


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return str(value)
    return None


class UniFiAuthSession:
    """Authenticate through the one UI-confirmed UniFi OS flow."""

    def __init__(
        self,
        session: AuthHttpSession,
        controller_base_url: str,
        username: str,
        password: str,
        *,
        timeout_seconds: float = 15.0,
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
        self._username = username
        self._password = password
        self._timeout_seconds = timeout_seconds
        self._authenticated = False
        self._csrf_token: str | None = None

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    @property
    def authenticated(self) -> bool:
        return self._authenticated

    def observe_response_headers(self, headers: Mapping[str, str]) -> None:
        """Retain only the current CSRF value in memory."""
        token = _header(headers, CSRF_HEADER_NAME)
        if token:
            self._csrf_token = token

    async def async_login(self) -> None:
        """Perform exactly one confirmed login request; never log its payload."""
        payload = {
            "username": self._username,
            "password": self._password,
            "rememberMe": False,
            "token": "",
        }
        try:
            async with self._session.request(
                CONFIRMED_LOGIN_ENDPOINT.method,
                self._url(CONFIRMED_LOGIN_ENDPOINT.path_template),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout_seconds,
            ) as response:
                if response.status == 401:
                    raise UniFiAuthenticationError(
                        "Controller rejected the supplied credentials"
                    )
                if response.status == 403:
                    raise UniFiPermissionError("Controller denied the login request")
                if not 200 <= response.status < 300:
                    raise UniFiAuthenticationError(
                        f"Controller login failed with HTTP {response.status}"
                    )
                try:
                    body = await response.json(content_type=None)
                except Exception as err:
                    raise UniFiSchemaError(
                        "Controller login response was not valid JSON"
                    ) from err
                if not isinstance(body, dict):
                    raise UniFiSchemaError(
                        "Controller login response root was not an object"
                    )
                self.observe_response_headers(response.headers)
                set_cookie = _header(response.headers, "Set-Cookie") or ""
                cookie_name = set_cookie.split("=", 1)[0].strip()
                if cookie_name != SESSION_COOKIE_NAME:
                    raise UniFiSchemaError(
                        "Controller login did not establish the confirmed session cookie"
                    )
        except (UniFiAuthenticationError, UniFiPermissionError, UniFiSchemaError):
            self.async_invalidate()
            raise
        except TimeoutError as err:
            self.async_invalidate()
            raise UniFiTransportError(
                "Controller login timed out", request_may_have_been_sent=False
            ) from err
        except OSError as err:
            self.async_invalidate()
            raise UniFiTransportError(
                "Controller login connection failed", request_may_have_been_sent=False
            ) from err
        self._authenticated = True

    async def async_logout(self) -> None:
        """Use the confirmed logout request and discard local session state."""
        if not self._authenticated:
            self.async_invalidate()
            return
        try:
            async with self._session.request(
                CONFIRMED_LOGOUT_ENDPOINT.method,
                self._url(CONFIRMED_LOGOUT_ENDPOINT.path_template),
                headers={"Accept": "application/json"},
                timeout=self._timeout_seconds,
            ) as response:
                if response.status not in {200, 401}:
                    raise UniFiAuthenticationError(
                        f"Controller logout failed with HTTP {response.status}"
                    )
        finally:
            self.async_invalidate()

    async def async_ensure_authenticated(self) -> None:
        if not self._authenticated:
            await self.async_login()

    def async_invalidate(self) -> None:
        """Forget in-memory authentication state without sending a request."""
        self._authenticated = False
        self._csrf_token = None

    async def async_get_csrf_token(self) -> str | None:
        await self.async_ensure_authenticated()
        return self._csrf_token

    def csrf_header(self) -> dict[str, str]:
        return {CSRF_HEADER_NAME: self._csrf_token} if self._csrf_token else {}

    def get_csrf_header(self) -> dict[str, str]:
        """Compatibility alias for the original diagnostic boundary."""
        return self.csrf_header()
