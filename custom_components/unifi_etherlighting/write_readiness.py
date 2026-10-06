"""Aggregate the effective write gate without weakening any contract."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from .const import WRITE_CAPABILITY_BLOCKED_STATE, WRITE_CAPABILITY_STATE

WRITE_READINESS_READY = "ready"
WRITE_READINESS_NOT_READY = "not_ready"


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
