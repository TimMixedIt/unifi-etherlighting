#!/usr/bin/env python3
"""Offline validator for the sanitized post-update runtime capture."""

from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path
import re
import sys
from typing import Any

IP_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
MAC_RE = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")
URL_RE = re.compile(r"(?i)https?://")
FORBIDDEN_KEYS = {
    "authorization",
    "cookie",
    "csrf",
    "csrf_token",
    "device_id",
    "email",
    "host",
    "mac",
    "password",
    "session_id",
    "site_id",
    "token",
    "username",
}


def _walk(value: Any, path: str = ""):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            yield from _walk(child, child_path)
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
    """Return blocking validation errors without changing the capture."""
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
        errors.append("capture contains a MAC address")
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

    if capture.get("capture_role") != "post_update_runtime_validation":
        errors.append("unexpected capture role")
    if capture.get("capture_source") != "home_assistant_entities":
        errors.append("unexpected capture source")
    if capture.get("integration_version") != "0.5.0":
        errors.append("unexpected integration version")

    environment = capture.get("environment")
    if not isinstance(environment, dict):
        errors.append("environment is missing")
    elif (
        environment.get("controller_type"),
        environment.get("previous_network_application_version"),
        environment.get("current_network_application_version"),
        environment.get("device_type"),
    ) != ("unifi_os", "10.5.62", "10.5.66", "usw"):
        errors.append("environment does not match the observed update")

    runtime = capture.get("runtime_contract")
    if not isinstance(runtime, dict):
        errors.append("runtime contract is missing")
    elif (
        runtime.get("profile"),
        runtime.get("network_api_generation_supported"),
        runtime.get("contract_compatible_device_count"),
        runtime.get("controller_status"),
        runtime.get("write_capability"),
        runtime.get("write_block_reason"),
    ) != ("unifi_os_network_v10", True, 1, "online", "ready", None):
        errors.append("runtime contract did not pass")

    sequences = capture.get("sequences")
    expected_paths = {
        "brightness": "ether_lighting.brightness",
        "mode": "ether_lighting.mode",
        "behavior": "ether_lighting.behavior",
        "network_color": "ether_lighting.network_overrides.color",
        "speed_color": "ether_lighting.speed_overrides.color",
    }
    if not isinstance(sequences, dict):
        errors.append("sequences are missing")
    else:
        for name, semantic_path in expected_paths.items():
            sequence = sequences.get(name)
            if not isinstance(sequence, dict):
                errors.append(f"{name}: sequence is missing")
                continue
            if sequence.get("semantic_path") != semantic_path:
                errors.append(f"{name}: semantic path is inconsistent")
            if sequence.get("before") == sequence.get("after"):
                errors.append(f"{name}: forward action did not change the value")
            if sequence.get("final") != sequence.get("before"):
                errors.append(f"{name}: original value was not restored")
            if (
                sequence.get("forward_result"),
                sequence.get("reverse_result"),
            ) != ("verified", "verified"):
                errors.append(f"{name}: read-back verification failed")

    if capture.get("final_invariants") != {
        "brightness": 30,
        "mode": "network",
        "behavior": "steady",
        "network_color_restored": True,
        "speed_color_restored": True,
        "write_block_reason": None,
        "integration_errors": 0,
    }:
        errors.append("final invariants are incomplete")
    if capture.get("security") != {
        "contains_credentials": False,
        "contains_addresses": False,
        "contains_identifiers": False,
        "contains_cookie_or_token_values": False,
        "contains_raw_requests_or_responses": False,
    }:
        errors.append("security assertions are incomplete")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    errors = validate(args.capture.resolve())
    if errors:
        print("Update compatibility validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Update compatibility validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
