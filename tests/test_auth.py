from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from custom_components.unifi_etherlighting.api.auth import UniFiAuthSession
from custom_components.unifi_etherlighting.api.errors import UniFiAuthenticationError


class FakeResponse:
    def __init__(
        self, status: int, body: Any, headers: dict[str, str] | None = None
    ) -> None:
        self.status = status
        self.body = body
        self.headers = headers or {}

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def json(self, *, content_type: str | None = None) -> Any:
        return self.body


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


def test_login_uses_only_confirmed_route_and_fields() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {"profile": "omitted"},
                {"Set-Cookie": "TOKEN=synthetic; Secure", "X-CSRF-Token": "synthetic"},
            )
        ]
    )
    auth = UniFiAuthSession(
        session, "https://controller.invalid", "test-user", "test-pass"
    )
    asyncio.run(auth.async_login())
    assert auth.authenticated
    assert len(session.calls) == 1
    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["url"].endswith("/api/auth/login")
    assert set(session.calls[0]["json"]) == {
        "username",
        "password",
        "rememberMe",
        "token",
    }
    assert auth.csrf_header() == {"X-CSRF-Token": "synthetic"}
    assert not hasattr(auth, "cookie_value")


def test_invalid_auth_does_not_try_alternate_routes() -> None:
    session = FakeSession([FakeResponse(401, {}, {})])
    auth = UniFiAuthSession(session, "https://controller.invalid", "test-user", "wrong")
    with pytest.raises(UniFiAuthenticationError):
        asyncio.run(auth.async_login())
    assert len(session.calls) == 1
    assert session.calls[0]["url"].endswith("/api/auth/login")


def test_logout_uses_confirmed_route_and_discards_in_memory_state() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {},
                {"Set-Cookie": "TOKEN=synthetic", "X-CSRF-Token": "synthetic"},
            ),
            FakeResponse(200, None, {}),
        ]
    )
    auth = UniFiAuthSession(
        session, "https://controller.invalid", "test-user", "test-pass"
    )
    asyncio.run(auth.async_login())
    asyncio.run(auth.async_logout())
    assert session.calls[-1]["method"] == "POST"
    assert session.calls[-1]["url"].endswith("/api/auth/logout")
    assert not auth.authenticated
    assert auth.csrf_header() == {}


def test_credentials_and_csrf_are_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    session = FakeSession(
        [
            FakeResponse(
                200, {}, {"Set-Cookie": "TOKEN=synthetic", "X-CSRF-Token": "synthetic"}
            )
        ]
    )
    auth = UniFiAuthSession(
        session, "https://controller.invalid", "private-user", "private-pass"
    )
    asyncio.run(auth.async_login())
    output = caplog.text
    assert "private-user" not in output
    assert "private-pass" not in output
    assert "synthetic" not in output
