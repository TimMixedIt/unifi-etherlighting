from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import pytest

from custom_components.unifi_etherlighting.api import client as client_module
from custom_components.unifi_etherlighting.api.adapters.unifi_os_device import (
    UniFiOsDeviceAdapter,
    validate_unifi_write_response,
)
from custom_components.unifi_etherlighting.api.adapters.unifi_os_controller import (
    UniFiOsControllerAdapter,
)
from custom_components.unifi_etherlighting.api.client import UniFiApiClient
from custom_components.unifi_etherlighting.api.errors import (
    UniFiAuthenticationError,
    UniFiPermissionError,
    UniFiResponseError,
)

FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(
        self, status: int, body: Any, headers: dict[str, str] | None = None
    ) -> None:
        self.status = status
        self._body = body
        self.headers = headers or {}

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    async def json(self, *, content_type: str | None = None) -> Any:
        return self._body


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.response


class QueueSession(FakeSession):
    def __init__(self, responses: list[FakeResponse]) -> None:
        super().__init__(responses[0])
        self.responses = responses

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


class FakeAuth:
    def __init__(self) -> None:
        self.logins = 0
        self.invalidations = 0

    async def async_ensure_authenticated(self) -> None:
        return None

    def observe_response_headers(self, headers: dict[str, str]) -> None:
        return None

    def async_invalidate(self) -> None:
        self.invalidations += 1

    async def async_login(self) -> None:
        self.logins += 1


async def csrf_token() -> str:
    return "csrf-value-that-must-not-be-logged"


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_adapter(
    response: dict[str, Any], status: int = 200
) -> tuple[UniFiOsDeviceAdapter, FakeSession]:
    session = FakeSession(FakeResponse(status, response))
    client = UniFiApiClient(session, "https://controller.invalid", csrf_token)
    return UniFiOsDeviceAdapter(client), session


def test_confirmed_proxy_path_uses_put_and_quotes_parameters() -> None:
    assert UniFiOsDeviceAdapter.device_write_path("site/name", "device name/1") == (
        "/proxy/network/api/s/site%2Fname/rest/device/device%20name%2F1"
    )
    assert UniFiOsDeviceAdapter.device_read_path("site/name") == (
        "/proxy/network/api/s/site%2Fname/stat/device"
    )


def test_controller_version_and_device_read_use_only_confirmed_paths() -> None:
    session = FakeSession(FakeResponse(200, {"version": "10.5.62"}))
    client = UniFiApiClient(session, "https://controller.invalid", csrf_token)
    controller = UniFiOsControllerAdapter(client)
    assert asyncio.run(controller.async_read_network_application_version()) == "10.5.62"
    assert session.calls[0]["method"] == "GET"
    assert session.calls[0]["url"].endswith("/proxy/network/v2/api/info")

    device = fixture("device_read_brightness_30.json")
    session.response = FakeResponse(200, {"meta": {"rc": "ok"}, "data": [device]})
    adapter = UniFiOsDeviceAdapter(client)
    assert asyncio.run(adapter.async_read_devices("site_001")) == (device,)
    assert asyncio.run(adapter.async_read_device("site_001", "device_001")) == device
    assert all(call["method"] == "GET" for call in session.calls[1:])
    assert all(
        call["url"].endswith("/proxy/network/api/s/site_001/stat/device")
        for call in session.calls[1:]
    )


def test_missing_version_and_device_schema_fail_closed() -> None:
    for body in ({}, {"version": None}, {"version": ""}):
        session = FakeSession(FakeResponse(200, body))
        controller = UniFiOsControllerAdapter(
            UniFiApiClient(session, "https://controller.invalid", csrf_token)
        )
        with pytest.raises(UniFiResponseError):
            asyncio.run(controller.async_read_network_application_version())

    for body in (
        {},
        {"meta": {"rc": "error"}, "data": []},
        {"meta": {"rc": "ok"}, "data": {}},
    ):
        adapter, _ = make_adapter(body)
        with pytest.raises(UniFiResponseError):
            asyncio.run(adapter.async_read_devices("site_001"))


