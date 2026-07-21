"""A deliberately locked Read-modify-write workflow for future confirmed reads."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .api.adapters.base import EtherlightingControllerAdapter
from .api.errors import (
    CapabilityNotConfirmedError,
    ReadPathNotConfirmedError,
    VerificationError,
)
from .api.models import (
    CapabilityEvidence,
    CapabilityState,
    EvidenceLevel,
    evidence_at_least,
)
from .brightness import build_brightness_write_payload


def deep_copy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Copy nested maps/lists without JSON reserialization or data loss."""
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dictionary")
    return deepcopy(payload)


def _step(container: Any, segment: str) -> Any:
    if isinstance(container, dict):
        if segment not in container:
            raise KeyError(f"JSON path segment is missing: {segment}")
        return container[segment]
    if isinstance(container, list):
        try:
            index = int(segment)
        except ValueError as err:
            raise KeyError(f"List path segment is not an index: {segment}") from err
        if index < 0 or index >= len(container):
            raise KeyError(f"List path index is out of range: {segment}")
        return container[index]
    raise KeyError(f"Cannot traverse non-container at path segment: {segment}")


def get_json_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    """Return an existing path only; absent paths must never be invented."""
    if not path:
        raise ValueError("json_path must not be empty")
    current: Any = data
    for segment in path:
        current = _step(current, segment)
    return current


def set_json_path(
    data: dict[str, Any], path: tuple[str, ...], value: Any
) -> dict[str, Any]:
    """Return a deep-copied payload with one existing leaf replaced."""
    result = deep_copy_payload(data)
    if not path:
        raise ValueError("json_path must not be empty")
    parent: Any = result
    for segment in path[:-1]:
        parent = _step(parent, segment)
    leaf = path[-1]
    if isinstance(parent, dict):
        if leaf not in parent:
            raise KeyError(f"JSON path segment is missing: {leaf}")
        parent[leaf] = value
    elif isinstance(parent, list):
        try:
            index = int(leaf)
        except ValueError as err:
            raise KeyError(f"List path segment is not an index: {leaf}") from err
        if index < 0 or index >= len(parent):
            raise KeyError(f"List path index is out of range: {leaf}")
        parent[index] = value
    else:
        raise KeyError(f"Cannot set a child on a non-container: {leaf}")
    return result


def _diff(
    before: Any, after: Any, path: tuple[str, ...] = ()
) -> list[tuple[str, Any, Any]]:
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[tuple[str, Any, Any]] = []
        for key in sorted(set(before) | set(after), key=str):
            changes.extend(_diff(before.get(key), after.get(key), path + (str(key),)))
        return changes
    if isinstance(before, list) and isinstance(after, list):
        changes = []
        for index in range(max(len(before), len(after))):
            left = before[index] if index < len(before) else None
            right = after[index] if index < len(after) else None
            changes.extend(_diff(left, right, path + (str(index),)))
        return changes
    return [] if before == after else [(".".join(path) or "<root>", before, after)]


def diff_json_paths(
    before: dict[str, Any], after: dict[str, Any]
) -> list[tuple[str, Any, Any]]:
    """Return all leaf changes, including additions, removals and type changes."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise TypeError("before and after must be dictionaries")
    return _diff(before, after)


async def async_update_confirmed_path(
    adapter: EtherlightingControllerAdapter,
    site_id: str,
    device_id: str,
    json_path: tuple[str, ...],
    new_value: Any,
    capability: CapabilityEvidence,
) -> dict[str, Any]:
    """Future RMW operation, protected so current captures cannot write anything."""
    if capability.state is not CapabilityState.CONFIRMED:
        raise CapabilityNotConfirmedError(
            f"{capability.capability} is not confirmed for this controller and firmware"
        )
    if not evidence_at_least(capability.evidence, EvidenceLevel.READ_VERIFIED):
        raise ReadPathNotConfirmedError(
            f"{capability.capability} lacks a confirmed read-before-write path"
        )

    if capability.capability != "brightness" or json_path != (
        "ether_lighting",
        "brightness",
    ):
        raise CapabilityNotConfirmedError(
            "Only the confirmed brightness projection is writable"
        )
    current = await adapter.async_read_device(site_id, device_id)
    old_value = get_json_path(current, json_path)
    payload = build_brightness_write_payload(current, new_value)
    expected_path = ".".join(json_path)
    projected_before = deep_copy_payload(payload)
    projected_before["ether_lighting"]["brightness"] = old_value
    if diff_json_paths(projected_before, payload) != [
        (expected_path, old_value, new_value)
    ]:
        raise VerificationError("Projected write payload contains unexpected changes")

    await adapter.async_write_device(site_id, device_id, payload)
    verified = await adapter.async_read_device(site_id, device_id)
    if get_json_path(verified, json_path) != new_value:
        raise VerificationError("Read-after-write did not return the requested value")
    unexpected = [
        change
        for change in diff_json_paths(current, verified)
        if change[0] != expected_path
    ]
    if unexpected:
        raise VerificationError(
            "Read-after-write changed fields outside the confirmed path"
        )
    return verified
