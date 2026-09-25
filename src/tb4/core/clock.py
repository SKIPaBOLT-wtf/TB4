from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Clock(Protocol):
    def utc_epoch(self) -> int: ...
    def monotonic(self) -> float: ...


class SystemClock:
    def utc_epoch(self) -> int:
        return int(time.time())

    def monotonic(self) -> float:
        return time.monotonic()


class ClockSkewDisposition(StrEnum):
    OK = "OK"
    REMOTE_AHEAD = "REMOTE_AHEAD"
    REMOTE_BEHIND = "REMOTE_BEHIND"


@dataclass(frozen=True, slots=True)
class ClockSkewDecision:
    disposition: ClockSkewDisposition
    delta_s: int
    tolerance_s: int

    @property
    def acceptable(self) -> bool:
        return abs(self.delta_s) <= self.tolerance_s


class ClockSkewError(RuntimeError):
    def __init__(self, decision: ClockSkewDecision) -> None:
        super().__init__(
            f"remote clock skew {decision.delta_s:+d}s exceeds "
            f"tolerance {decision.tolerance_s}s"
        )
        self.decision = decision


def inspect_clock_skew(
    local_epoch: int,
    remote_epoch: int,
    tolerance_s: int,
) -> ClockSkewDecision:
    if tolerance_s < 0:
        raise ValueError("clock skew tolerance must be non-negative")
    delta = remote_epoch - local_epoch
    if delta > 0:
        disposition = ClockSkewDisposition.REMOTE_AHEAD
    elif delta < 0:
        disposition = ClockSkewDisposition.REMOTE_BEHIND
    else:
        disposition = ClockSkewDisposition.OK
    return ClockSkewDecision(disposition, delta, tolerance_s)


def assert_clock_skew_sane(
    local_epoch: int,
    remote_epoch: int,
    tolerance_s: int,
) -> ClockSkewDecision:
    decision = inspect_clock_skew(local_epoch, remote_epoch, tolerance_s)
    if not decision.acceptable:
        raise ClockSkewError(decision)
    return decision
