from custom_components.unifi_etherlighting.diagnostics import redact_diagnostics


def test_diagnostics_allowlist_removes_credentials_hosts_and_ids() -> None:
    result = redact_diagnostics(
        {
            "controller_type": "unifi_os",
            "network_application_version": None,
            "compatibility_profile": "unifi_os_network_v10",
            "network_api_generation_supported": True,
            "contract_compatible_device_count": 1,
            "write_capability": "ready",
            "write_block_reason": None,
            "missing_confirmed_fields": [],
            "brightness_read_supported": True,
            "brightness_write_supported": "confirmed",
            "brightness_write_ready": True,
            "behavior_read_supported": True,
            "behavior_write_supported": "confirmed",
            "behavior_write_ready": True,
            "mode_read_supported": True,
            "mode_write_supported": "confirmed",
            "mode_write_ready": True,
            "host": "controller.invalid",
            "username": "user",
            "password": "secret",
            "cookie": "cookie",
            "csrf_token": "token",
            "device_id": "device_001",
            "options": {"verify_ssl": True, "host": "controller.invalid"},
            "capabilities": [
                {
                    "capability": "brightness",
                    "state": "confirmed",
                    "evidence": "write_accepted",
                    "payload": {"secret": True},
                }
            ],
        }
    )
    assert result["controller_type"] == "unifi_os"
    assert result["compatibility_profile"] == "unifi_os_network_v10"
    assert result["network_api_generation_supported"] is True
    assert result["contract_compatible_device_count"] == 1
    assert result["write_capability"] == "ready"
    assert result["write_block_reason"] is None
    assert result["missing_confirmed_fields"] == []
    assert result["brightness_read_supported"] is True
    assert result["brightness_write_supported"] == "confirmed"
    assert result["brightness_write_ready"] is True
    assert result["behavior_read_supported"] is True
    assert result["behavior_write_supported"] == "confirmed"
    assert result["behavior_write_ready"] is True
    assert result["mode_read_supported"] is True
    assert result["mode_write_supported"] == "confirmed"
    assert result["mode_write_ready"] is True
    assert result["options"] == {"verify_ssl": True}
    assert result["capabilities"] == [
        {"capability": "brightness", "state": "confirmed", "evidence": "write_accepted"}
    ]
    assert "host" not in result
    assert "password" not in result
