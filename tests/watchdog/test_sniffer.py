from __future__ import annotations

from dataclasses import dataclass

from tb4.core.retry import RetryPolicy
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.watchdog.sniffer import (
    KnownDeviceSniffer,
    KnownDeviceTarget,
    ProbeKind,
    ProbeObservation,
    Reachability,
    SniffOutcome,
)


@dataclass
class FakeClock:
    monotonic_value: float = 100.0
    epoch_value: int = 1_700_200_000

    def monotonic(self) -> float:
        return self.monotonic_value

    def epoch(self) -> int:
        return self.epoch_value

    def sleep(self, seconds: float) -> None:
        self.monotonic_value += seconds

    def advance(self, seconds: float) -> None:
        self.monotonic_value += seconds
        self.epoch_value += int(seconds)


@dataclass
class MutableProbe:
    observation: ProbeObservation
    error: Exception | None = None
    calls: int = 0

    def probe(self, target: KnownDeviceTarget) -> ProbeObservation:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.observation


def online() -> ProbeObservation:
    return ProbeObservation(
        Reachability.ONLINE,
        ProbeKind.ICMP,
        ("192.0.2.10",),
        "AA:BB:CC:DD:EE:FF",
    )


def offline() -> ProbeObservation:
    return ProbeObservation(
        Reachability.OFFLINE,
        ProbeKind.ICMP,
        ("192.0.2.10",),
        "AA:BB:CC:DD:EE:FF",
    )


def make_sniffer(probe: MutableProbe, *, freshness_s: float = 300):
    backend = InMemoryDriveBackend()
    obj = backend.create_text(backend.root_id, "DOG_SNIFF", "{}")
    assert obj.ok and obj.value is not None
    backend.reset_operation_counts()
    clock = FakeClock()
    sniffer = KnownDeviceSniffer(
        backend=backend,
        local_probe=probe,
        retry_policy=RetryPolicy((0.01, 0.02, 0.04), 3),
        freshness_s=freshness_s,
        monotonic_now=clock.monotonic,
        epoch_now=clock.epoch,
        sleeper=clock.sleep,
    )
    target = KnownDeviceTarget(
        device_id="device-001",
        dog_sniff_object_id=obj.value.metadata.object_id,
        address_hints=("192.0.2.10",),
        mac_address="AA:BB:CC:DD:EE:FF",
    )
    return backend, clock, sniffer, target


def test_unchanged_frequent_probe_does_not_write_drive() -> None:
    probe = MutableProbe(online())
    backend, clock, sniffer, target = make_sniffer(probe)

    first = sniffer.probe_once(target)
    writes = backend.operation_counts.get("replace_text", 0)

    clock.advance(20)
    second = sniffer.probe_once(target)

    assert first.outcome is SniffOutcome.PUBLISHED_CHANGE
    assert second.outcome is SniffOutcome.UNCHANGED
    assert backend.operation_counts.get("replace_text", 0) == writes
    assert backend.operation_counts.get("list_children", 0) == 0


def test_online_to_offline_publishes_immediately() -> None:
    probe = MutableProbe(online())
    backend, clock, sniffer, target = make_sniffer(probe)
    sniffer.probe_once(target)
    writes = backend.operation_counts.get("replace_text", 0)

    clock.advance(20)
    probe.observation = offline()
    result = sniffer.probe_once(target)

    assert result.outcome is SniffOutcome.PUBLISHED_CHANGE
    assert result.observation.reachability is Reachability.OFFLINE
    assert backend.operation_counts.get("replace_text", 0) == writes + 1


def test_offline_to_online_publishes_immediately() -> None:
    probe = MutableProbe(offline())
    backend, clock, sniffer, target = make_sniffer(probe)
    sniffer.probe_once(target)

    clock.advance(20)
    probe.observation = online()
    result = sniffer.probe_once(target)

    assert result.outcome is SniffOutcome.PUBLISHED_CHANGE
    assert result.observation.reachability is Reachability.ONLINE


def test_unchanged_observation_republishes_at_freshness_deadline() -> None:
    probe = MutableProbe(online())
    backend, clock, sniffer, target = make_sniffer(probe, freshness_s=300)
    first = sniffer.probe_once(target)
    writes = backend.operation_counts.get("replace_text", 0)

    clock.advance(299)
    assert sniffer.probe_once(target).outcome is SniffOutcome.UNCHANGED
    assert backend.operation_counts.get("replace_text", 0) == writes

    clock.advance(1)
    refreshed = sniffer.probe_once(target)
    assert refreshed.outcome is SniffOutcome.PUBLISHED_FRESHNESS
    assert refreshed.sequence == first.sequence + 1
    assert backend.operation_counts.get("replace_text", 0) == writes + 1


def test_probe_exception_becomes_unknown_evidence_not_exception() -> None:
    probe = MutableProbe(online(), error=OSError("host probe failed"))
    _, _, sniffer, target = make_sniffer(probe)

    result = sniffer.probe_once(target)

    assert result.outcome is SniffOutcome.PUBLISHED_CHANGE
    assert result.observation.reachability is Reachability.UNKNOWN
    assert result.observation.probe_kind is ProbeKind.NONE
    assert "OSError" in (result.probe_error or "")


def test_one_target_failure_does_not_poison_other_target_state() -> None:
    probe = MutableProbe(online())
    backend, clock, sniffer, target_a = make_sniffer(probe)

    second = backend.create_text(backend.root_id, "DOG_SNIFF", "{}")
    assert second.ok and second.value is not None
    target_b = KnownDeviceTarget(
        device_id="device-002",
        dog_sniff_object_id=second.value.metadata.object_id,
        address_hints=("192.0.2.11",),
    )

    assert sniffer.probe_once(target_a).outcome is SniffOutcome.PUBLISHED_CHANGE
    probe.error = RuntimeError("target-b probe blew up")
    unknown = sniffer.probe_once(target_b)
    assert unknown.observation.reachability is Reachability.UNKNOWN

    probe.error = None
    clock.advance(20)
    unchanged_a = sniffer.probe_once(target_a)
    assert unchanged_a.outcome is SniffOutcome.UNCHANGED


def test_delayed_drive_visibility_confirms_without_second_write() -> None:
    probe = MutableProbe(online())
    backend, _, sniffer, target = make_sniffer(probe)
    backend.delay_next_mutation_visibility(reads=2)

    result = sniffer.probe_once(target)

    assert result.outcome is SniffOutcome.PUBLISHED_CHANGE
    assert result.confirmation_probes == 3
    assert backend.operation_counts.get("replace_text", 0) == 1
