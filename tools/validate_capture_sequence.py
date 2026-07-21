#!/usr/bin/env python3
"""Offline validator for a sanitized Etherlighting capture sequence."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path
from typing import Any


ROLES = (
    "read_before",
    "write_forward",
    "read_after",
    "write_reverse",
    "read_final",
)
READ_ROLES = ("read_before", "read_after", "read_final")
WRITE_ROLES = ("write_forward", "write_reverse")
EXPECTED_SESSION = "brightness_capture_001"
EXPECTED_READ_PATH = "/proxy/network/api/s/site_001/stat/device"
EXPECTED_WRITE_PATH = "/proxy/network/api/s/site_001/rest/device/device_001"
EXPECTED_CHANGE_PATH = "ether_lighting.brightness"
PSEUDONYM_RE = re.compile(r"^(site|device|network|user)_\d{3}$")
MAC_RE = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])")
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
URL_RE = re.compile(r"(?i)\bhttps?://")
HEX_ID_RE = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{24}(?![0-9a-f])")
UUID_RE = re.compile(
    r"(?i)(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}(?![0-9a-f])"
)
IPV4_CANDIDATE_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
FORBIDDEN_KEYS = {
    "password",
    "passwd",
    "cookie",
    "cookies",
    "authorization",
    "api_key",
    "apikey",
    "jwt",
    "certificate",
    "private_key",
    "csrf_token",
    "x_csrf_token",
}


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        errors.append(f"{path}: cannot load JSON: {err}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path}: top-level value must be an object")
        return {}
    return value


def get_path(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def response_device(capture: dict[str, Any]) -> dict[str, Any]:
    data = get_path(capture, "response.body.data")
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        return data[0]
    return {}


def ether_from_response(capture: dict[str, Any]) -> dict[str, Any]:
    value = response_device(capture).get("ether_lighting")
    return value if isinstance(value, dict) else {}


def leaf_paths(value: Any, prefix: str = "") -> set[str]:
    if isinstance(value, dict):
        result: set[str] = set()
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            result.update(leaf_paths(child, child_prefix))
        return result
    if isinstance(value, list):
        result = set()
        for index, child in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            result.update(leaf_paths(child, child_prefix))
        return result
    return {prefix}


def diff_paths(left: Any, right: Any, prefix: str = "") -> set[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        differences: set[str] = set()
        for key in left.keys() | right.keys():
            child_prefix = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                differences.add(child_prefix)
            else:
                differences.update(diff_paths(left[key], right[key], child_prefix))
        return differences
    if isinstance(left, list) and isinstance(right, list):
        differences = set()
        if len(left) != len(right):
            differences.add(prefix)
        for index, (left_child, right_child) in enumerate(zip(left, right)):
            differences.update(
                diff_paths(left_child, right_child, f"{prefix}[{index}]")
            )
        return differences
    return set() if left == right else {prefix}


def walk(value: Any, prefix: str = ""):
    yield prefix, value
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            yield from walk(child, child_prefix)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{prefix}[{index}]")


def contains_ipv4(text: str) -> bool:
    for match in IPV4_CANDIDATE_RE.finditer(text):
        try:
            ipaddress.ip_address(match.group(0))
        except ValueError:
            continue
        return True
    return False


def validate_safety(
    label: str, capture: dict[str, Any], raw_text: str, errors: list[str]
) -> None:
    if contains_ipv4(raw_text):
        errors.append(f"{label}: contains an IPv4 address")
    if MAC_RE.search(raw_text):
        errors.append(f"{label}: contains a hardware address")
    if EMAIL_RE.search(raw_text):
        errors.append(f"{label}: contains an email address")
    if URL_RE.search(raw_text):
        errors.append(f"{label}: contains an absolute URL or host")
    if HEX_ID_RE.search(raw_text) or UUID_RE.search(raw_text):
        errors.append(f"{label}: contains a non-pseudonymized identifier")

    for path, value in walk(capture):
        key = path.rsplit(".", 1)[-1].split("[", 1)[0].lower().replace("-", "_")
        if key in FORBIDDEN_KEYS:
            errors.append(f"{label}: forbidden sensitive key at {path}")
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        if "-----begin " in lowered or lowered.startswith("bearer "):
            errors.append(f"{label}: credential-like value at {path}")
        if value.count(".") == 2 and all(len(part) >= 8 for part in value.split(".")):
            errors.append(f"{label}: token-like value at {path}")

    if "request" in capture:
        header_names = get_path(capture, "request.header_names")
        if not isinstance(header_names, list) or not all(
            isinstance(name, str) and ":" not in name and "\n" not in name
            for name in header_names
        ):
            errors.append(f"{label}: header_names must contain names only")


def validate(capture_dir: Path) -> list[str]:
    errors: list[str] = []
    environment_path = capture_dir.parent / "environment.json"
    if not environment_path.is_file():
        errors.append(f"missing environment file: {environment_path}")
    environment = (
        load_json(environment_path, errors) if environment_path.is_file() else {}
    )

    captures: dict[str, dict[str, Any]] = {}
    raw_texts: dict[str, str] = {}
    for role in ROLES:
        path = capture_dir / f"{role}.json"
        if not path.is_file():
            errors.append(f"missing capture file: {path}")
            continue
        raw_texts[role] = path.read_text(encoding="utf-8")
        captures[role] = load_json(path, errors)

    if len(captures) != len(ROLES):
        return errors

    expected_context = {
        "controller_type": environment.get("controller_type"),
        "network_application_version": environment.get("network_application_version"),
        "device_model": environment.get("device_model"),
        "device_firmware": environment.get("device_firmware"),
    }
    if not environment.get("network_application_version"):
        errors.append("environment: Network Application version is missing")
    if environment.get("session_id") != EXPECTED_SESSION:
        errors.append("environment: unexpected session_id")

    for role, capture in captures.items():
        if capture.get("capture_role") != role:
            errors.append(f"{role}: capture_role does not match filename")
        if capture.get("session_id") != EXPECTED_SESSION:
            errors.append(f"{role}: session_id is inconsistent")
        if capture.get("version_context") != expected_context:
            errors.append(f"{role}: version context differs from environment")
        if get_path(capture, "request.query") != {}:
            errors.append(f"{role}: expected an empty query object")
        status = get_path(capture, "response.status")
        if not isinstance(status, int) or not 200 <= status < 300:
            errors.append(f"{role}: response status is not successful")
        if get_path(capture, "response.body.meta.rc") != "ok":
            errors.append(f"{role}: UniFi meta.rc is not ok")
        device = response_device(capture)
        if not device:
            errors.append(f"{role}: response must contain one projected target device")
        if device.get("_id") != "device_001" or device.get("site_id") != "site_001":
            errors.append(
                f"{role}: target identifiers are not consistently pseudonymized"
            )
        validate_safety(role, capture, raw_texts[role], errors)

    environment_raw = (
        environment_path.read_text(encoding="utf-8") if environment else ""
    )
    validate_safety("environment", environment, environment_raw, errors)

    read_paths = {get_path(captures[role], "request.path") for role in READ_ROLES}
    write_paths = {get_path(captures[role], "request.path") for role in WRITE_ROLES}
    if read_paths != {EXPECTED_READ_PATH}:
        errors.append("reads do not use the same pseudonymized UI-observed path")
    if write_paths != {EXPECTED_WRITE_PATH}:
        errors.append("writes do not use the same pseudonymized UI-observed path")
    for role in READ_ROLES:
        if get_path(captures[role], "request.method") != "GET":
            errors.append(f"{role}: method is not GET")
    for role in WRITE_ROLES:
        if get_path(captures[role], "request.method") != "PUT":
            errors.append(f"{role}: method is not PUT")
        headers = get_path(captures[role], "request.header_names") or []
        if set(headers) != {"Content-Type", "X-CSRF-Token"}:
            errors.append(f"{role}: expected write header names are missing")

    before = ether_from_response(captures["read_before"])
    forward_response = ether_from_response(captures["write_forward"])
    after = ether_from_response(captures["read_after"])
    reverse_response = ether_from_response(captures["write_reverse"])
    final = ether_from_response(captures["read_final"])
    forward_body = get_path(captures["write_forward"], "request.body") or {}
    reverse_body = get_path(captures["write_reverse"], "request.body") or {}
    forward_request = get_path(forward_body, "ether_lighting") or {}
    reverse_request = get_path(reverse_body, "ether_lighting") or {}

    before_value = before.get("brightness")
    target_value = get_path(captures["write_forward"], "ui_action.after")
    if get_path(captures["write_forward"], "ui_action.before") != before_value:
        errors.append("write_forward: UI action does not start at read_before")
    if not isinstance(before_value, int) or target_value != before_value + 1:
        errors.append("write_forward: brightness is not exactly one UI step")
    if forward_request.get("brightness") != target_value:
        errors.append("write_forward: request brightness does not match UI target")
    if forward_response.get("brightness") != target_value:
        errors.append("write_forward: response brightness does not match UI target")
    if after.get("brightness") != target_value:
        errors.append("read_after: independent read does not confirm target")
    if get_path(captures["write_reverse"], "ui_action.before") != target_value:
        errors.append("write_reverse: UI action does not start at target")
    if get_path(captures["write_reverse"], "ui_action.after") != before_value:
        errors.append("write_reverse: UI action does not restore the original value")
    if reverse_request.get("brightness") != before_value:
        errors.append("write_reverse: request does not restore original brightness")
    if reverse_response.get("brightness") != before_value:
        errors.append("write_reverse: response does not confirm restored brightness")
    if final.get("brightness") != before_value:
        errors.append(
            "read_final: independent read does not confirm original brightness"
        )

    body_diffs = diff_paths(forward_body, reverse_body)
    if body_diffs != {EXPECTED_CHANGE_PATH}:
        errors.append(
            "write request bodies differ outside the single allowed path: "
            + ", ".join(sorted(body_diffs))
        )

    ether_snapshots = (
        before,
        forward_request,
        forward_response,
        after,
        reverse_request,
        reverse_response,
        final,
    )
    for field in ("mode", "behavior", "led_mode"):
        values = {snapshot.get(field) for snapshot in ether_snapshots}
        if len(values) != 1 or None in values:
            errors.append(f"Etherlighting field changed or disappeared: {field}")

    baseline_device_paths = leaf_paths(response_device(captures["read_before"]))
    for role in ROLES[1:]:
        if leaf_paths(response_device(captures[role])) != baseline_device_paths:
            errors.append(
                f"{role}: relevant projected device fields disappeared or appeared"
            )
    if leaf_paths(forward_body) != leaf_paths(reverse_body):
        errors.append("write_reverse: request fields differ from write_forward")

    response_diffs = diff_paths(
        response_device(captures["read_before"]),
        response_device(captures["read_final"]),
    )
    if response_diffs:
        errors.append(
            "read_final: projected configuration differs from read_before: "
            + ", ".join(sorted(response_diffs))
        )

    for role in READ_ROLES:
        ui_state = captures[role].get("ui_state") or {}
        response_ether = ether_from_response(captures[role])
        for field in ("brightness", "mode", "behavior"):
            if ui_state.get(field) != response_ether.get(field):
                errors.append(f"{role}: UI state differs from response field {field}")
        if ui_state.get("enabled") is not True:
            errors.append(f"{role}: active Etherlighting state was not preserved")

    for path_value in read_paths | write_paths:
        if not isinstance(path_value, str):
            continue
        for segment in path_value.split("/"):
            if segment.startswith(
                ("site_", "device_", "network_", "user_")
            ) and not PSEUDONYM_RE.fullmatch(segment):
                errors.append(f"invalid pseudonym in path: {segment}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "capture_dir", type=Path, help="directory containing five capture files"
    )
    args = parser.parse_args()
    errors = validate(args.capture_dir.resolve())
    if errors:
        print("Capture sequence: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Capture sequence: PASS")
    print("- files and session: consistent")
    print("- version context and pseudonyms: consistent")
    print("- read/write/read-back/reversal: confirmed")
    print("- only ether_lighting.brightness changed")
    print("- sensitive-data scan: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
