from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from tb4.drive.backend import DriveBackend
from tb4.fetcher.heartbeat import HeartbeatOutcome, HeartbeatPublisher
from tb4.fetcher.idle_manager import IdleDecision, IdleManager


class StartupDisposition(StrEnum):
    READY = "READY"
    WORK_AVAILABLE = "WORK_AVAILABLE"
    STALE_EXECUTION = "STALE_EXECUTION"
    INCOMPLETE_RETURN = "INCOMPLETE_RETURN"
    TERMINAL_WAIT = "TERMINAL_WAIT"
    CONTROL_PENDING = "CONTROL_PENDING"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class StartupSnapshot:
    disposition: StartupDisposition
    fetch_ball_state: str
    stop_ball_state: str
    heartbeat_published: bool
    message: str | None = None


@dataclass(frozen=True, slots=True)
class LifecycleTick:
    idle_decision: IdleDecision
    fetch_ball_state: str
    stop_ball_state: str
    child_active: bool
    cancellation_active: bool


_FETCH_PREFIX = "FETCH_BALL_"
_STOP_PREFIX = "STOP_BALL_"

_FETCH_TERMINAL = {
    "DONE",
    "PARTIAL",
    "FAILED",
    "CANCELLED",
    "GONE",
}
_STOP_PENDING = {
    "LOADING",
    "REQUESTED",
    "RETURNING",
    "ACKNOWLEDGED",
}


@dataclass(slots=True)
class FetcherServiceLifecycle:
    """Small lifecycle coordinator for FETCHER startup and idle shutdown.

    This class deliberately does not execute jobs and does not repair remote
    state. It inspects the exact canonical FETCH_BALL and STOP_BALL objects,
    publishes the initial heartbeat, classifies restart state, and gates idle
    exit through IdleManager.

    A freshly started FETCHER must never resume a pre-existing CHEW as local
    work. Only a TOSS may be claimed by a new process instance.
    """

    backend: DriveBackend
    fetch_ball_object_id: str
    stop_ball_object_id: str
    heartbeat: HeartbeatPublisher
    idle_manager: IdleManager
    child_active: Callable[[], bool]
    cancellation_active: Callable[[], bool]

    def startup_inspect(self) -> StartupSnapshot:
        fetch_state = self._state(self.fetch_ball_object_id, _FETCH_PREFIX)
        stop_state = self._state(self.stop_ball_object_id, _STOP_PREFIX)

        active = fetch_state not in {"READY", *_FETCH_TERMINAL}
        heartbeat = self.heartbeat.tick(active=active)
        heartbeat_published = heartbeat.outcome is HeartbeatOutcome.PUBLISHED
        if heartbeat.outcome not in {
            HeartbeatOutcome.PUBLISHED,
            HeartbeatOutcome.NOT_DUE,
        }:
            return StartupSnapshot(
                StartupDisposition.INVALID,
                fetch_state,
                stop_state,
                heartbeat_published=False,
                message=f"initial heartbeat failed: {heartbeat.outcome.value}: {heartbeat.message or ''}".rstrip(),
            )

        if fetch_state == "READY":
            if stop_state == "READY":
                return StartupSnapshot(
                    StartupDisposition.READY,
                    fetch_state,
                    stop_state,
                    heartbeat_published,
                )
            if stop_state in _STOP_PENDING:
                return StartupSnapshot(
                    StartupDisposition.CONTROL_PENDING,
                    fetch_state,
                    stop_state,
                    heartbeat_published,
                    message="STOP_BALL is not reusable yet; do not accept new work",
                )
            return StartupSnapshot(
                StartupDisposition.INVALID,
                fetch_state,
                stop_state,
                heartbeat_published,
                message=f"unknown STOP_BALL state {stop_state!r}",
            )

        if fetch_state == "TOSS":
            return StartupSnapshot(
                StartupDisposition.WORK_AVAILABLE,
                fetch_state,
                stop_state,
                heartbeat_published,
                message="verified request may be claimed by this FETCHER instance",
            )

        if fetch_state == "CHEW":
            return StartupSnapshot(
                StartupDisposition.STALE_EXECUTION,
                fetch_state,
                stop_state,
                heartbeat_published,
                message="pre-existing CHEW is not resumed; WATCHDOG must recover it",
            )

        if fetch_state == "RETURNING":
            return StartupSnapshot(
                StartupDisposition.INCOMPLETE_RETURN,
                fetch_state,
                stop_state,
                heartbeat_published,
                message="pre-existing RETURNING is not fabricated or completed by restart",
            )

        if fetch_state in _FETCH_TERMINAL:
            return StartupSnapshot(
                StartupDisposition.TERMINAL_WAIT,
                fetch_state,
                stop_state,
                heartbeat_published,
                message="terminal result belongs to COACH until recycled",
            )

        if fetch_state in {"LOADING", "RECYCLING"}:
            return StartupSnapshot(
                StartupDisposition.CONTROL_PENDING,
                fetch_state,
                stop_state,
                heartbeat_published,
                message="COACH-owned FETCH_BALL state is not executable by FETCHER",
            )

        return StartupSnapshot(
            StartupDisposition.INVALID,
            fetch_state,
            stop_state,
            heartbeat_published,
            message=f"unknown FETCH_BALL state {fetch_state!r}",
        )

    def tick_idle(self) -> LifecycleTick:
        fetch_state = self._state(self.fetch_ball_object_id, _FETCH_PREFIX)
        stop_state = self._state(self.stop_ball_object_id, _STOP_PREFIX)
        child = bool(self.child_active())
        cancelling = bool(self.cancellation_active())

        decision = self.idle_manager.observe(
            fetch_ball_ready=fetch_state == "READY",
            stop_ball_ready=stop_state == "READY",
            child_active=child,
            cancellation_active=cancelling,
        )
        return LifecycleTick(
            idle_decision=decision,
            fetch_ball_state=fetch_state,
            stop_ball_state=stop_state,
            child_active=child,
            cancellation_active=cancelling,
        )

    def _state(self, object_id: str, prefix: str) -> str:
        metadata = self.backend.get_metadata(object_id)
        if not metadata.ok or metadata.value is None:
            raise RuntimeError(
                f"metadata read failed for {object_id}: "
                f"{metadata.outcome.value}: {metadata.message or ''}".rstrip()
            )
        if metadata.value.is_folder:
            raise RuntimeError(f"control object {object_id} is a folder")
        if not metadata.value.name.startswith(prefix):
            raise RuntimeError(
                f"control object {object_id} has unexpected name {metadata.value.name!r}"
            )
        return metadata.value.name[len(prefix):]
