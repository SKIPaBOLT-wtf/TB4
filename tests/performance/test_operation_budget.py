from __future__ import annotations

from dataclasses import dataclass

from tb4.core.retry import RetryPolicy
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.fetcher.execution_models import ExecutionDisposition
from tb4.testing.simulation import SimulationHarness, execution_report
from tb4.watchdog.scheduler import ScheduledTask, WatchdogScheduler
from tb4.watchdog.sniffer import (
    KnownDeviceSniffer,
    KnownDeviceTarget,
    ProbeKind,
    ProbeObservation,
    Reachability,
)


@dataclass
class FakeClock:
    monotonic_value: float = 0.0
    epoch_value: int = 1_700_300_000

    def monotonic(self) -> float:
        return self.monotonic_value

    def epoch(self) -> int:
        return self.epoch_value

    def advance(self, seconds: float) -> None:
        self.monotonic_value += seconds
        self.epoch_value += int(seconds)

    def sleep(self, seconds: float) -> None:
        self.advance(seconds)


@dataclass
class StableProbe:
    calls: int = 0

    def probe(self, target: KnownDeviceTarget) -> ProbeObservation:
        self.calls += 1
        return ProbeObservation(
            Reachability.ONLINE,
            ProbeKind.ICMP,
            target.address_hints,
            target.mac_address,
        )


def test_idle_scheduler_sleeps_to_next_deadline_instead_of_busy_looping() -> None:
    clock = FakeClock()
    scheduler = WatchdogScheduler(clock.monotonic)
    dispatches: dict[str, int] = {
        "heartbeat": 0,
        "known-probe": 0,
        "stray-scan": 0,
        "retention": 0,
        "full-audit": 0,
    }

    def callback(name: str):
        def run(_reason) -> None:
            dispatches[name] += 1
        return run

    scheduler.register(ScheduledTask("heartbeat", callback("heartbeat"), 30, phase_key="watchdog:heartbeat"))
    scheduler.register(ScheduledTask("known-probe", callback("known-probe"), 20, phase_key="target-a:known-probe"))
    scheduler.register(ScheduledTask("stray-scan", callback("stray-scan"), 600, phase_key="watchdog:stray-scan"))
    scheduler.register(ScheduledTask("retention", callback("retention"), 3600, phase_key="watchdog:retention"))
    scheduler.register(ScheduledTask("full-audit", callback("full-audit"), 21600, phase_key="watchdog:full-audit"))

    end = 3600.0
    while clock.monotonic() < end:
        wait = scheduler.next_wakeup_in()
        assert wait is not None
        assert wait >= 0
        if clock.monotonic() + wait > end:
            clock.advance(end - clock.monotonic())
            break
        clock.advance(wait)
        assert scheduler.run_due() >= 1

    metrics = scheduler.metrics()
    # Event-driven sleeping should require only actual timer deadlines, not
    # thousands/millions of empty wakeups over an hour.
    assert metrics.wakeups <= 320
    assert metrics.dispatches <= 320
    assert dispatches["known-probe"] <= 180
    assert dispatches["heartbeat"] <= 120
    assert dispatches["stray-scan"] <= 6
    assert dispatches["retention"] <= 1
    assert dispatches["full-audit"] <= 1


def test_unchanged_known_device_probes_publish_at_most_freshness_rate() -> None:
    backend = InMemoryDriveBackend()
    dog_sniff = backend.create_text(backend.root_id, "DOG_SNIFF", "{}")
    assert dog_sniff.ok and dog_sniff.value is not None
    backend.reset_operation_counts()

    clock = FakeClock()
    probe = StableProbe()
    sniffer = KnownDeviceSniffer(
        backend=backend,
        local_probe=probe,
        retry_policy=RetryPolicy((0.01, 0.02, 0.04), 3),
        freshness_s=300,
        monotonic_now=clock.monotonic,
        epoch_now=clock.epoch,
        sleeper=clock.sleep,
    )
    target = KnownDeviceTarget(
        "target-a",
        dog_sniff.value.metadata.object_id,
        ("192.0.2.10",),
        "AA:BB:CC:DD:EE:FF",
    )

    # 31 local probes at the configured 20-second cadence span ten minutes.
    # Stable state should publish only initially and at 300/600s freshness.
    for index in range(31):
        sniffer.probe_once(target)
        if index != 30:
            clock.advance(20)

    assert probe.calls == 31
    assert backend.operation_counts.get("replace_text", 0) == 3
    assert backend.operation_counts.get("list_children", 0) == 0
    # Unchanged probes return from local cached state before remote metadata/read.
    assert backend.operation_counts.get("get_metadata", 0) == 3


def test_normal_job_round_trip_stays_within_exact_object_operation_budget() -> None:
    sim = SimulationHarness()
    target = sim.add_target("target-a", online=True)
    sim.publish_pulse(target)
    sim.reset_operation_counts()

    sim.toss_job(target)
    result = sim.run_job(
        target,
        execution_report(ExecutionDisposition.EXITED, exit_code=0),
    )
    sim.recycle_job(target)

    assert result.terminal_state == "DONE"
    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_READY"
    assert sim.backend.operation_counts.get("list_children", 0) == 0

    counts = sim.backend.operation_counts
    remote_ops = sum(counts.values())
    # This is deliberately a ceiling, not an optimization target. Verification
    # reads are part of correctness and must not be removed merely to lower it.
    assert remote_ops <= 60
    assert counts.get("rename", 0) <= 7
    assert counts.get("replace_text", 0) <= 4


def test_phase_offsets_spread_many_device_probes_across_interval() -> None:
    clock = FakeClock()
    due: list[float] = []

    for index in range(64):
        scheduler = WatchdogScheduler(clock.monotonic)
        task = ScheduledTask(
            "known-device-probe",
            lambda _reason: None,
            snooze_interval_s=20,
            phase_key=f"target-{index:02d}:known-device-probe",
        )
        scheduler.register(task)
        assert task.next_due_monotonic_s is not None
        due.append(task.next_due_monotonic_s)

    assert all(0 <= value < 20 for value in due)
    assert len(set(due)) == 64
    assert max(due) - min(due) >= 15

    # Avoid a thundering herd: no two-second bucket may contain the majority
    # of the 64 devices.
    buckets: dict[int, int] = {}
    for value in due:
        bucket = int(value // 2)
        buckets[bucket] = buckets.get(bucket, 0) + 1
    assert max(buckets.values()) <= 16
