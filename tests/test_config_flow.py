from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unifi_etherlighting.api.errors import (
    UniFiAuthenticationError,
    UniFiPermissionError,
    UniFiResponseError,
    UniFiSchemaError,
    UniFiVersionSchemaError,
    VersionSchemaMismatchReason,
)
from custom_components.unifi_etherlighting.config_flow import (
    ConfigFlow,
    ValidationStage,
    ValidationStageError,
    _log_stage_failure,
)
from custom_components.unifi_etherlighting.const import DOMAIN

FIXTURES = Path(__file__).parent / "fixtures"

CONNECTION = {
    "host": "controller.invalid",
    "port": 443,
    "use_ssl": True,
    "verify_ssl": True,
    "username": "user",
    "password": "secret",
    "site": "site_001",
}
DEVICE = json.loads((FIXTURES / "device_read_brightness_30.json").read_text())


async def _start_validated_flow(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONNECTION
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "devices"
    return result


async def test_user_flow_validates_and_selects_device(hass) -> None:
    with patch(
        "custom_components.unifi_etherlighting.config_flow.ConfigFlow._async_validate_connection",
        new=AsyncMock(return_value=(DEVICE,)),
    ) as validate:
        result = await _start_validated_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_ids": ["device_001"]}
        )
    assert validate.await_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "controller.invalid:443"
    assert result["data"]["site"] == "site_001"
    assert result["data"]["device_ids"] == ["device_001"]
    assert "secret" not in result["title"]


async def test_duplicate_controller_is_aborted(hass) -> None:
    with patch(
        "custom_components.unifi_etherlighting.config_flow.ConfigFlow._async_validate_connection",
        new=AsyncMock(return_value=(DEVICE,)),
    ):
        first = await _start_validated_flow(hass)
        first = await hass.config_entries.flow.async_configure(
            first["flow_id"], {"device_ids": ["device_001"]}
        )
        assert first["type"] is FlowResultType.CREATE_ENTRY

        second = await _start_validated_flow(hass)
        second = await hass.config_entries.flow.async_configure(
            second["flow_id"], {"device_ids": ["device_001"]}
        )
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_configured"


