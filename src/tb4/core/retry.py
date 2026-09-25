from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Mapping, Any

from .deadlines import MonotonicDeadline


class ProbeDisposition(StrEnum):
    CONFIRMED = "CONFIRMED"
    NOT_VISIBLE = "NOT_VISIBLE"
    AMBIGUOUS = "AMBIGUOUS"


class RetryStopReason(StrEnum):
    CONFIRMED = "CONFIRMED"
    EXHAUSTED = "EXHAUSTED"
    DEADLINE = "DEADLINE"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    confirmation_backoff_s: tuple[float, ...]
    operation_attempts: int

    def __post_init__(self) -> None:
        if self.operation_attempts <= 0:
            raise ValueError("operation_attempts must be positive")
        if not self.confirmation_backoff_s:
            raise ValueError("confirmation backoff sequence must not be empty")
        if any(delay <= 0 for delay in self.confirmation_backoff_s):
            raise ValueError("confirmation backoff values must be positive")
        if tuple(sorted(self.confirmation_backoff_s)) != self.confirmation_backoff_s:
            raise ValueError("confirmation backoff must be nondecreasing")

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "RetryPolicy":
        drive = config["drive"]
        return cls(
            confirmation_backoff_s=tuple(
                milliseconds / 1000.0
                for milliseconds in drive["confirm_backoff_ms"]
            ),
            operation_attempts=int(drive["transition_attempts"]),
        )


@dataclass(frozen=True, slots=True)
class ConfirmationReport:
    reason: RetryStopReason
    probe_count: int
    slept_s: float

    @property
    def confirmed(self) -> bool:
        return self.reason is RetryStopReason.CONFIRMED


@dataclass(slots=True)
class OperationAttemptBudget:
    policy: RetryPolicy
    monotonic_now: Callable[[], float]
    deadline: MonotonicDeadline | None = None
    _claimed: int = 0

    @property
    def claimed(self) -> int:
        return self._claimed

    def claim(self) -> int | None:
        """Return the next 1-based attempt number, or None when bounded out."""

        if self._claimed >= self.policy.operation_attempts:
            return None
        if self.deadline is not None and self.deadline.expired(self.monotonic_now()):
            return None
        self._claimed += 1
        return self._claimed


def confirm_with_backoff(
    probe: Callable[[], ProbeDisposition],
    *,
    policy: RetryPolicy,
    monotonic_now: Callable[[], float],
    sleeper: Callable[[float], None],
    deadline: MonotonicDeadline | None = None,
) -> ConfirmationReport:
    """Retry a read-only confirmation probe; never retry an ambiguous mutation."""

    probe_count = 1
    slept_s = 0.0
    first = probe()
    if first is ProbeDisposition.CONFIRMED:
        return ConfirmationReport(RetryStopReason.CONFIRMED, probe_count, slept_s)
    if first is ProbeDisposition.AMBIGUOUS:
        return ConfirmationReport(RetryStopReason.AMBIGUOUS, probe_count, slept_s)

    for delay in policy.confirmation_backoff_s:
        now = monotonic_now()
        if deadline is not None:
            remaining = deadline.remaining(now)
            if remaining <= 0 or delay >= remaining:
                return ConfirmationReport(
                    RetryStopReason.DEADLINE, probe_count, slept_s
                )

        sleeper(delay)
        slept_s += delay
        probe_count += 1
        result = probe()

        if result is ProbeDisposition.CONFIRMED:
            return ConfirmationReport(
                RetryStopReason.CONFIRMED, probe_count, slept_s
            )
        if result is ProbeDisposition.AMBIGUOUS:
            return ConfirmationReport(
                RetryStopReason.AMBIGUOUS, probe_count, slept_s
            )

    return ConfirmationReport(RetryStopReason.EXHAUSTED, probe_count, slept_s)
