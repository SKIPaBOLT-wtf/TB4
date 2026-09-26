from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from tb4.core.retry import RetryPolicy
from tb4.drive.body_keeper import BodyKeeper
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.drive.state_walker import StateWalker
from tb4.watchdog.sniffer import KnownDeviceTarget, ProbeKind, ProbeObservation, Reachability
from tb4.watchdog.ssh_bootstrap import (
    BootstrapPlatform,
    BootstrapTarget,
    DoorScratchOutcome,
    DoorScratchReport,
)
from tb4.watchdog.wake_manager import WakeManager, WakeManagerOutcome, WakeTiming
from tb4.watchdog.wol import BoneThrowOutcome, BoneThrowReport, WakeTarget


ROOT = Path(__file__).resolve().parents[2]


@dataclass
class FakeClock:
    monotonic_value: float = 100.0
    epoch_value: int = 1_700_001_001

    def monotonic(self):
        return self.monotonic_value

    def epoch(self):
        value = self.epoch_value
        self.epoch_value += 1
        return value

    def sleep(self, seconds):
        self.monotonic_value += seconds
        self.epoch_value += int(seconds)


@dataclass
class FakeProbe:
    states: list[Reachability]

    def probe(self, target):
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return ProbeObservation(state, ProbeKind.ICMP, target.address_hints)


@dataclass
class FakeBone:
    outcome: BoneThrowOutcome = BoneThrowOutcome.SENT
    calls: int = 0

    def throw(self, target):
        self.calls += 1
        return BoneThrowReport(self.outcome, 102 if self.outcome is BoneThrowOutcome.SENT else 0)


@dataclass
class FakeDoor:
    outcome: DoorScratchOutcome = DoorScratchOutcome.STARTED
    calls: int = 0
    on_call: callable | None = None

    def scratch(self, target):
        self.calls += 1
        if self.on_call:
            self.on_call()
        return DoorScratchReport(
            self.outcome,
            service_running=self.outcome in {DoorScratchOutcome.STARTED, DoorScratchOutcome.ALREADY_RUNNING},
            protocol_ready=False,
        )


def toss_body():
    return json.loads((ROOT / "protocol" / "examples" / "wake-bone" / "toss.json").read_text())


def pulse_body(*, emitted_at: int, device_id="target-a"):
    return {
        "schema_version": 1,
        "protocol_major": 1,
        "device_id": device_id,
        "emitted_at": emitted_at,
        "sequence": 1,
        "instance_id": "fetcher-instance-001",
        "claimed_generation": None,
        "claimed_operation_id": None,
    }


def make_manager(
    *,
    probe_states=(Reachability.ONLINE,),
    pulse=None,
    bone=None,
    door=None,
    body=None,
    clock=None,
):
    backend = InMemoryDriveBackend()
    clock = clock or FakeClock()
    body = body or toss_body()
    wake = backend.create_text(
        backend.root_id,
        "WAKE_BONE_TOSS",
        json.dumps(body, sort_keys=True, separators=(",", ":")),
    )
    pulse_obj = backend.create_text(
        backend.root_id,
        "DOG_PULSE",
        json.dumps(pulse or pulse_body(emitted_at=1), sort_keys=True, separators=(",", ":")),
    )
    assert wake.ok and wake.value and pulse_obj.ok and pulse_obj.value

    policy = RetryPolicy((0.01, 0.02, 0.04), 3)
    walker = StateWalker(backend, policy, clock.monotonic, clock.sleep)
    keeper = BodyKeeper(backend, policy, clock.monotonic, clock.sleep)

    manager = WakeManager(
        backend=backend,
        state_walker=walker,
        body_keeper=keeper,
        bone_thrower=bone or FakeBone(),
        door_scratcher=door or FakeDoor(),
        local_probe=FakeProbe(list(probe_states)),
        wake_bone_object_id=wake.value.metadata.object_id,
        dog_pulse_object_id=pulse_obj.value.metadata.object_id,
        target_device_id="target-a",
        probe_target=KnownDeviceTarget("target-a", "unused", ("192.0.2.10",)),
        wake_target=WakeTarget(True, "00:11:22:33:44:55", "192.0.2.255"),
        bootstrap_target=BootstrapTarget(True, "target-a.local", "cred-a", BootstrapPlatform.LINUX_SYSTEMD),
        timing=WakeTiming(10, 5, 90, 35, 10),
        monotonic_now=clock.monotonic,
        epoch_now=clock.epoch,
        sleeper=clock.sleep,
    )
    backend.reset_operation_counts()
    return backend, clock, manager, wake.value.metadata.object_id, pulse_obj.value.metadata.object_id


