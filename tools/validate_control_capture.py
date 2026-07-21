#!/usr/bin/env python3
"""Offline validation for the sanitized behavior and mode live capture."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path
from typing import Any

EXPECTED_READ = "/proxy/network/api/s/site_001/stat/device"
EXPECTED_WRITE = "/proxy/network/api/s/site_001/rest/device/device_001"
EXPECTED_VERSION = {
    "controller_type": "unifi_os",
    "network_application_version": "10.5.62",
    "device_type": "usw",
    "device_model": "USWED72",
    "device_firmware": "7.4.1.16850",
}
IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
MAC_RE = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])")
URL_RE = re.compile(r"(?i)https?://")
FORBIDDEN_KEYS = {
    "password",
    "cookie",
    "authorization",
    "token",
    "csrf_token",
    "host",
    "ip",
    "mac",
    "username",
    "email",
}


def _contains_ipv4(text: str) -> bool:
    for match in IPV4_RE.finditer(text):
        try:
            ipaddress.ip_address(match.group(0))
        except ValueError:
            continue
        return True
    return False


def _walk(value: Any, path: str = ""):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _changed_fields(before: dict[str, Any], after: dict[str, Any]) -> set[str]:
    return {
        key
        for key in before.keys() | after.keys()
        if before.get(key) != after.get(key)
    }


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        raw = path.read_text(encoding="utf-8")
        capture = json.loads(raw)
    except (OSError, json.JSONDecodeError) as err:
        return [f"capture cannot be loaded: {err}"]
    if not isinstance(capture, dict):
        return ["capture root must be an object"]

    if _contains_ipv4(raw):
        errors.append("capture contains an IP address")
    if MAC_RE.search(raw):
        errors.append("capture contains a hardware address")
    if URL_RE.search(raw):
        errors.append("capture contains an absolute URL")
    for field_path, value in _walk(capture):
        key = field_path.rsplit(".", 1)[-1].split("[", 1)[0].lower()
        if key in FORBIDDEN_KEYS:
            errors.append(f"forbidden sensitive field: {field_path}")
        if isinstance(value, str) and (
            value.lower().startswith("bearer ") or "-----begin " in value.lower()
        ):
            errors.append(f"credential-like value: {field_path}")

    if capture.get("session_id") != "etherlighting_controls_capture_001":
        errors.append("unexpected session_id")
    if capture.get("capture_source") != "unifi_network_web_ui":
        errors.append("unexpected capture source")
    if capture.get("version_context") != EXPECTED_VERSION:
        errors.append("version context does not match the confirmed tuple")

    read = capture.get("read")
    if not isinstance(read, dict) or (
        read.get("method"), read.get("path"), read.get("status")
    ) != ("GET", EXPECTED_READ, 200):
        errors.append("read contract is not confirmed")
    write = capture.get("write")
    if not isinstance(write, dict) or (
        write.get("method"), write.get("path")
    ) != ("PUT", EXPECTED_WRITE):
        errors.append("write contract is not confirmed")
    elif write.get("header_names") != ["Content-Type", "X-CSRF-Token"]:
        errors.append("write header names are inconsistent")

    sequences = capture.get("sequences")
    if not isinstance(sequences, dict):
        return errors + ["sequences object is missing"]
    expectations = {
        "behavior": ("behavior", "steady", "breath"),
        "mode": ("mode", "network", "speed"),
    }
    for name, (field, original, target) in expectations.items():
        sequence = sequences.get(name)
        if not isinstance(sequence, dict):
            errors.append(f"{name}: sequence is missing")
            continue
        states = {}
        for state_name in ("before", "read_after", "final"):
            state = sequence.get(state_name)
            if not isinstance(state, dict):
                errors.append(f"{name}: {state_name} is missing")
                state = {}
            states[state_name] = state
        writes = {}
        for write_name in ("write_forward", "write_reverse"):
            write_state = sequence.get(write_name)
            if not isinstance(write_state, dict):
                errors.append(f"{name}: {write_name} is missing")
                write_state = {}
            elif (write_state.get("status"), write_state.get("meta_rc")) != (
                200,
                "ok",
            ):
                errors.append(f"{name}: {write_name} was not successful")
            ether = write_state.get("ether_lighting")
            writes[write_name] = ether if isinstance(ether, dict) else {}

        if states["before"].get(field) != original:
            errors.append(f"{name}: unexpected original value")
        if writes["write_forward"].get(field) != target:
            errors.append(f"{name}: forward target is not confirmed")
        if states["read_after"] != writes["write_forward"]:
            errors.append(f"{name}: read-after-write does not match")
        if writes["write_reverse"].get(field) != original:
            errors.append(f"{name}: reverse target is not confirmed")
        if states["final"] != states["before"]:
            errors.append(f"{name}: final state was not restored")
        if _changed_fields(states["before"], writes["write_forward"]) != {field}:
            errors.append(f"{name}: forward changed more than {field}")
        if _changed_fields(states["read_after"], writes["write_reverse"]) != {field}:
            errors.append(f"{name}: reverse changed more than {field}")
        if sequence.get("changed_path") != f"ether_lighting.{field}":
            errors.append(f"{name}: changed path is inconsistent")

    safety = capture.get("safety")
    expected_safety = {
        "ui_triggered_writes_only": True,
        "manually_constructed_requests": False,
        "colors_changed": False,
        "sensitive_values_retained": False,
        "final_state_restored": True,
    }
    if safety != expected_safety:
        errors.append("safety assertions are incomplete")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    errors = validate(args.capture.resolve())
    if errors:
        print("Control capture validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Control capture validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
