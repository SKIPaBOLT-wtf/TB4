from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

from tb4.core.deadlines import MonotonicDeadline
from tb4.core.retry import (
    OperationAttemptBudget,
    ProbeDisposition,
    RetryPolicy,
    RetryStopReason,
    confirm_with_backoff,
)


ROOT = Path(__file__).resolve().parents[2]


@dataclass
class FakeMonotonic:
    now: float = 100.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _canonical_policy() -> RetryPolicy:
    config = tomllib.loads(
        (ROOT / "config" / "defaults.toml").read_text(encoding="utf-8")
    )
    return RetryPolicy.from_config(config)


def test_policy_uses_exact_configured_drive_backoff() -> None:
    policy = _canonical_policy()
    assert policy.confirmation_backoff_s == (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
    assert policy.operation_attempts == 3


def test_zero_negative_or_decreasing_backoff_is_rejected() -> None:
    with pytest.raises(ValueError):
        RetryPolicy((), 1)
    with pytest.raises(ValueError):
        RetryPolicy((0.0,), 1)
    with pytest.raises(ValueError):
        RetryPolicy((-1.0,), 1)
    with pytest.raises(ValueError):
        RetryPolicy((1.0, 0.5), 1)
    with pytest.raises(ValueError):
        RetryPolicy((1.0,), 0)


def test_confirmation_success_has_no_sleep_after_success() -> None:
    clock = FakeMonotonic()
    calls = 0

    def probe() -> ProbeDisposition:
        nonlocal calls
        calls += 1
        return ProbeDisposition.CONFIRMED

    report = confirm_with_backoff(
        probe,
        policy=_canonical_policy(),
        monotonic_now=clock.monotonic,
        sleeper=clock.sleep,
    )
    assert report.reason is RetryStopReason.CONFIRMED
    assert report.probe_count == 1
    assert report.slept_s == 0
    assert calls == 1
    assert clock.now == 100.0


def test_confirmation_uses_configured_sequence_until_visible() -> None:
    clock = FakeMonotonic()
    answers = iter(
        [
            ProbeDisposition.NOT_VISIBLE,
            ProbeDisposition.NOT_VISIBLE,
            ProbeDisposition.CONFIRMED,
        ]
    )

    report = confirm_with_backoff(
        lambda: next(answers),
        policy=_canonical_policy(),
        monotonic_now=clock.monotonic,
        sleeper=clock.sleep,
    )
    assert report.reason is RetryStopReason.CONFIRMED
    assert report.probe_count == 3
    assert report.slept_s == pytest.approx(0.75)
    assert clock.now == pytest.approx(100.75)


def test_confirmation_exhaustion_is_explicit() -> None:
    clock = FakeMonotonic()
    report = confirm_with_backoff(
        lambda: ProbeDisposition.NOT_VISIBLE,
        policy=RetryPolicy((0.25, 0.5), 3),
        monotonic_now=clock.monotonic,
        sleeper=clock.sleep,
    )
    assert report.reason is RetryStopReason.EXHAUSTED
    assert report.probe_count == 3
    assert report.slept_s == pytest.approx(0.75)


def test_ambiguous_result_stops_without_retry_or_sleep() -> None:
    clock = FakeMonotonic()
    report = confirm_with_backoff(
        lambda: ProbeDisposition.AMBIGUOUS,
        policy=_canonical_policy(),
        monotonic_now=clock.monotonic,
        sleeper=clock.sleep,
    )
    assert report.reason is RetryStopReason.AMBIGUOUS
    assert report.probe_count == 1
    assert report.slept_s == 0
    assert clock.now == 100.0


def test_deadline_stops_before_scheduled_probe_beyond_budget() -> None:
    clock = FakeMonotonic()
    deadline = MonotonicDeadline(clock.monotonic(), 0.4)
    report = confirm_with_backoff(
        lambda: ProbeDisposition.NOT_VISIBLE,
        policy=RetryPolicy((0.25, 0.5, 1.0), 3),
        monotonic_now=clock.monotonic,
        sleeper=clock.sleep,
        deadline=deadline,
    )
    assert report.reason is RetryStopReason.DEADLINE
    assert report.probe_count == 2
    assert report.slept_s == pytest.approx(0.25)


def test_operation_attempt_budget_enforces_exact_ceiling() -> None:
    clock = FakeMonotonic()
    budget = OperationAttemptBudget(_canonical_policy(), clock.monotonic)
    assert [budget.claim(), budget.claim(), budget.claim(), budget.claim()] == [
        1,
        2,
        3,
        None,
    ]


def test_operation_attempt_budget_obeys_monotonic_deadline() -> None:
    clock = FakeMonotonic()
    deadline = MonotonicDeadline(clock.monotonic(), 1.0)
    budget = OperationAttemptBudget(
        _canonical_policy(), clock.monotonic, deadline
    )
    assert budget.claim() == 1
    clock.sleep(1.0)
    assert budget.claim() is None
