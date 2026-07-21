"""UniFi Etherlighting with verified, version-bound local controls."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from aiohttp import CookieJar

from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api.adapters.unifi_os_controller import UniFiOsControllerAdapter
from .api.adapters.unifi_os_device import UniFiOsDeviceAdapter
from .api.auth import UniFiAuthSession
from .api.client import UniFiApiClient
from .brightness import BrightnessService
from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USE_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from .coordinator import EtherlightingDataUpdateCoordinator
from .repairs import async_sync_repairs

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SELECT,
]


@dataclass(slots=True)
class RuntimeData:
    """Controller clients and state held only for the lifetime of one entry."""

    coordinator: EtherlightingDataUpdateCoordinator
    auth: UniFiAuthSession
    controller: UniFiOsControllerAdapter
    adapter: UniFiOsDeviceAdapter
    brightness_service: BrightnessService
    controller_unique_id: str


def _controller_base_url(entry: ConfigEntry) -> str:
    scheme = "https" if entry.data[CONF_USE_SSL] else "http"
    return f"{scheme}://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Authenticate and perform read-only setup; setup never writes a Device."""
    session = async_create_clientsession(
        hass,
        verify_ssl=entry.options.get(CONF_VERIFY_SSL, entry.data[CONF_VERIFY_SSL]),
        cookie_jar=CookieJar(unsafe=True),
    )
    base_url = _controller_base_url(entry)
    auth = UniFiAuthSession(
        session,
        base_url,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    client = UniFiApiClient(
        session,
        base_url,
        auth.async_get_csrf_token,
        auth_session=auth,
    )
    controller = UniFiOsControllerAdapter(client)
    adapter = UniFiOsDeviceAdapter(client)
    brightness_service = BrightnessService(auth, controller, adapter)
    coordinator = EtherlightingDataUpdateCoordinator(
        hass, entry, controller, adapter, brightness_service
    )
    entry.runtime_data = RuntimeData(
        coordinator=coordinator,
        auth=auth,
        controller=controller,
        adapter=adapter,
        brightness_service=brightness_service,
        controller_unique_id=entry.unique_id or entry.entry_id,
    )

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await async_sync_repairs(hass, entry, coordinator.data)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms and close the confirmed controller session."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        runtime: RuntimeData = entry.runtime_data
        try:
            await runtime.auth.async_logout()
        except Exception:
            # Unload must not leak credentials or become stuck on a best-effort logout.
            pass
        entry.runtime_data = None
    return unloaded
