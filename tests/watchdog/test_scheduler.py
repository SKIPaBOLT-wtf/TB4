from __future__ import annotations

from dataclasses import dataclass

from tb4.watchdog.scheduler import (
    DispatchReason,
    DogMode,
    ScheduledTask,
    WatchdogScheduler,
)


@dataclass
class FakeClock:
    value: float = 100.0

    def now(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_tasks_run_in_deadline_then_name_order() -> None:
    clock = FakeClock()
    seen: list[str] = []
    scheduler = WatchdogScheduler(clock.now)

    scheduler.register(
        ScheduledTask("z-task", lambda _: seen.append("z"), 10, next_due_monotonic_s=105)
    )
    scheduler.register(
        ScheduledTask("a-task", lambda _: seen.append("a"), 10, next_due_monotonic_s=105)
    )
    scheduler.register(
        ScheduledTask("first", lambda _: seen.append("first"), 10, next_due_monotonic_s=103)
    )

    clock.advance(5)
    assert scheduler.run_due() == 3
    assert seen == ["first", "a", "z"]


def test_phase_offsets_are_deterministic_and_spread_devices() -> None:
    clock = FakeClock()

    def due_for(key: str) -> float:
        scheduler = WatchdogScheduler(clock.now)
        task = ScheduledTask(
            "known-device-probe",
            lambda _: None,
            20,
            phase_key=key,
        )
        scheduler.register(task)
        assert task.next_due_monotonic_s is not None
        return task.next_due_monotonic_s

    a1 = due_for("target-a:known-device-probe")
    a2 = due_for("target-a:known-device-probe")
    b = due_for("target-b:known-device-probe")

    assert a1 == a2
    assert a1 != b
    assert 100 <= a1 < 120
    assert 100 <= b < 120


def test_dog_mode_switch_rebases_only_mode_sensitive_tasks() -> None:
    clock = FakeClock()
    scheduler = WatchdogScheduler(clock.now)
    fast = ScheduledTask(
        "heartbeat",
        lambda _: None,
        snooze_interval_s=30,
        awake_interval_s=10,
        phase_key="watchdog:heartbeat",
    )
    fixed = ScheduledTask(
        "stray-scan",
        lambda _: None,
        snooze_interval_s=600,
        phase_key="watchdog:stray-scan",
    )
    scheduler.register(fast)
    scheduler.register(fixed)
    fixed_due = fixed.next_due_monotonic_s
    snooze_due = fast.next_due_monotonic_s

    scheduler.set_mode(DogMode.AWAKE)

    assert fast.next_due_monotonic_s != snooze_due
    assert fixed.next_due_monotonic_s == fixed_due


def test_event_dispatch_does_not_reset_periodic_deadline() -> None:
    clock = FakeClock()
    reasons: list[DispatchReason] = []
    scheduler = WatchdogScheduler(clock.now)
    task = ScheduledTask(
        "wake-bone-watch",
        reasons.append,
        60,
        next_due_monotonic_s=150,
    )
    scheduler.register(task)

    scheduler.trigger("wake-bone-watch")
    assert scheduler.next_wakeup_in() == 0
    assert scheduler.run_due() == 1

    assert reasons == [DispatchReason.EVENT]
    assert task.next_due_monotonic_s == 150
    assert scheduler.next_wakeup_in() == 50


def test_slow_helper_preserves_other_task_timing_state() -> None:
    clock = FakeClock()
    seen: list[str] = []
    scheduler = WatchdogScheduler(clock.now)

    def slow(_: DispatchReason) -> None:
        seen.append("slow")
        clock.advance(7)

    scheduler.register(
        ScheduledTask("slow", slow, 10, next_due_monotonic_s=101)
    )
    scheduler.register(
        ScheduledTask("other", lambda _: seen.append("other"), 10, next_due_monotonic_s=105)
    )

    clock.advance(1)
    assert scheduler.run_due() == 2
    assert seen == ["slow", "other"]
    assert scheduler.tasks["slow"].next_due_monotonic_s == 111
    assert scheduler.tasks["other"].next_due_monotonic_s == 115


def test_missed_intervals_are_skipped_not_replayed_as_burst() -> None:
    clock = FakeClock()
    calls = 0

    def callback(_: DispatchReason) -> None:
        nonlocal calls
        calls += 1

    scheduler = WatchdogScheduler(clock.now)
    scheduler.register(
        ScheduledTask("probe", callback, 10, next_due_monotonic_s=101)
    )

    clock.advance(100)
    assert scheduler.run_due() == 1
    assert calls == 1
    assert scheduler.tasks["probe"].next_due_monotonic_s > clock.now()


def test_callback_exception_is_recorded_and_other_tasks_continue() -> None:
    clock = FakeClock()
    seen: list[str] = []
    scheduler = WatchdogScheduler(clock.now)

    def broken(_: DispatchReason) -> None:
        raise RuntimeError("bad dog")

    scheduler.register(
        ScheduledTask("broken", broken, 10, next_due_monotonic_s=101)
    )
    scheduler.register(
        ScheduledTask("healthy", lambda _: seen.append("healthy"), 10, next_due_monotonic_s=101)
    )

    clock.advance(1)
    assert scheduler.run_due() == 2
    assert seen == ["healthy"]
    assert scheduler.tasks["broken"].metrics.failures == 1
    assert scheduler.metrics().failures == 1


def test_scheduler_has_no_wakeup_without_tasks_and_reports_future_delay() -> None:
    clock = FakeClock()
    scheduler = WatchdogScheduler(clock.now)

    assert scheduler.next_wakeup_in() is None

    scheduler.register(
        ScheduledTask("audit", lambda _: None, 100, next_due_monotonic_s=125)
    )
    assert scheduler.next_wakeup_in() == 25
    assert scheduler.run_due() == 0
