from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from tb4.core.models import DeviceId
from tb4.core.protocol_names import LogicalObject, Role
from tb4.core.retry import RetryPolicy
from tb4.core.schemas import canonical_json_text
from tb4.drive.body_keeper import BodyKeeper
from tb4.drive.bootstrap import bootstrap_tree
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.drive.park_map import DeviceRegistration, ParkMap
from tb4.drive.state_walker import StateWalker
from tb4.fetcher.artifact_spool import BoundedResult
from tb4.fetcher.ball_pipeline import BallPipeline, LocalExecution
from tb4.fetcher.execution_models import ExecutionDisposition, ExecutionReport
from tb4.watchdog.sniffer import KnownDeviceTarget, ProbeKind, ProbeObservation, Reachability
from tb4.watchdog.ssh_bootstrap import (
    BootstrapPlatform,
    BootstrapTarget,
    DoorScratchOutcome,
    DoorScratchReport,
)
from tb4.watchdog.wake_manager import WakeManager, WakeTiming
from tb4.watchdog.wol import BoneThrowOutcome, BoneThrowReport, WakeTarget


ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class FakeClock:
    monotonic_value: float = 100.0
    epoch_value: int = 1_700_100_000

    def monotonic(self) -> float:
        return self.monotonic_value

    def epoch(self) -> int:
        value = self.epoch_value
        self.epoch_value += 1
        return value

    def sleep(self, seconds: float) -> None:
        self.monotonic_value += seconds
        self.epoch_value += max(0, int(seconds))


@dataclass(frozen=True, slots=True)
class TargetRefs:
    device_id: str
    root_id: str
    dog_tag_id: str
    dog_sniff_id: str
    dog_pulse_id: str
    leash_id: str
    kennel_id: str
    wake_bone_id: str
    playground_id: str
    fetch_ball_id: str
    stop_ball_id: str
    toy_box_id: str
    boneyard_id: str


@dataclass(slots=True)
class SimulatedNetwork:
    online: dict[str, bool] = field(default_factory=dict)

    def is_online(self, device_id: str) -> bool:
        return bool(self.online.get(device_id, False))


@dataclass(slots=True)
class SimulatedProbe:
    network: SimulatedNetwork

    def probe(self, target: KnownDeviceTarget) -> ProbeObservation:
        state = Reachability.ONLINE if self.network.is_online(target.device_id) else Reachability.OFFLINE
        return ProbeObservation(
            state,
            ProbeKind.ICMP,
            target.address_hints,
            target.mac_address,
        )


@dataclass(slots=True)
class SimulatedBoneThrower:
    network: SimulatedNetwork
    calls: int = 0

    def throw(self, target: WakeTarget) -> BoneThrowReport:
        self.calls += 1
        # The simulation maps the one active wake target to the manager's target.
        # WakeManager's probe is the authority that confirms readiness.
        return BoneThrowReport(BoneThrowOutcome.SENT, 102)


@dataclass(slots=True)
class SimulatedDoorScratcher:
    harness: "SimulationHarness"
    target: TargetRefs
    calls: int = 0

    def scratch(self, target: BootstrapTarget) -> DoorScratchReport:
        self.calls += 1
        self.harness.publish_pulse(self.target)
        return DoorScratchReport(
            DoorScratchOutcome.STARTED,
            service_running=True,
            protocol_ready=False,
        )


@dataclass(slots=True)
class SimulatedExecutor:
    report: ExecutionReport
    calls: int = 0

    def execute(self, body, *, now_epoch_s: int, cancel_requested=None) -> LocalExecution:
        self.calls += 1
        return LocalExecution(
            report=self.report,
            bounded=BoundedResult(
                stdout_tail=self.report.stdout,
                stderr_tail=self.report.stderr,
                result_artifact_id=None,
                result_artifact_sha256=None,
                result_artifact_size_bytes=None,
                full_output_preserved=True,
            ),
        )


