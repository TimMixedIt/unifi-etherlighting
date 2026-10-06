from __future__ import annotations

from types import SimpleNamespace

from custom_components.unifi_etherlighting.const import (
    WRITE_CAPABILITY_BLOCKED_STATE,
    WRITE_CAPABILITY_ENABLED,
    WRITE_CAPABILITY_STATE,
    write_capability_state,
)
from custom_components.unifi_etherlighting.write_readiness import (
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
