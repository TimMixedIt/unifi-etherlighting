from __future__ import annotations

from types import SimpleNamespace

from custom_components.unifi_etherlighting.const import (
    WRITE_CAPABILITY_BLOCKED_STATE,
    WRITE_CAPABILITY_ENABLED,
    WRITE_CAPABILITY_STATE,
    write_capability_state,
)
from custom_components.unifi_etherlighting.api.models import CapabilityState
from custom_components.unifi_etherlighting.write_readiness import (
    color_control_summary,
    device_control_summary,
    effective_write_ready,
    effective_write_readiness,
)


def _device(*, ready: bool, blocked: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        brightness_write_ready=ready,
        behavior_write_ready=False,
        mode_write_ready=False,
        write_blocked=blocked,
    )


def _color(*, ready: bool, blocked: bool = False) -> SimpleNamespace:
    return SimpleNamespace(write_ready=ready, write_blocked=blocked)


def test_effective_write_readiness_requires_a_live_unblocked_control() -> None:
    assert effective_write_readiness("ready", (_device(ready=True),), ()) == "ready"
    assert effective_write_ready("ready", (_device(ready=True),), ())

    assert (
        effective_write_readiness("ready", (_device(ready=True, blocked=True),), ())
        == "not_ready"
    )
    assert not effective_write_ready("ready", (_device(ready=False),), ())
    assert effective_write_readiness("ready", (), (_color(ready=True),)) == "ready"


def test_global_write_block_always_wins() -> None:
    assert (
        effective_write_readiness("blocked", (_device(ready=True),), ())
        == "blocked"
    )
    assert not effective_write_ready("blocked", (), (_color(ready=True),))


def test_unknown_global_write_state_fails_closed() -> None:
    assert not effective_write_ready("unknown", (_device(ready=True),), ())
    assert (
        effective_write_readiness("unknown", (_device(ready=True),), ())
        == "not_ready"
    )


def test_global_write_capability_state_follows_the_release_gate() -> None:
    assert write_capability_state(True) == "ready"
    assert write_capability_state(False) == WRITE_CAPABILITY_BLOCKED_STATE
    assert WRITE_CAPABILITY_STATE == write_capability_state(WRITE_CAPABILITY_ENABLED)


def test_control_summaries_report_the_strongest_write_evidence() -> None:
    def control(state: CapabilityState) -> SimpleNamespace:
        return SimpleNamespace(
            **{
                f"{name}_{suffix}": value
                for name in ("brightness", "behavior", "mode")
                for suffix, value in (
                    ("read_supported", True),
                    ("write_supported", state),
                    ("write_ready", state is CapabilityState.CONFIRMED),
                )
            }
        )

    candidate = device_control_summary((control(CapabilityState.CANDIDATE),))
    assert candidate["behavior_write_supported"] == "candidate"
    assert candidate["mode_write_supported"] == "candidate"
    assert not candidate["mode_write_ready"]
    mixed = device_control_summary(
        (control(CapabilityState.UNSUPPORTED), control(CapabilityState.CONFIRMED))
    )
    assert mixed["brightness_write_supported"] == "confirmed"
    assert mixed["brightness_write_ready"]
    assert device_control_summary(())["mode_write_supported"] == "unsupported"

    speed = SimpleNamespace(
        category="speed",
        read_supported=True,
        write_supported=CapabilityState.CONFIRMED,
        write_ready=True,
        write_blocked=True,
    )
    assert color_control_summary((speed,)) == {
        "network_color_read_supported": False,
        "network_color_write_supported": "unsupported",
        "network_color_write_ready": False,
        "speed_color_read_supported": True,
        "speed_color_write_supported": "confirmed",
        "speed_color_write_ready": False,
    }
