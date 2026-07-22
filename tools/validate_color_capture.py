#!/usr/bin/env python3
"""Offline safety and sequence validator for the sanitized color capture."""

from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path
import re
import sys
from typing import Any

EXPECTED_VERSION = {
    "controller_type": "unifi_os",
    "network_application_version": "10.5.62",
    "device_type": "usw",
    "device_model": "USWED72",
    "device_firmware": "7.4.1.16850",
}
IP_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
MAC_RE = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")
HEX_ID_RE = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{24}(?![0-9a-f])")
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


def _get(value: Any, path: str) -> Any:
    current = value
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def _walk(value: Any, path: str = ""):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _contains_ip(text: str) -> bool:
    for match in IP_RE.finditer(text):
        try:
            ipaddress.ip_address(match.group(0))
        except ValueError:
            continue
        return True
    return False


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        raw = path.read_text(encoding="utf-8")
        capture = json.loads(raw)
    except (OSError, json.JSONDecodeError) as err:
        return [f"capture cannot be loaded: {err}"]
    if not isinstance(capture, dict):
        return ["capture root must be an object"]

    if _contains_ip(raw):
        errors.append("capture contains an IP address")
    if MAC_RE.search(raw):
        errors.append("capture contains a hardware address")
    if HEX_ID_RE.search(raw):
        errors.append("capture contains an unredacted identifier")
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

    if capture.get("session_id") != "color_capture_001":
        errors.append("unexpected session ID")
    if capture.get("capture_source") != "unifi_network_web_ui":
        errors.append("unexpected capture source")
    if capture.get("version_context") != EXPECTED_VERSION:
        errors.append("version context does not match the confirmed tuple")

    expected_reads = {
        "settings": ("GET", "/proxy/network/api/s/site_001/get/setting"),
        "network_labels": (
            "GET",
            "/proxy/network/api/s/site_001/rest/networkconf",
        ),
    }
    for name, (method, request_path) in expected_reads.items():
        read = _get(capture, f"reads.{name}")
        if not isinstance(read, dict) or (
            read.get("method"),
            read.get("path"),
            read.get("status"),
            read.get("meta_rc"),
        ) != (method, request_path, 200, "ok"):
            errors.append(f"{name} read contract is not confirmed")

    expected_writes = {
        "settings": (
            "POST",
            "/proxy/network/api/s/site_001/set/setting/ether_lighting",
        ),
        "device_refresh": (
            "PUT",
            "/proxy/network/api/s/site_001/rest/device/device_001",
        ),
    }
    for name, (method, request_path) in expected_writes.items():
        write = _get(capture, f"writes.{name}")
        if not isinstance(write, dict) or (
            write.get("method"),
            write.get("path"),
            write.get("status"),
            write.get("meta_rc"),
        ) != (method, request_path, 200, "ok"):
            errors.append(f"{name} write contract is not confirmed")
        elif set(write.get("header_names", [])) != {
            "Content-Type",
            "X-CSRF-Token",
        }:
            errors.append(f"{name} write header names are incomplete")

    expectations = {
        "network": ("0544FF", "0644FF", "network_overrides"),
        "speed": ("FFC105", "FEC105", "speed_overrides"),
    }
    for name, (original, target, field) in expectations.items():
        sequence = _get(capture, f"sequences.{name}")
        if not isinstance(sequence, dict):
            errors.append(f"{name} sequence is missing")
            continue
        if (
            sequence.get("before"),
            sequence.get("read_after"),
            sequence.get("final"),
        ) != (original, target, original):
            errors.append(f"{name} read-before/read-after/final sequence failed")
        for write_name, expected in (
            ("write_forward", target),
            ("write_reverse", original),
        ):
            write = sequence.get(write_name)
            if not isinstance(write, dict) or (
                write.get("requested"),
                write.get("status"),
                write.get("meta_rc"),
            ) != (expected, 200, "ok"):
                errors.append(f"{name} {write_name} failed")
            elif not isinstance(write.get(field), list):
                errors.append(f"{name} {write_name} omitted the full override array")

    if _get(capture, "writes.device_refresh.ether_lighting_unchanged") is not True:
        errors.append("accompanying Device PUT was not confirmed unchanged")
    if capture.get("unchanged_device_state") != {
        "mode": "network",
        "brightness": 30,
        "behavior": "steady",
        "led_mode": "etherlighting",
    }:
        errors.append("Device Etherlighting state was not preserved")
    if capture.get("safety") != {
        "ui_triggered_capture_writes_only": True,
        "manually_constructed_capture_requests": False,
        "network_assignments_changed": False,
        "port_configuration_changed": False,
        "sensitive_values_retained": False,
        "final_state_restored": True,
    }:
        errors.append("safety assertions are incomplete")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    errors = validate(args.capture.resolve())
    if errors:
        print("Color capture validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Color capture validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