async def test_reauth_updates_only_credentials_and_reloads(hass) -> None:
    entry = MockConfigEntry(
        version=2,
        minor_version=1,
        domain=DOMAIN,
        title="UniFi Etherlighting",
        data={
            **CONNECTION,
            "username": "old_user",
            "password": "old_password",
            "device_ids": ["device_001"],
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="controller.invalid:443",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.unifi_etherlighting.config_flow.ConfigFlow._async_validate_connection",
        new=AsyncMock(return_value=(DEVICE,)),
    ) as validate:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=dict(entry.data),
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "new_user", "password": "new_password"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["username"] == "new_user"
    assert entry.data["password"] == "new_password"
    assert entry.data["site"] == "site_001"
    assert entry.data["device_ids"] == ["device_001"]
    validated = validate.await_args.args[0]
    assert validated["username"] == "new_user"
    assert validated["password"] == "new_password"


async def test_reauth_rejects_bad_credentials_without_updating_entry(hass) -> None:
    entry = MockConfigEntry(
        version=2,
        minor_version=1,
        domain=DOMAIN,
        title="UniFi Etherlighting",
        data={
            **CONNECTION,
            "device_ids": ["device_001"],
        },
        source=config_entries.SOURCE_USER,
        options={},
        unique_id="controller.invalid:443",
    )
    entry.add_to_hass(hass)
    original = dict(entry.data)

    with patch(
        "custom_components.unifi_etherlighting.config_flow.ConfigFlow._async_validate_connection",
        new=AsyncMock(
            side_effect=ValidationStageError(
                ValidationStage.LOGIN,
                UniFiAuthenticationError("synthetic rejection"),
            )
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=dict(entry.data),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user", "password": "wrong"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data == original


async def test_no_compatible_devices_stays_in_user_step(hass) -> None:
    with patch(
        "custom_components.unifi_etherlighting.config_flow.ConfigFlow._async_validate_connection",
        new=AsyncMock(side_effect=Exception("safe synthetic failure")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=CONNECTION,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_permission_failure_is_not_reported_as_bad_credentials(hass) -> None:
    with patch(
        "custom_components.unifi_etherlighting.config_flow.ConfigFlow._async_validate_connection",
        new=AsyncMock(side_effect=UniFiPermissionError("synthetic denial")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=CONNECTION,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "insufficient_permissions"}


async def test_successful_validation_is_not_masked_by_logout_failure(
    hass, caplog: pytest.LogCaptureFixture
) -> None:
    """A cleanup failure after successful reads must not look like bad credentials."""
    caplog.set_level(
        logging.WARNING, logger="custom_components.unifi_etherlighting.config_flow"
    )
    auth = MagicMock()
    auth.authenticated = True
    auth.async_login = AsyncMock()
    auth.async_logout = AsyncMock(
        side_effect=UniFiAuthenticationError(
            "Controller logout failed (HTTP 403 sensitive diagnostic marker)"
        )
    )
    auth.async_get_csrf_token = AsyncMock(return_value=None)

    controller = MagicMock()
    controller.async_read_network_application_version = AsyncMock(
        return_value="10.5.66"
    )
    devices = MagicMock()
    devices.async_read_devices = AsyncMock(return_value=[DEVICE])

    with (
        patch(
            "custom_components.unifi_etherlighting.config_flow.async_create_clientsession"
        ),
        patch(
            "custom_components.unifi_etherlighting.config_flow.UniFiAuthSession",
            return_value=auth,
        ),
        patch("custom_components.unifi_etherlighting.config_flow.UniFiApiClient"),
        patch(
            "custom_components.unifi_etherlighting.config_flow.UniFiOsControllerAdapter",
            return_value=controller,
        ),
        patch(
            "custom_components.unifi_etherlighting.config_flow.UniFiOsDeviceAdapter",
            return_value=devices,
        ),
    ):
        flow = ConfigFlow()
        flow.hass = hass
        compatible = await flow._async_validate_connection(CONNECTION)

    assert compatible == (DEVICE,)
    auth.async_logout.assert_awaited_once()
    auth.async_invalidate.assert_called_once()
    assert "stage=logout" in caplog.text
    assert "category=validation_logout" in caplog.text
    assert "http_status=403" in caplog.text
    assert "sensitive diagnostic marker" not in caplog.text


async def test_failed_version_read_stops_before_device_read_or_write(hass) -> None:
    auth = MagicMock()
    auth.authenticated = True
    auth.async_login = AsyncMock()
    auth.async_logout = AsyncMock()
    auth.async_get_csrf_token = AsyncMock(return_value=None)

    controller = MagicMock()
    controller.async_read_network_application_version = AsyncMock(
        side_effect=UniFiVersionSchemaError(
            VersionSchemaMismatchReason.VERSION_FIELD_MISSING
        )
    )
    devices = MagicMock()
    devices.async_read_devices = AsyncMock()
    devices.async_write_device = AsyncMock()

    with (
        patch(
            "custom_components.unifi_etherlighting.config_flow.async_create_clientsession"
        ),
        patch(
            "custom_components.unifi_etherlighting.config_flow.UniFiAuthSession",
            return_value=auth,
        ),
        patch("custom_components.unifi_etherlighting.config_flow.UniFiApiClient"),
        patch(
            "custom_components.unifi_etherlighting.config_flow.UniFiOsControllerAdapter",
            return_value=controller,
        ),
        patch(
            "custom_components.unifi_etherlighting.config_flow.UniFiOsDeviceAdapter",
            return_value=devices,
        ),
    ):
        flow = ConfigFlow()
        flow.hass = hass
        with pytest.raises(ValidationStageError) as caught:
            await flow._async_validate_connection(CONNECTION)

    assert caught.value.stage is ValidationStage.VERSION_READ
    assert isinstance(caught.value.cause, UniFiVersionSchemaError)
    auth.async_login.assert_awaited_once()
    devices.async_read_devices.assert_not_awaited()
    devices.async_write_device.assert_not_awaited()


@pytest.mark.parametrize(
    "stage",
    [
        ValidationStage.SESSION,
        ValidationStage.LOGIN,
        ValidationStage.VERSION_READ,
        ValidationStage.DEVICE_READ,
        ValidationStage.COMPATIBILITY,
    ],
)
async def test_unexpected_validation_error_preserves_stage(hass, stage) -> None:
    session = MagicMock()
    auth = MagicMock()
    auth.authenticated = stage not in {ValidationStage.SESSION, ValidationStage.LOGIN}
    auth.async_login = AsyncMock()
    auth.async_logout = AsyncMock()
    auth.async_get_csrf_token = AsyncMock(return_value=None)
    controller = MagicMock()
    controller.async_read_network_application_version = AsyncMock(
        return_value="10.5.62"
    )
    devices = MagicMock()
    devices.async_read_devices = AsyncMock(return_value=[DEVICE])

    if stage is ValidationStage.LOGIN:
        auth.async_login.side_effect = RuntimeError("sensitive diagnostic marker")
    elif stage is ValidationStage.VERSION_READ:
        controller.async_read_network_application_version.side_effect = RuntimeError(
            "sensitive diagnostic marker"
        )
    elif stage is ValidationStage.DEVICE_READ:
        devices.async_read_devices.side_effect = RuntimeError(
            "sensitive diagnostic marker"
        )

    session_factory = MagicMock(return_value=session)
    if stage is ValidationStage.SESSION:
        session_factory.side_effect = RuntimeError("sensitive diagnostic marker")

    compatibility = MagicMock(return_value=True)
    if stage is ValidationStage.COMPATIBILITY:
        compatibility.side_effect = RuntimeError("sensitive diagnostic marker")

    with (
        patch(
            "custom_components.unifi_etherlighting.config_flow.async_create_clientsession",
            session_factory,
        ),
        patch(
            "custom_components.unifi_etherlighting.config_flow.UniFiAuthSession",
            return_value=auth,
        ),
        patch("custom_components.unifi_etherlighting.config_flow.UniFiApiClient"),
        patch(
            "custom_components.unifi_etherlighting.config_flow.UniFiOsControllerAdapter",
            return_value=controller,
        ),
        patch(
            "custom_components.unifi_etherlighting.config_flow.UniFiOsDeviceAdapter",
            return_value=devices,
        ),
        patch(
            "custom_components.unifi_etherlighting.config_flow.runtime_contract_is_supported",
            compatibility,
        ),
    ):
        flow = ConfigFlow()
        flow.hass = hass
        with pytest.raises(ValidationStageError) as caught:
            await flow._async_validate_connection(CONNECTION)

    assert caught.value.stage is stage
    assert str(caught.value) == f"Config-flow validation failed at stage={stage.value}"
    assert "sensitive diagnostic marker" not in str(caught.value)


@pytest.mark.parametrize(
    ("stage", "error_key"),
    [
        (ValidationStage.SESSION, "validation_session"),
        (ValidationStage.LOGIN, "validation_login"),
        (ValidationStage.VERSION_READ, "validation_version_read"),
        (ValidationStage.DEVICE_READ, "validation_device_read"),
        (ValidationStage.COMPATIBILITY, "validation_compatibility"),
    ],
)
async def test_stage_error_is_exposed_without_cause_details(
    hass,
    caplog: pytest.LogCaptureFixture,
    stage: ValidationStage,
    error_key: str,
) -> None:
    caplog.set_level(
        logging.WARNING, logger="custom_components.unifi_etherlighting.config_flow"
    )
    staged_error = ValidationStageError(
        stage, UniFiSchemaError("sensitive diagnostic marker")
    )
    with patch(
        "custom_components.unifi_etherlighting.config_flow.ConfigFlow._async_validate_connection",
        new=AsyncMock(side_effect=staged_error),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=CONNECTION,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}
    assert f"stage={stage.value}" in caplog.text
    assert f"category={error_key}" in caplog.text
    assert "exception_type=UniFiSchemaError" in caplog.text
    assert "sensitive diagnostic marker" not in caplog.text


@pytest.mark.parametrize(
    ("stage", "cause", "error_key"),
    [
        (
            ValidationStage.LOGIN,
            UniFiAuthenticationError("sensitive diagnostic marker"),
            "invalid_auth",
        ),
        (
            ValidationStage.VERSION_READ,
            UniFiPermissionError("sensitive diagnostic marker"),
            "insufficient_permissions",
        ),
        (
            ValidationStage.DEVICE_READ,
            UniFiResponseError("HTTP 404 sensitive diagnostic marker"),
            "site_not_found",
        ),
    ],
)
async def test_staged_known_error_keeps_existing_ui_class(
    hass,
    stage: ValidationStage,
    cause: Exception,
    error_key: str,
) -> None:
    with patch(
        "custom_components.unifi_etherlighting.config_flow.ConfigFlow._async_validate_connection",
        new=AsyncMock(side_effect=ValidationStageError(stage, cause)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=CONNECTION,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}


def test_safe_stage_log_keeps_only_numeric_http_status(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(
        logging.WARNING, logger="custom_components.unifi_etherlighting.config_flow"
    )
    error = ValidationStageError(
        ValidationStage.DEVICE_READ,
        UniFiSchemaError("HTTP 503 sensitive diagnostic marker"),
    )

    _log_stage_failure(error, "validation_device_read")

    assert "stage=device_read" in caplog.text
    assert "http_status=503" in caplog.text
    assert "sensitive diagnostic marker" not in caplog.text