def test_already_ready_target_completes_without_wol_or_ssh():
    clock = FakeClock()
    bone = FakeBone()
    door = FakeDoor()
    _, _, manager, wake_id, _ = make_manager(
        pulse=pulse_body(emitted_at=clock.epoch_value),
        bone=bone,
        door=door,
        clock=clock,
    )

    result = manager.process_toss()

    assert result.outcome is WakeManagerOutcome.DONE
    assert result.reason_code == "FETCHER_READY"
    assert bone.calls == 0
    assert door.calls == 0
    assert manager.backend.get_metadata(wake_id).value.name == "WAKE_BONE_DONE"


def test_offline_target_gets_one_wol_then_ready_pulse():
    clock = FakeClock()
    bone = FakeBone()
    backend, _, manager, _, pulse_id = make_manager(
        probe_states=(Reachability.OFFLINE, Reachability.ONLINE),
        bone=bone,
        clock=clock,
    )

    # Make the target publish a fresh pulse when local probing first sees it online.
    original_probe = manager.local_probe
    class Probe:
        calls = 0
        def probe(self, target):
            self.calls += 1
            if self.calls == 1:
                return ProbeObservation(Reachability.OFFLINE, ProbeKind.ICMP, target.address_hints)
            current = backend.get_metadata(pulse_id).value
            backend.replace_text(
                pulse_id,
                json.dumps(pulse_body(emitted_at=clock.epoch_value), sort_keys=True, separators=(",", ":")),
                expected_version_token=current.version_token,
            )
            return ProbeObservation(Reachability.ONLINE, ProbeKind.ICMP, target.address_hints)
    manager.local_probe = Probe()

    result = manager.process_toss()

    assert result.outcome is WakeManagerOutcome.DONE
    assert bone.calls == 1


def test_online_target_can_bootstrap_then_requires_fresh_pulse():
    clock = FakeClock()
    backend, _, manager, _, pulse_id = make_manager(clock=clock)
    def publish():
        meta = backend.get_metadata(pulse_id).value
        backend.replace_text(
            pulse_id,
            json.dumps(pulse_body(emitted_at=clock.epoch_value), sort_keys=True, separators=(",", ":")),
            expected_version_token=meta.version_token,
        )
    door = FakeDoor(on_call=publish)
    manager.door_scratcher = door

    result = manager.process_toss()

    assert result.outcome is WakeManagerOutcome.DONE
    assert door.calls == 1
    assert result.reason_code == "FETCHER_READY"


def test_ssh_success_without_pulse_never_becomes_done():
    clock = FakeClock()
    _, _, manager, _, _ = make_manager(clock=clock, door=FakeDoor())

    result = manager.process_toss()

    assert result.outcome is WakeManagerOutcome.FAILED
    assert result.reason_code == "WAKE_DEADLINE"


def test_expired_toss_is_failed_without_wol_or_ssh():
    clock = FakeClock(epoch_value=1_700_002_000)
    body = toss_body()
    body["expires_at"] = 1_700_001_500
    bone = FakeBone()
    door = FakeDoor()
    backend, _, manager, wake_id, _ = make_manager(body=body, clock=clock, bone=bone, door=door)

    result = manager.process_toss()

    assert result.outcome is WakeManagerOutcome.EXPIRED
    assert bone.calls == 0
    assert door.calls == 0
    assert backend.get_metadata(wake_id).value.name == "WAKE_BONE_FAILED"


def test_offline_without_wol_capability_fails_target_locally():
    bone = FakeBone(BoneThrowOutcome.NOT_CAPABLE)
    _, _, manager, _, _ = make_manager(
        probe_states=(Reachability.OFFLINE,),
        bone=bone,
    )

    result = manager.process_toss()

    assert result.outcome is WakeManagerOutcome.FAILED
    assert result.reason_code == "TARGET_OFFLINE_NO_WOL"


def test_delayed_toss_to_chew_visibility_is_confirmed_before_body_write():
    backend, _, manager, _, _ = make_manager(
        pulse=pulse_body(emitted_at=1_700_001_001),
    )
    backend.delay_next_mutation_visibility(reads=2)

    result = manager.process_toss()

    assert result.outcome is WakeManagerOutcome.DONE
    assert backend.operation_counts.get("list_children", 0) == 0
