from custom_components.unifi_etherlighting.diagnostics import redact_diagnostics


def test_diagnostics_allowlist_removes_credentials_hosts_and_ids() -> None:
    result = redact_diagnostics(
        {
            "controller_type": "unifi_os",
            "network_application_version": None,
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
                    "state": "candidate",
                    "evidence": "write_accepted",
                    "payload": {"secret": True},
                }
            ],
        }
    )
    assert result["controller_type"] == "unifi_os"
    assert result["options"] == {"verify_ssl": True}
    assert result["capabilities"] == [
        {"capability": "brightness", "state": "candidate", "evidence": "write_accepted"}
    ]
    assert "host" not in result
    assert "password" not in result
