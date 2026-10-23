"""Aggregate the effective write gate without weakening any contract."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from .const import WRITE_CAPABILITY_BLOCKED_STATE, WRITE_CAPABILITY_STATE

WRITE_READINESS_READY = "ready"
WRITE_READINESS_NOT_READY = "not_ready"
DEVICE_CONTROLS = ("brightness", "behavior", "mode")
COLOR_CATEGORIES = ("network", "speed")


class _DeviceWriteState(Protocol):
    """The bounded write state needed for the diagnostic aggregate."""

    brightness_write_ready: bool
    behavior_write_ready: bool
    mode_write_ready: bool
    write_blocked: bool


class _ColorWriteState(Protocol):
    """The bounded color write state needed for the diagnostic aggregate."""

    write_ready: bool
    write_blocked: bool


def effective_write_ready(
    global_write_capability: str,
    devices: Iterable[_DeviceWriteState],
    colors: Iterable[_ColorWriteState],
) -> bool:
    """Whether at least one current, unblocked Etherlighting write is safe.

    ``global_write_capability`` is a release-wide kill switch.  It must remain
    open *and* a live Device or color contract must expose a write that has not
    been blocked after an indeterminate result.
    """
    # This diagnostic must fail closed: only the exact, current release-wide
    # open state can make a live control effectively write-ready.
    if global_write_capability != WRITE_CAPABILITY_STATE:
        return False

    return any(
        not device.write_blocked
        and (
            device.brightness_write_ready
            or device.behavior_write_ready
            or device.mode_write_ready
        )
        for device in devices
    ) or any(
        color.write_ready and not color.write_blocked for color in colors
    )


def effective_write_readiness(
    global_write_capability: str,
    devices: Iterable[_DeviceWriteState],
    colors: Iterable[_ColorWriteState],
) -> str:
    """Return a bounded user-facing effective write-readiness state."""
    if global_write_capability == WRITE_CAPABILITY_BLOCKED_STATE:
        return WRITE_CAPABILITY_BLOCKED_STATE
    if effective_write_ready(global_write_capability, devices, colors):
        return WRITE_READINESS_READY
    return WRITE_READINESS_NOT_READY


def _write_support_state(states: Iterable[str]) -> str:
    """Return the strongest write-evidence state among the given values."""
    present = set(states)
    if "confirmed" in present:
        return "confirmed"
    if "candidate" in present:
        return "candidate"
    return "unsupported"


def device_control_summary(devices: Iterable[Any]) -> dict[str, object]:
    """Aggregate per-control read and write state across selected Devices."""
    devices = tuple(devices)
    summary: dict[str, object] = {}
    for control in DEVICE_CONTROLS:
        summary[f"{control}_read_supported"] = any(
            getattr(device, f"{control}_read_supported") for device in devices
        )
        summary[f"{control}_write_supported"] = _write_support_state(
            getattr(device, f"{control}_write_supported").value for device in devices
        )
        summary[f"{control}_write_ready"] = any(
            getattr(device, f"{control}_write_ready") for device in devices
        )
    return summary


def color_control_summary(colors: Iterable[Any]) -> dict[str, object]:
    """Aggregate read and write state for the network and speed palettes."""
    colors = tuple(colors)
    summary: dict[str, object] = {}
    for category in COLOR_CATEGORIES:
        items = tuple(color for color in colors if color.category == category)
        summary[f"{category}_color_read_supported"] = any(
            color.read_supported for color in items
        )
        summary[f"{category}_color_write_supported"] = _write_support_state(
            color.write_supported.value for color in items
        )
        summary[f"{category}_color_write_ready"] = any(
            color.write_ready and not color.write_blocked for color in items
        )
    return summary