def test_write_accepts_http_200_and_meta_ok() -> None:
    response = fixture("device_put_response_brightness_35.json")
    adapter, session = make_adapter(response)
    payload = fixture("device_put_brightness_35.json")
    result = asyncio.run(adapter.async_write_device("site_001", "device_001", payload))
    assert result == response
    assert session.calls[0]["method"] == "PUT"
    assert session.calls[0]["url"].endswith(
        "/proxy/network/api/s/site_001/rest/device/device_001"
    )
    assert (
        session.calls[0]["headers"]["X-CSRF-Token"]
        == "csrf-value-that-must-not-be-logged"
    )
    assert session.calls[0]["json"] == payload


def test_http_and_envelope_failures_are_controlled() -> None:
    adapter, _ = make_adapter({"meta": {"rc": "ok"}}, status=500)
    try:
        asyncio.run(adapter.async_write_device("site", "device", {"known": True}))
    except UniFiResponseError:
        pass
    else:
        raise AssertionError("HTTP error must fail")

    for response in ({}, {"meta": {}}, {"meta": {"rc": "error"}}, []):
        try:
            validate_unifi_write_response(response)  # type: ignore[arg-type]
        except UniFiResponseError:
            pass
        else:
            raise AssertionError("Invalid success envelope must fail")

    response = fixture("device_put_response_brightness_35.json")
    validate_unifi_write_response(
        response,
        expected_json_path=("data", "0", "ether_lighting", "brightness"),
        expected_value=35,
    )
    for path, value in (
        (("data", "0", "ether_lighting", "missing"), 35),
        (("data", "0", "ether_lighting", "brightness"), 36),
    ):
        try:
            validate_unifi_write_response(
                response, expected_json_path=path, expected_value=value
            )
        except UniFiResponseError:
            pass
        else:
            raise AssertionError(
                "Missing or mismatched observed response field must fail"
            )


def test_auth_and_permission_errors_are_not_retried() -> None:
    for status, expected in (
        (401, UniFiAuthenticationError),
        (403, UniFiPermissionError),
    ):
        adapter, session = make_adapter({}, status=status)
        try:
            asyncio.run(adapter.async_write_device("site", "device", {"known": True}))
        except expected:
            pass
        else:
            raise AssertionError(f"HTTP {status} must raise {expected.__name__}")
        assert len(session.calls) == 1


def test_safe_read_reauthenticates_once_but_write_never_retries() -> None:
    auth = FakeAuth()
    read_session = QueueSession(
        [FakeResponse(401, {}), FakeResponse(200, {"version": "10.5.62"})]
    )
    client = UniFiApiClient(
        read_session,
        "https://controller.invalid",
        csrf_token,
        auth_session=auth,  # type: ignore[arg-type]
    )
    result = asyncio.run(
        client.async_request_json(
            "GET", "/proxy/network/v2/api/info", retry_auth_once=True
        )
    )
    assert result["version"] == "10.5.62"
    assert len(read_session.calls) == 2
    assert auth.logins == 1

    write_session = QueueSession([FakeResponse(401, {})])
    write_client = UniFiApiClient(
        write_session,
        "https://controller.invalid",
        csrf_token,
        auth_session=auth,  # type: ignore[arg-type]
    )
    with pytest.raises(UniFiAuthenticationError):
        asyncio.run(
            write_client.async_request_json(
                "PUT",
                "/proxy/network/api/s/site/rest/device/device",
                payload={"known": True},
                requires_csrf=True,
            )
        )
    assert len(write_session.calls) == 1


def test_token_and_payload_never_appear_in_debug_logs() -> None:
    response = fixture("device_put_response_brightness_35.json")
    adapter, _ = make_adapter(response)
    messages: list[str] = []

    class Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            messages.append(record.getMessage())

    handler = Handler()
    client_module._LOGGER.addHandler(handler)
    old_level = client_module._LOGGER.level
    client_module._LOGGER.setLevel(logging.DEBUG)
    try:
        asyncio.run(
            adapter.async_write_device(
                "site", "device", {"ether_lighting": {"brightness": 35}}
            )
        )
    finally:
        client_module._LOGGER.setLevel(old_level)
        client_module._LOGGER.removeHandler(handler)
    log_output = "\n".join(messages)
    assert "csrf-value-that-must-not-be-logged" not in log_output
    assert "ether_lighting" not in log_output
