from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.unifi_etherlighting.api.errors import UniFiPermissionError
from custom_components.unifi_etherlighting.config_flow import ConfigFlow
from custom_components.unifi_etherlighting.const import DOMAIN

CONNECTION = {
    "host": "controller.invalid",
    "port": 443,
    "use_ssl": True,
    "verify_ssl": True,
    "username": "user",
    "password": "secret",
    "site": "site_001",
}
DEVICE = {
    "_id": "device_001",
    "model": "USWED72",
    "version": "7.4.1.16850",
    "ether_lighting": {"brightness": 30},
}


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


async def test_successful_validation_is_not_masked_by_logout_failure(hass) -> None:
    """A cleanup failure after successful reads must not look like bad credentials."""
    auth = MagicMock()
    auth.authenticated = True
    auth.async_login = AsyncMock()
    auth.async_logout = AsyncMock(side_effect=Exception("synthetic cleanup failure"))
    auth.async_get_csrf_token = AsyncMock(return_value=None)

    controller = MagicMock()
    controller.async_read_network_application_version = AsyncMock(
        return_value="10.5.62"
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
