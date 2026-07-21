"""Live-validated config flow with explicit Site and compatible Device selection."""

from __future__ import annotations

import re
from typing import Any

from aiohttp import CookieJar
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api.adapters.unifi_os_controller import UniFiOsControllerAdapter
from .api.adapters.unifi_os_device import UniFiOsDeviceAdapter
from .api.auth import UniFiAuthSession
from .api.client import UniFiApiClient
from .api.errors import (
    UniFiAuthenticationError,
    UniFiPermissionError,
    UniFiResponseError,
    UniFiSchemaError,
    UniFiTransportError,
)
from .api.models import CURRENT_COMPATIBILITY, brightness_is_confirmed
from .const import (
    CONF_DEBUG_DIAGNOSTICS,
    CONF_DEVICE_IDS,
    CONF_DIAGNOSTIC_SENSORS,
    CONF_POLL_INTERVAL,
    CONF_SITE,
    CONF_USE_SSL,
    CONF_VERIFY_SSL,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_PORT,
    DOMAIN,
)

_SITE_SLUG = re.compile(r"^[A-Za-z0-9_-]+$")


def _normalise_unique_id(host: str, port: int) -> str:
    return f"{host.strip().lower()}:{port}"


CONNECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Required(CONF_USE_SSL, default=True): bool,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SITE): selector.TextSelector(),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL_SECONDS
        ): vol.All(vol.Coerce(int), vol.Range(min=60, max=86400)),
        vol.Required(CONF_DIAGNOSTIC_SENSORS, default=True): bool,
        vol.Required(CONF_DEBUG_DIAGNOSTICS, default=False): bool,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Login, validate the explicit Site, and select exact-compatible switches."""

    VERSION = 2

    def __init__(self) -> None:
        self._pending_data: dict[str, Any] | None = None
        self._compatible_devices: tuple[dict[str, Any], ...] = ()

    @staticmethod
    def _base_url(data: dict[str, Any]) -> str:
        scheme = "https" if data[CONF_USE_SSL] else "http"
        return f"{scheme}://{data[CONF_HOST]}:{data[CONF_PORT]}"

    async def _async_validate_connection(
        self, data: dict[str, Any]
    ) -> tuple[dict[str, Any], ...]:
        session = async_create_clientsession(
            self.hass,
            verify_ssl=data[CONF_VERIFY_SSL],
            cookie_jar=CookieJar(unsafe=True),
        )
        base_url = self._base_url(data)
        auth = UniFiAuthSession(
            session, base_url, data[CONF_USERNAME], data[CONF_PASSWORD]
        )
        client = UniFiApiClient(
            session,
            base_url,
            auth.async_get_csrf_token,
            auth_session=auth,
        )
        controller = UniFiOsControllerAdapter(client)
        devices = UniFiOsDeviceAdapter(client)
        try:
            await auth.async_login()
            network_version = await controller.async_read_network_application_version()
            all_devices = await devices.async_read_devices(data[CONF_SITE])
        finally:
            if auth.authenticated:
                await auth.async_logout()

        if network_version != CURRENT_COMPATIBILITY.network_application_version:
            raise vol.Invalid("unsupported_network_version")
        if not all_devices:
            raise vol.Invalid("no_devices")
        compatible = tuple(
            device
            for device in all_devices
            if brightness_is_confirmed(network_version, device)
        )
        if not compatible:
            raise vol.Invalid("no_compatible_devices")
        return compatible

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                validated = dict(CONNECTION_SCHEMA(user_input))
                if not _SITE_SLUG.fullmatch(validated[CONF_SITE]):
                    errors[CONF_SITE] = "invalid_site"
                    return self.async_show_form(
                        step_id="user",
                        data_schema=CONNECTION_SCHEMA,
                        errors=errors,
                    )
                compatible = await self._async_validate_connection(validated)
            except vol.Invalid as err:
                reason = str(err)
                errors["base"] = (
                    reason
                    if reason
                    in {
                        "unsupported_network_version",
                        "no_devices",
                        "no_compatible_devices",
                    }
                    else "unknown"
                )
            except UniFiAuthenticationError:
                errors["base"] = "invalid_auth"
            except UniFiPermissionError:
                errors["base"] = "invalid_auth"
            except UniFiTransportError as err:
                cause_name = type(err.__cause__).__name__ if err.__cause__ else ""
                if "Certificate" in cause_name:
                    errors["base"] = "invalid_ssl"
                elif isinstance(err.__cause__, TimeoutError):
                    errors["base"] = "timeout"
                else:
                    errors["base"] = "cannot_connect"
            except UniFiSchemaError:
                errors["base"] = "unknown"
            except UniFiResponseError as err:
                errors["base"] = (
                    "site_not_found" if "HTTP 404" in str(err) else "unknown"
                )
            except TimeoutError:
                errors["base"] = "timeout"
            except Exception:
                errors["base"] = "unknown"
            else:
                self._pending_data = validated
                self._compatible_devices = compatible
                return await self.async_step_devices()
        return self.async_show_form(
            step_id="user", data_schema=CONNECTION_SCHEMA, errors=errors
        )

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if self._pending_data is None or not self._compatible_devices:
            return self.async_abort(reason="unknown")
        choices = [
            selector.SelectOptionDict(
                value=str(device["_id"]),
                label=f"{device.get('model', 'unknown')} / {device.get('version', 'unknown')}",
            )
            for device in self._compatible_devices
            if isinstance(device.get("_id"), str)
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_IDS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=choices,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="devices", data_schema=schema)

        selected = user_input.get(CONF_DEVICE_IDS)
        if isinstance(selected, str):
            selected = [selected]
        allowed = {option["value"] for option in choices}
        if (
            not isinstance(selected, list)
            or not selected
            or not set(selected) <= allowed
        ):
            return self.async_show_form(
                step_id="devices",
                data_schema=schema,
                errors={"base": "no_compatible_devices"},
            )

        data = {**self._pending_data, CONF_DEVICE_IDS: list(selected)}
        unique_id = _normalise_unique_id(data[CONF_HOST], data[CONF_PORT])
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"UniFi Etherlighting ({unique_id})", data=data
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "OptionsFlow":
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            try:
                validated = OPTIONS_SCHEMA(user_input)
            except vol.Invalid:
                return self.async_show_form(
                    step_id="init",
                    data_schema=OPTIONS_SCHEMA,
                    errors={"base": "unknown"},
                )
            return self.async_create_entry(title="", data=validated)

        defaults = {
            CONF_POLL_INTERVAL: self._config_entry.options.get(
                CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL_SECONDS
            ),
            CONF_DIAGNOSTIC_SENSORS: self._config_entry.options.get(
                CONF_DIAGNOSTIC_SENSORS, True
            ),
            CONF_DEBUG_DIAGNOSTICS: self._config_entry.options.get(
                CONF_DEBUG_DIAGNOSTICS, False
            ),
            CONF_VERIFY_SSL: self._config_entry.options.get(
                CONF_VERIFY_SSL, self._config_entry.data[CONF_VERIFY_SSL]
            ),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL, default=defaults[CONF_POLL_INTERVAL]
                    ): vol.All(vol.Coerce(int), vol.Range(min=60, max=86400)),
                    vol.Required(
                        CONF_DIAGNOSTIC_SENSORS,
                        default=defaults[CONF_DIAGNOSTIC_SENSORS],
                    ): bool,
                    vol.Required(
                        CONF_DEBUG_DIAGNOSTICS,
                        default=defaults[CONF_DEBUG_DIAGNOSTICS],
                    ): bool,
                    vol.Required(
                        CONF_VERIFY_SSL, default=defaults[CONF_VERIFY_SSL]
                    ): bool,
                }
            ),
        )
