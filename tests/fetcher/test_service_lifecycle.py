from __future__ import annotations

from dataclasses import dataclass

from tb4.core.retry import RetryPolicy
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.fetcher.heartbeat import HeartbeatPublisher
from tb4.fetcher.idle_manager import IdleDecision, IdleManager
from tb4.fetcher.service import FetcherServiceLifecycle, StartupDisposition


@dataclass
class FakeClock:
    monotonic_value: float = 100.0
    epoch_value: int = 1_700_100_000

    def monotonic(self) -> float:
        return self.monotonic_value

    def epoch(self) -> int:
        return self.epoch_value

    def sleep(self, seconds: float) -> None:
        self.monotonic_value += seconds

    def advance(self, seconds: float) -> None:
        self.monotonic_value += seconds
        self.epoch_value += int(seconds)


def make_service(
    *,
    fetch_state: str = "READY",
    stop_state: str = "READY",
    child_active=lambda: False,
    cancellation_active=lambda: False,
    idle_exit_s: float = 600,
):
    backend = InMemoryDriveBackend()
    fetch = backend.create_text(backend.root_id, f"FETCH_BALL_{fetch_state}", "{}")
    stop = backend.create_text(backend.root_id, f"STOP_BALL_{stop_state}", "{}")
    pulse = backend.create_text(backend.root_id, "DOG_PULSE", "{}")
    assert fetch.ok and fetch.value is not None
    assert stop.ok and stop.value is not None
    assert pulse.ok and pulse.value is not None

    clock = FakeClock()
    heartbeat = HeartbeatPublisher(
        backend=backend,
        dog_pulse_object_id=pulse.value.metadata.object_id,
        device_id="target-a",
        instance_id="fetcher-instance-038",
        idle_interval_s=60,
        active_interval_s=10,
        retry_policy=RetryPolicy((0.01, 0.02, 0.04), 3),
        monotonic_now=clock.monotonic,
        epoch_now=clock.epoch,
        sleeper=clock.sleep,
    )
    idle = IdleManager(idle_exit_s=idle_exit_s, monotonic_now=clock.monotonic)
    service = FetcherServiceLifecycle(
        backend=backend,
        fetch_ball_object_id=fetch.value.metadata.object_id,
        stop_ball_object_id=stop.value.metadata.object_id,
        heartbeat=heartbeat,
        idle_manager=idle,
        child_active=child_active,
        cancellation_active=cancellation_active,
    )
    backend.reset_operation_counts()
    return backend, clock, service


def test_startup_ready_publishes_heartbeat_and_is_idle_eligible() -> None:
    backend, _, service = make_service()

    snapshot = service.startup_inspect()

    assert snapshot.disposition is StartupDisposition.READY
    assert snapshot.heartbeat_published is True
    assert backend.operation_counts.get("list_children", 0) == 0
    assert service.tick_idle().idle_decision is IdleDecision.IDLE_COUNTING


def test_startup_pending_toss_is_work_available_not_resumed_work() -> None:
    backend, _, service = make_service(fetch_state="TOSS")

    snapshot = service.startup_inspect()

    assert snapshot.disposition is StartupDisposition.WORK_AVAILABLE
    assert snapshot.fetch_ball_state == "TOSS"
    assert service.tick_idle().idle_decision is IdleDecision.BUSY
    assert backend.operation_counts.get("list_children", 0) == 0


def test_restart_with_preexisting_chew_never_reexecutes_or_fabricates_result() -> None:
    backend, _, service = make_service(fetch_state="CHEW")

    snapshot = service.startup_inspect()

    assert snapshot.disposition is StartupDisposition.STALE_EXECUTION
    state = backend.get_metadata(service.fetch_ball_object_id)
    assert state.ok and state.value is not None
    assert state.value.name == "FETCH_BALL_CHEW"
    assert backend.operation_counts.get("rename", 0) == 0
    assert backend.operation_counts.get("replace_text", 0) == 1  # heartbeat only


def test_restart_with_returning_leaves_recovery_to_watchdog() -> None:
    backend, _, service = make_service(fetch_state="RETURNING")

    snapshot = service.startup_inspect()

    assert snapshot.disposition is StartupDisposition.INCOMPLETE_RETURN
    state = backend.get_metadata(service.fetch_ball_object_id)
    assert state.ok and state.value is not None
    assert state.value.name == "FETCH_BALL_RETURNING"
    assert backend.operation_counts.get("rename", 0) == 0


def test_stale_stop_ball_blocks_ready_idle_exit_until_control_channel_reusable() -> None:
    _, _, service = make_service(stop_state="REQUESTED")

    snapshot = service.startup_inspect()

    assert snapshot.disposition is StartupDisposition.CONTROL_PENDING
    assert service.tick_idle().idle_decision is IdleDecision.BUSY


def test_idle_exit_occurs_only_after_full_configured_interval() -> None:
    _, clock, service = make_service(idle_exit_s=600)

    assert service.tick_idle().idle_decision is IdleDecision.IDLE_COUNTING
    clock.advance(599)
    assert service.tick_idle().idle_decision is IdleDecision.IDLE_COUNTING
    clock.advance(1)
    assert service.tick_idle().idle_decision is IdleDecision.EXIT_IDLE


def test_active_child_prevents_exit_and_resets_timer() -> None:
    child = {"active": False}
    _, clock, service = make_service(
        idle_exit_s=10,
        child_active=lambda: child["active"],
    )

    assert service.tick_idle().idle_decision is IdleDecision.IDLE_COUNTING
    clock.advance(9)
    child["active"] = True
    assert service.tick_idle().idle_decision is IdleDecision.BUSY

    clock.advance(100)
    child["active"] = False
    assert service.tick_idle().idle_decision is IdleDecision.IDLE_COUNTING
    clock.advance(10)
    assert service.tick_idle().idle_decision is IdleDecision.EXIT_IDLE


def test_cancellation_handling_prevents_idle_exit() -> None:
    cancelling = {"active": True}
    _, clock, service = make_service(
        idle_exit_s=5,
        cancellation_active=lambda: cancelling["active"],
    )

    assert service.tick_idle().idle_decision is IdleDecision.BUSY
    clock.advance(100)
    cancelling["active"] = False
    assert service.tick_idle().idle_decision is IdleDecision.IDLE_COUNTING
