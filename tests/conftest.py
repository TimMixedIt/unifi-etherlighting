"""Shared Home Assistant test configuration; no live controller fixture exists."""

import asyncio

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def enable_event_loop_debug() -> None:
    """Override the HA helper that calls removed implicit-loop behavior on 3.13."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.set_debug(True)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make this repository's custom component discoverable to Home Assistant."""
    yield
