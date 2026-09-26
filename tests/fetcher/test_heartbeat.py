from __future__ import annotations

import json
from dataclasses import dataclass

from tb4.core.retry import RetryPolicy
from tb4.drive.errors import BackendOutcome
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.fetcher.heartbeat import HeartbeatOutcome, HeartbeatPublisher


@dataclass
class FakeClock:
    monotonic_value: float = 100.0
    epoch_value: int = 1_700_000_000

    def monotonic(self) -> float:
        return self.monotonic_value

    def epoch(self) -> int:
        return self.epoch_value

    def sleep(self, seconds: float) -> None:
        self.monotonic_value += seconds

    def advance(self, seconds: float) -> None:
        self.monotonic_value += seconds
        self.epoch_value += int(seconds)


def publisher(
    backend: InMemoryDriveBackend,
    object_id: str,
    clock: FakeClock,
) -> HeartbeatPublisher:
    return HeartbeatPublisher(
        backend=backend,
        dog_pulse_object_id=object_id,
        device_id="target-a",
        instance_id="fetcher-instance-001",
        idle_interval_s=60,
        active_interval_s=10,
        retry_policy=RetryPolicy((0.01, 0.02, 0.04), 3),
        monotonic_now=clock.monotonic,
        epoch_now=clock.epoch,
        sleeper=clock.sleep,
    )


def add_pulse(backend: InMemoryDriveBackend) -> str:
    created = backend.create_text(backend.root_id, "DOG_PULSE", "{}")
    assert created.ok and created.value is not None
    backend.reset_operation_counts()
    return created.value.metadata.object_id


def test_first_idle_tick_publishes_and_second_before_cadence_does_not() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeClock()
    object_id = add_pulse(backend)
    pulse = publisher(backend, object_id, clock)

    first = pulse.tick(active=False)
    second = pulse.tick(active=False)

    assert first.outcome is HeartbeatOutcome.PUBLISHED
    assert first.sequence == 1
    assert second.outcome is HeartbeatOutcome.NOT_DUE
    assert backend.operation_counts["replace_text"] == 1
    assert backend.operation_counts.get("list_children", 0) == 0


def test_active_cadence_publishes_sooner_than_idle() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeClock()
    object_id = add_pulse(backend)
    pulse = publisher(backend, object_id, clock)

    assert pulse.tick(active=False).outcome is HeartbeatOutcome.PUBLISHED
    clock.advance(11)
    assert pulse.tick(active=True).outcome is HeartbeatOutcome.PUBLISHED
    assert pulse.sequence == 2


def test_claim_identity_is_published_as_a_pair() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeClock()
    object_id = add_pulse(backend)
    pulse = publisher(backend, object_id, clock)

    result = pulse.tick(
        active=True,
        claimed_generation=7,
        claimed_operation_id="job-1700000000-a1b2c3d4",
    )

    assert result.outcome is HeartbeatOutcome.PUBLISHED
    remote = backend.read_text(object_id)
    assert remote.ok and remote.value is not None
    body = json.loads(remote.value.text)
    assert body["claimed_generation"] == 7
    assert body["claimed_operation_id"] == "job-1700000000-a1b2c3d4"


def test_sequence_advances_only_after_confirmed_publish() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeClock()
    object_id = add_pulse(backend)
    pulse = publisher(backend, object_id, clock)
    backend.inject_outcome("replace_text", BackendOutcome.TRANSIENT_ERROR)

    failed = pulse.tick(active=True)
    assert failed.outcome is HeartbeatOutcome.FAILURE
    assert pulse.sequence == 0

    # Failed attempts still consume cadence so a tight loop cannot hammer Drive.
    assert pulse.tick(active=True).outcome is HeartbeatOutcome.NOT_DUE
    clock.advance(11)

    recovered = pulse.tick(active=True)
    assert recovered.outcome is HeartbeatOutcome.PUBLISHED
    assert pulse.sequence == 1


def test_epoch_clock_regression_is_rejected_without_remote_write() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeClock()
    object_id = add_pulse(backend)
    pulse = publisher(backend, object_id, clock)

    assert pulse.tick(active=True).outcome is HeartbeatOutcome.PUBLISHED
    writes_before = backend.operation_counts["replace_text"]

    clock.advance(11)
    clock.epoch_value -= 100
    result = pulse.tick(active=True)

    assert result.outcome is HeartbeatOutcome.CLOCK_ANOMALY
    assert pulse.sequence == 1
    assert backend.operation_counts["replace_text"] == writes_before


def test_delayed_remote_visibility_confirms_without_second_write() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeClock()
    object_id = add_pulse(backend)
    pulse = publisher(backend, object_id, clock)
    backend.delay_next_mutation_visibility(reads=2)

    result = pulse.tick(active=True)

    assert result.outcome is HeartbeatOutcome.PUBLISHED
    assert result.confirmation_probes == 3
    assert backend.operation_counts["replace_text"] == 1


def test_claim_fields_must_be_set_together() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeClock()
    object_id = add_pulse(backend)
    pulse = publisher(backend, object_id, clock)

    try:
        pulse.tick(active=True, claimed_generation=1)
    except ValueError as exc:
        assert "must be set together" in str(exc)
    else:
        raise AssertionError("expected ValueError")
