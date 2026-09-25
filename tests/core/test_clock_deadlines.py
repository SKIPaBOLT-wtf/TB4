from __future__ import annotations

from dataclasses import dataclass

import pytest

from tb4.core.clock import (
    ClockSkewDisposition,
    ClockSkewError,
    assert_clock_skew_sane,
    inspect_clock_skew,
)
from tb4.core.deadlines import (
    MonotonicDeadline,
    is_accept_expired,
    is_lease_expired,
    is_run_expired,
    is_stale,
    observed_age_s,
)


@dataclass
class FakeClock:
    wall: int = 1_700_000_000
    mono: float = 100.0

    def utc_epoch(self) -> int:
        return self.wall

    def monotonic(self) -> float:
        return self.mono

    def advance(self, seconds: float) -> None:
        self.mono += seconds
        self.wall += int(seconds)


def test_accept_expiry_is_closed_at_exact_boundary() -> None:
    assert not is_accept_expired(99, 100)
    assert is_accept_expired(100, 100)
    assert is_accept_expired(101, 100)
    assert is_accept_expired(99, 0)


def test_run_limit_and_lease_are_closed_at_exact_boundary() -> None:
    assert not is_run_expired(1299, 1000, 300)
    assert is_run_expired(1300, 1000, 300)
    assert not is_lease_expired(1099, 1000, 100)
    assert is_lease_expired(1100, 1000, 100)


def test_unstarted_run_or_lease_is_not_silently_treated_as_valid() -> None:
    with pytest.raises(ValueError):
        is_run_expired(1000, 0, 300)
    with pytest.raises(ValueError):
        is_lease_expired(1000, 0, 300)


def test_monotonic_deadline_ignores_wall_clock_changes() -> None:
    clock = FakeClock()
    deadline = MonotonicDeadline(clock.monotonic(), 10)

    clock.wall -= 3600
    clock.mono += 9.5
    assert not deadline.expired(clock.monotonic())
    assert deadline.remaining(clock.monotonic()) == pytest.approx(0.5)

    clock.mono += 0.5
    assert deadline.expired(clock.monotonic())
    assert deadline.remaining(clock.monotonic()) == 0


def test_fake_clock_forward_progression() -> None:
    clock = FakeClock()
    deadline = MonotonicDeadline(clock.monotonic(), 5)
    clock.advance(5)
    assert deadline.expired(clock.monotonic())
    assert clock.utc_epoch() == 1_700_000_005


def test_clock_skew_is_reported_without_correction() -> None:
    decision = inspect_clock_skew(1000, 1007, 10)
    assert decision.disposition is ClockSkewDisposition.REMOTE_AHEAD
    assert decision.delta_s == 7
    assert decision.acceptable

    decision = inspect_clock_skew(1000, 990, 10)
    assert decision.disposition is ClockSkewDisposition.REMOTE_BEHIND
    assert decision.acceptable


def test_future_observation_within_tolerance_never_returns_negative_age() -> None:
    assert observed_age_s(1000, 1007, clock_skew_tolerance_s=10) == 0


def test_future_observation_beyond_tolerance_is_not_treated_healthy() -> None:
    with pytest.raises(ClockSkewError):
        observed_age_s(1000, 1011, clock_skew_tolerance_s=10)
    with pytest.raises(ClockSkewError):
        is_stale(1000, 1011, 30, clock_skew_tolerance_s=10)


def test_stale_age_boundary_is_deterministic() -> None:
    assert not is_stale(1000, 971, 30, clock_skew_tolerance_s=10)
    assert is_stale(1000, 970, 30, clock_skew_tolerance_s=10)


def test_clock_skew_assertion_rejects_large_delta() -> None:
    with pytest.raises(ClockSkewError):
        assert_clock_skew_sane(1000, 1020, 10)


def test_negative_durations_and_thresholds_are_rejected() -> None:
    with pytest.raises(ValueError):
        MonotonicDeadline(0.0, -1)
    with pytest.raises(ValueError):
        is_run_expired(1000, 900, 0)
    with pytest.raises(ValueError):
        is_stale(1000, 900, 0, clock_skew_tolerance_s=10)
