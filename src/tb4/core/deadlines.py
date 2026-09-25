from __future__ import annotations

from dataclasses import dataclass

from .clock import ClockSkewError, assert_clock_skew_sane


@dataclass(frozen=True, slots=True)
class MonotonicDeadline:
    started_at: float
    duration_s: float

    def __post_init__(self) -> None:
        if self.duration_s < 0:
            raise ValueError("duration must be non-negative")

    @property
    def due_at(self) -> float:
        return self.started_at + self.duration_s

    def expired(self, monotonic_now: float) -> bool:
        return monotonic_now >= self.due_at

    def remaining(self, monotonic_now: float) -> float:
        return max(0.0, self.due_at - monotonic_now)


def is_accept_expired(now_epoch: int, expires_at: int) -> bool:
    """Published work is expired at the exact expiry boundary."""

    if expires_at <= 0:
        return True
    return now_epoch >= expires_at


def is_run_expired(now_epoch: int, started_at: int, run_limit_s: int) -> bool:
    if started_at <= 0:
        raise ValueError("run deadline requires a positive started_at")
    if run_limit_s <= 0:
        raise ValueError("run_limit_s must be positive")
    return now_epoch >= started_at + run_limit_s


def is_lease_expired(now_epoch: int, lease_started_at: int, lease_duration_s: int) -> bool:
    if lease_started_at <= 0:
        raise ValueError("lease start must be positive")
    if lease_duration_s <= 0:
        raise ValueError("lease duration must be positive")
    return now_epoch >= lease_started_at + lease_duration_s


def observed_age_s(
    now_epoch: int,
    observed_at: int,
    *,
    clock_skew_tolerance_s: int,
) -> int:
    """Return non-negative age or raise when the remote clock is implausibly ahead."""

    if observed_at <= 0:
        raise ValueError("observed_at must be positive")
    if observed_at > now_epoch:
        assert_clock_skew_sane(now_epoch, observed_at, clock_skew_tolerance_s)
        # Small known skew is tolerated for ordering, but never returned as negative age.
        return 0
    return now_epoch - observed_at


def is_stale(
    now_epoch: int,
    observed_at: int,
    stale_after_s: int,
    *,
    clock_skew_tolerance_s: int,
) -> bool:
    if stale_after_s <= 0:
        raise ValueError("stale_after_s must be positive")
    return (
        observed_age_s(
            now_epoch,
            observed_at,
            clock_skew_tolerance_s=clock_skew_tolerance_s,
        )
        >= stale_after_s
    )
