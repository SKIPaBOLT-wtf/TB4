from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable


class IdleDecision(StrEnum):
    BUSY = "BUSY"
    IDLE_COUNTING = "IDLE_COUNTING"
    EXIT_IDLE = "EXIT_IDLE"


@dataclass(slots=True)
class IdleManager:
    """Monotonic FETCHER idle-exit policy.

    Idle time exists only while the protocol is fully reusable: FETCH_BALL_READY,
    STOP_BALL_READY, and no local child process/cancellation handling is active.
    Leaving that condition resets the timer rather than merely pausing it.
    """

    idle_exit_s: float
    monotonic_now: Callable[[], float]
    idle_since_monotonic_s: float | None = None

    def __post_init__(self) -> None:
        if self.idle_exit_s <= 0:
            raise ValueError("idle_exit_s must be positive")

    def observe(
        self,
        *,
        fetch_ball_ready: bool,
        stop_ball_ready: bool,
        child_active: bool,
        cancellation_active: bool,
    ) -> IdleDecision:
        eligible = (
            fetch_ball_ready
            and stop_ball_ready
            and not child_active
            and not cancellation_active
        )
        now = self.monotonic_now()

        if not eligible:
            self.idle_since_monotonic_s = None
            return IdleDecision.BUSY

        if self.idle_since_monotonic_s is None:
            self.idle_since_monotonic_s = now
            return IdleDecision.IDLE_COUNTING

        if now - self.idle_since_monotonic_s >= self.idle_exit_s:
            return IdleDecision.EXIT_IDLE

        return IdleDecision.IDLE_COUNTING

    def reset(self) -> None:
        self.idle_since_monotonic_s = None