class SimulationHarness:
    """Integrated in-memory TB4 harness using production protocol helpers."""

    def __init__(self) -> None:
        self.backend = InMemoryDriveBackend()
        self.clock = FakeClock()
        self.retry = RetryPolicy((0.01, 0.02, 0.04), 3)
        self.walker = StateWalker(
            self.backend,
            self.retry,
            self.clock.monotonic,
            self.clock.sleep,
        )
        self.keeper = BodyKeeper(
            self.backend,
            self.retry,
            self.clock.monotonic,
            self.clock.sleep,
        )
        report = bootstrap_tree(self.backend, root_id=self.backend.root_id)
        self.park_map = report.park_map
        self.targets: dict[str, TargetRefs] = {}
        self.network = SimulatedNetwork()

    def add_target(self, device_id: str, *, online: bool = True) -> TargetRefs:
        if device_id in self.targets:
            raise ValueError(f"target {device_id!r} already exists")
        device_key = device_id
        ball_park_id = self.park_map.lookup("BALL_PARK")

        root_id = self._folder(ball_park_id, device_key)
        dog_tag_id = self._text(root_id, "DOG_TAG", "{}\n")
        dog_sniff_id = self._text(root_id, "DOG_SNIFF", "{}\n")
        dog_pulse_id = self._text(root_id, "DOG_PULSE", canonical_json_text(self._pulse_body(device_id, emitted_at=1)))
        leash_id = self._text(root_id, "LEASH_CLEAR", "{}\n")
        kennel_id = self._folder(root_id, "KENNEL")
        wake_bone_id = self._text(kennel_id, "WAKE_BONE_READY", "{}\n")
        playground_id = self._folder(root_id, "PLAYGROUND")
        fetch_ball_id = self._text(playground_id, "FETCH_BALL_READY", canonical_json_text(self._idle_fetch_body(0)))
        stop_ball_id = self._text(playground_id, "STOP_BALL_READY", "{}\n")
        toy_box_id = self._folder(root_id, "TOY_BOX")
        boneyard_id = self._folder(root_id, "BONEYARD")

        refs = TargetRefs(
            device_id=device_id,
            root_id=root_id,
            dog_tag_id=dog_tag_id,
            dog_sniff_id=dog_sniff_id,
            dog_pulse_id=dog_pulse_id,
            leash_id=leash_id,
            kennel_id=kennel_id,
            wake_bone_id=wake_bone_id,
            playground_id=playground_id,
            fetch_ball_id=fetch_ball_id,
            stop_ball_id=stop_ball_id,
            toy_box_id=toy_box_id,
            boneyard_id=boneyard_id,
        )
        reference_map = {
            ParkMap.device_ref(device_id, "ROOT"): root_id,
            ParkMap.device_ref(device_id, "DOG_TAG"): dog_tag_id,
            ParkMap.device_ref(device_id, "DOG_SNIFF"): dog_sniff_id,
            ParkMap.device_ref(device_id, "DOG_PULSE"): dog_pulse_id,
            ParkMap.device_ref(device_id, "TARGET_LEASH"): leash_id,
            ParkMap.device_ref(device_id, "KENNEL"): kennel_id,
            ParkMap.device_ref(device_id, "KENNEL.WAKE_BONE"): wake_bone_id,
            ParkMap.device_ref(device_id, "PLAYGROUND"): playground_id,
            ParkMap.device_ref(device_id, "PLAYGROUND.FETCH_BALL"): fetch_ball_id,
            ParkMap.device_ref(device_id, "PLAYGROUND.STOP_BALL"): stop_ball_id,
            ParkMap.device_ref(device_id, "TOY_BOX"): toy_box_id,
            ParkMap.device_ref(device_id, "BONEYARD"): boneyard_id,
        }
        self.park_map = self.park_map.register_device(
            DeviceRegistration(DeviceId(device_id), device_key),
            reference_map,
        )
        map_id = self.park_map.lookup("PARK_MAP")
        meta = self.backend.get_metadata(map_id)
        assert meta.ok and meta.value is not None
        write = self.backend.replace_text(
            map_id,
            canonical_json_text(self.park_map.to_dict()),
            expected_version_token=meta.value.version_token,
        )
        assert write.ok

        self.targets[device_id] = refs
        self.network.online[device_id] = online
        return refs

    def reset_operation_counts(self) -> None:
        self.backend.reset_operation_counts()

    def state(self, object_id: str) -> str:
        meta = self.backend.get_metadata(object_id)
        assert meta.ok and meta.value is not None
        return meta.value.name

    def publish_pulse(self, target: TargetRefs) -> None:
        meta = self.backend.get_metadata(target.dog_pulse_id)
        assert meta.ok and meta.value is not None
        write = self.backend.replace_text(
            target.dog_pulse_id,
            canonical_json_text(
                self._pulse_body(target.device_id, emitted_at=self.clock.epoch())
            ),
            expected_version_token=meta.value.version_token,
        )
        assert write.ok

    def toss_job(
        self,
        target: TargetRefs,
        *,
        payload: str = "echo simulated",
        generation: int = 1,
    ) -> dict:
        now = self.clock.epoch()
        body = self._fetch_toss_body(
            generation=generation,
            operation_id=f"job-{target.device_id}-{generation:04d}",
            now=now,
            payload=payload,
        )
        self._walk(target.fetch_ball_id, LogicalObject.FETCH_BALL, "READY", "LOADING", Role.COACH)
        write = self.keeper.replace_verified(
            object_id=target.fetch_ball_id,
            logical_object=LogicalObject.FETCH_BALL,
            state="LOADING",
            actor=Role.COACH,
            schema_name="fetch-ball.schema.json",
            body=body,
        )
        assert write.success, write
        self._walk(target.fetch_ball_id, LogicalObject.FETCH_BALL, "LOADING", "TOSS", Role.COACH)
        return body

    def run_job(self, target: TargetRefs, report: ExecutionReport):
        pipeline = BallPipeline(
            backend=self.backend,
            state_walker=self.walker,
            body_keeper=self.keeper,
            executor=SimulatedExecutor(report),
            epoch_now=self.clock.epoch,
        )
        return pipeline.process_one(target.fetch_ball_id)

    def recycle_job(self, target: TargetRefs) -> None:
        current = self.state(target.fetch_ball_id)
        if not current.startswith("FETCH_BALL_"):
            raise AssertionError(current)
        terminal = current.removeprefix("FETCH_BALL_")
        remote = self.backend.read_text(target.fetch_ball_id)
        assert remote.ok and remote.value is not None
        body = json.loads(remote.value.text)
        generation = int(body["generation"])

        self._walk(
            target.fetch_ball_id,
            LogicalObject.FETCH_BALL,
            terminal,
            "RECYCLING",
            Role.COACH,
        )
        idle = self._idle_fetch_body(generation)
        write = self.keeper.replace_verified(
            object_id=target.fetch_ball_id,
            logical_object=LogicalObject.FETCH_BALL,
            state="RECYCLING",
            actor=Role.COACH,
            schema_name="fetch-ball.schema.json",
            body=idle,
        )
        assert write.success, write
        self._walk(
            target.fetch_ball_id,
            LogicalObject.FETCH_BALL,
            "RECYCLING",
            "READY",
            Role.COACH,
        )

    def toss_wake(self, target: TargetRefs, *, generation: int = 1) -> dict:
        now = self.clock.epoch()
        body = self._wake_toss_body(target.device_id, generation, now)
        self._walk(target.wake_bone_id, LogicalObject.WAKE_BONE, "READY", "LOADING", Role.COACH)
        write = self.keeper.replace_verified(
            object_id=target.wake_bone_id,
            logical_object=LogicalObject.WAKE_BONE,
            state="LOADING",
            actor=Role.COACH,
            schema_name="wake-bone.schema.json",
            body=body,
        )
        assert write.success, write
        self._walk(target.wake_bone_id, LogicalObject.WAKE_BONE, "LOADING", "TOSS", Role.COACH)
        return body

    def run_wake(self, target: TargetRefs):
        probe = SimulatedProbe(self.network)

        class Bone:
            calls = 0
            def throw(inner_self, wake_target):
                inner_self.calls += 1
                self.network.online[target.device_id] = True
                return BoneThrowReport(BoneThrowOutcome.SENT, 102)

        door = SimulatedDoorScratcher(self, target)
        manager = WakeManager(
            backend=self.backend,
            state_walker=self.walker,
            body_keeper=self.keeper,
            bone_thrower=Bone(),
            door_scratcher=door,
            local_probe=probe,
            wake_bone_object_id=target.wake_bone_id,
            dog_pulse_object_id=target.dog_pulse_id,
            target_device_id=target.device_id,
            probe_target=KnownDeviceTarget(
                target.device_id,
                target.dog_sniff_id,
                ("192.0.2.10",),
                "00:11:22:33:44:55",
            ),
            wake_target=WakeTarget(True, "00:11:22:33:44:55", "192.0.2.255"),
            bootstrap_target=BootstrapTarget(
                True,
                f"{target.device_id}.example.invalid",
                f"credential-ref-{target.device_id}",
                BootstrapPlatform.LINUX_SYSTEMD,
            ),
            timing=WakeTiming(1, 1, 15, 35, 10),
            monotonic_now=self.clock.monotonic,
            epoch_now=self.clock.epoch,
            sleeper=self.clock.sleep,
        )
        return manager.process_toss()

    def mark_job_gone(self, target: TargetRefs) -> None:
        remote = self.backend.read_text(target.fetch_ball_id)
        assert remote.ok and remote.value is not None
        body = json.loads(remote.value.text)
        self._walk(
            target.fetch_ball_id,
            LogicalObject.FETCH_BALL,
            "TOSS",
            "CHEW",
            Role.FETCHER,
        )
        body["started_at"] = self.clock.epoch()
        started = self.keeper.replace_verified(
            object_id=target.fetch_ball_id,
            logical_object=LogicalObject.FETCH_BALL,
            state="CHEW",
            actor=Role.FETCHER,
            schema_name="fetch-ball.schema.json",
            body=body,
        )
        assert started.success, started
        self._walk(
            target.fetch_ball_id,
            LogicalObject.FETCH_BALL,
            "CHEW",
            "GONE",
            Role.WATCHDOG,
        )
        body.update(
            finished_at=self.clock.epoch(),
            result_code="GONE",
            reason_code="FETCHER_LOST",
            exit_code=None,
            stdout_tail=None,
            stderr_tail=None,
            effects_known="UNKNOWN",
            completed_effects=[],
            result_artifact_ids=[],
            result_sha256="b" * 64,
        )
        gone = self.keeper.replace_verified(
            object_id=target.fetch_ball_id,
            logical_object=LogicalObject.FETCH_BALL,
            state="GONE",
            actor=Role.WATCHDOG,
            schema_name="fetch-ball.schema.json",
            body=body,
        )
        assert gone.success, gone

    def _walk(
        self,
        object_id: str,
        logical_object: LogicalObject,
        expected: str,
        target: str,
        actor: Role,
    ) -> None:
        report = self.walker.walk(
            object_id=object_id,
            logical_object=logical_object,
            expected_state=expected,
            target_state=target,
            actor=actor,
        )
        assert report.success, report

    def _folder(self, parent_id: str, name: str) -> str:
        result = self.backend.create_folder(parent_id, name)
        assert result.ok and result.value is not None
        return result.value.metadata.object_id

    def _text(self, parent_id: str, name: str, text: str) -> str:
        result = self.backend.create_text(parent_id, name, text)
        assert result.ok and result.value is not None
        return result.value.metadata.object_id

    @staticmethod
    def _pulse_body(device_id: str, *, emitted_at: int) -> dict:
        return {
            "schema_version": 1,
            "protocol_major": 1,
            "device_id": device_id,
            "emitted_at": emitted_at,
            "sequence": max(1, emitted_at),
            "instance_id": f"sim-fetcher-{device_id}",
            "claimed_generation": None,
            "claimed_operation_id": None,
        }

    @staticmethod
    def _idle_fetch_body(generation: int) -> dict:
        return {
            "schema_version": 1,
            "protocol_major": 1,
            "protocol_minor": 0,
            "generation": generation,
            "operation_id": None,
            "given_at": 0,
            "expires_at": 0,
            "started_at": 0,
            "finished_at": 0,
            "run_limit_s": 0,
            "payload_sha256": None,
            "result_sha256": None,
            "artifact_refs": [],
            "payload_source": None,
            "payload_type": None,
            "inline_payload": None,
            "payload_artifact_id": None,
            "runtime_hint": None,
            "result_code": None,
            "reason_code": None,
            "exit_code": None,
            "stdout_tail": None,
            "stderr_tail": None,
            "effects_known": None,
            "completed_effects": [],
            "result_artifact_ids": [],
        }

    @staticmethod
    def _fetch_toss_body(*, generation: int, operation_id: str, now: int, payload: str) -> dict:
        return {
            "schema_version": 1,
            "protocol_major": 1,
            "protocol_minor": 0,
            "generation": generation,
            "operation_id": operation_id,
            "given_at": now,
            "expires_at": now + 120,
            "started_at": 0,
            "finished_at": 0,
            "run_limit_s": 300,
            "payload_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            "result_sha256": None,
            "artifact_refs": [],
            "payload_source": "INLINE",
            "payload_type": "SHELL",
            "inline_payload": payload,
            "payload_artifact_id": None,
            "runtime_hint": "bash",
            "result_code": None,
            "reason_code": None,
            "exit_code": None,
            "stdout_tail": None,
            "stderr_tail": None,
            "effects_known": None,
            "completed_effects": [],
            "result_artifact_ids": [],
        }

    @staticmethod
    def _wake_toss_body(device_id: str, generation: int, now: int) -> dict:
        marker = f"wake:{device_id}:{generation}".encode("utf-8")
        return {
            "schema_version": 1,
            "protocol_major": 1,
            "protocol_minor": 0,
            "generation": generation,
            "operation_id": f"wake-{device_id}-{generation:04d}",
            "given_at": now,
            "expires_at": now + 90,
            "started_at": 0,
            "finished_at": 0,
            "run_limit_s": 90,
            "payload_sha256": hashlib.sha256(marker).hexdigest(),
            "result_sha256": None,
            "artifact_refs": [],
            "target_device_id": device_id,
            "fetcher_start_mode": "IF_NEEDED",
            "wake_reason_code": "FETCHER_REQUIRED",
            "host_seen_at": 0,
            "fetcher_started_at": 0,
            "pulse_confirmed_at": 0,
            "result_code": None,
            "reason_code": None,
        }


def execution_report(
    disposition: ExecutionDisposition,
    *,
    exit_code: int | None = None,
    effects: tuple[str, ...] = (),
) -> ExecutionReport:
    started = None if disposition is ExecutionDisposition.START_FAILED else 1.0
    return ExecutionReport(
        disposition=disposition,
        exit_code=exit_code,
        stdout="simulated stdout",
        stderr="" if exit_code in {0, None} else "simulated stderr",
        started_monotonic_s=started,
        finished_monotonic_s=2.0,
        known_effects=effects,
    )
