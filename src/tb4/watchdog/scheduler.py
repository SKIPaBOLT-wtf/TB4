from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Callable


class DogMode(StrEnum):
    SNOOZE = "SNOOZE"
    AWAKE = "AWAKE"


class DispatchReason(StrEnum):
    TIMER = "TIMER"
    EVENT = "EVENT"


TaskCallback = Callable[[DispatchReason], None]


@dataclass(slots=True)
class TaskMetrics:
    dispatches: int = 0
    timer_dispatches: int = 0
    event_dispatches: int = 0
    failures: int = 0
    last_started_monotonic_s: float | None = None
    last_finished_monotonic_s: float | None = None
    last_error: str | None = None


@dataclass(slots=True)
class ScheduledTask:
    name: str
    callback: TaskCallback
    snooze_interval_s: float
    awake_interval_s: float | None = None
    phase_key: str | None = None
    next_due_monotonic_s: float | None = None
    event_pending: bool = False
    metrics: TaskMetrics = field(default_factory=TaskMetrics)

    def interval_for(self, mode: DogMode) -> float:
        interval = (
            self.awake_interval_s
            if mode is DogMode.AWAKE and self.awake_interval_s is not None
            else self.snooze_interval_s
        )
        if interval <= 0:
            raise ValueError(f"task {self.name!r} interval must be positive")
        return float(interval)


@dataclass(frozen=True, slots=True)
class SchedulerMetrics:
    wakeups: int
    dispatches: int
    failures: int
    task_count: int
    pending_events: int


@dataclass(slots=True)
class WatchdogScheduler:
    """Deterministic monotonic scheduler for WATCHDOG helpers.

    The scheduler owns timing only. It does not know LAN, Drive, WOL, SSH, or
    protocol semantics. Each registered callback is isolated: one exception is
    recorded and cannot remove or reset the timing state of other tasks.

    Event-triggered dispatch is orthogonal to periodic cadence. Triggering a
    task does not move its timer deadline.
    """

    monotonic_now: Callable[[], float]
    mode: DogMode = DogMode.SNOOZE
    tasks: dict[str, ScheduledTask] = field(default_factory=dict)
    wakeups: int = 0

    def register(self, task: ScheduledTask) -> None:
        if not task.name:
            raise ValueError("task name is required")
        if task.name in self.tasks:
            raise ValueError(f"task {task.name!r} is already registered")
        task.interval_for(DogMode.SNOOZE)
        if task.awake_interval_s is not None:
            task.interval_for(DogMode.AWAKE)

        now = self.monotonic_now()
        if task.next_due_monotonic_s is None:
            interval = task.interval_for(self.mode)
            task.next_due_monotonic_s = now + self._phase_offset(task, interval)
        self.tasks[task.name] = task

    def unregister(self, name: str) -> ScheduledTask:
        try:
            return self.tasks.pop(name)
        except KeyError as exc:
            raise KeyError(f"unknown task {name!r}") from exc

    def set_mode(self, mode: DogMode) -> None:
        if mode is self.mode:
            return
        now = self.monotonic_now()
        self.mode = mode

        # Rebase only the periodic deadline of tasks whose cadence changes.
        # Pending events remain pending and unrelated task identity is preserved.
        for task in self.tasks.values():
            if task.awake_interval_s is None:
                continue
            interval = task.interval_for(mode)
            task.next_due_monotonic_s = now + self._phase_offset(task, interval)

    def trigger(self, name: str) -> None:
        try:
            self.tasks[name].event_pending = True
        except KeyError as exc:
            raise KeyError(f"unknown task {name!r}") from exc

    def next_wakeup_in(self) -> float | None:
        if not self.tasks:
            return None
        if any(task.event_pending for task in self.tasks.values()):
            return 0.0

        now = self.monotonic_now()
        due = min(
            task.next_due_monotonic_s
            for task in self.tasks.values()
            if task.next_due_monotonic_s is not None
        )
        return max(0.0, float(due - now))

    def run_due(self) -> int:
        """Dispatch all work currently due and return dispatch count.

        Timer ordering is deterministic: earliest deadline first, then task
        name. Events are dispatched before timers at the same scheduler wakeup.
        A timer that became due while an earlier callback was slow is still run
        in the same call. Missed periodic intervals are skipped rather than
        replayed as a burst.
        """

        self.wakeups += 1
        dispatched = 0

        # Snapshot event names so an event raised by a callback becomes work for
        # the next wakeup rather than recursively dispatching without bound.
        event_names = sorted(
            name for name, task in self.tasks.items() if task.event_pending
        )
        for name in event_names:
            task = self.tasks.get(name)
            if task is None or not task.event_pending:
                continue
            task.event_pending = False
            self._dispatch(task, DispatchReason.EVENT)
            dispatched += 1

        while True:
            now = self.monotonic_now()
            due_tasks = [
                task
                for task in self.tasks.values()
                if task.next_due_monotonic_s is not None
                and task.next_due_monotonic_s <= now
            ]
            if not due_tasks:
                break

            due_tasks.sort(key=lambda task: (task.next_due_monotonic_s, task.name))
            task = due_tasks[0]
            previous_due = float(task.next_due_monotonic_s)
            self._dispatch(task, DispatchReason.TIMER)
            dispatched += 1
            self._advance_deadline(task, previous_due)

        return dispatched

    def metrics(self) -> SchedulerMetrics:
        return SchedulerMetrics(
            wakeups=self.wakeups,
            dispatches=sum(t.metrics.dispatches for t in self.tasks.values()),
            failures=sum(t.metrics.failures for t in self.tasks.values()),
            task_count=len(self.tasks),
            pending_events=sum(1 for t in self.tasks.values() if t.event_pending),
        )

    def _dispatch(self, task: ScheduledTask, reason: DispatchReason) -> None:
        started = self.monotonic_now()
        task.metrics.dispatches += 1
        task.metrics.last_started_monotonic_s = started
        if reason is DispatchReason.TIMER:
            task.metrics.timer_dispatches += 1
        else:
            task.metrics.event_dispatches += 1

        try:
            task.callback(reason)
        except Exception as exc:  # helper failures are isolated by design
            task.metrics.failures += 1
            task.metrics.last_error = f"{type(exc).__name__}: {exc}"
        finally:
            task.metrics.last_finished_monotonic_s = self.monotonic_now()

    def _advance_deadline(self, task: ScheduledTask, previous_due: float) -> None:
        interval = task.interval_for(self.mode)
        now = self.monotonic_now()
        next_due = previous_due + interval
        if next_due <= now:
            missed = int((now - next_due) // interval) + 1
            next_due += missed * interval
        task.next_due_monotonic_s = next_due

    @staticmethod
    def _phase_offset(task: ScheduledTask, interval_s: float) -> float:
        key = task.phase_key if task.phase_key is not None else task.name
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        fraction = int.from_bytes(digest[:8], "big") / float(2**64)
        return fraction * interval_s
