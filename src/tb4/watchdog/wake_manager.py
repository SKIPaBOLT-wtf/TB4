from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Any

from tb4.core.deadlines import MonotonicDeadline, is_stale
from tb4.core.fencing import FenceToken
from tb4.core.models import Generation, ObjectStateRef, OperationId
from tb4.core.protocol_names import LogicalObject, Role
from tb4.core.schemas import SchemaStore, canonical_json_text, load_schema_store
from tb4.drive.backend import DriveBackend
from tb4.drive.body_keeper import BodyKeeper
from tb4.drive.errors import BackendOutcome, BackendResult
from tb4.drive.state_walker import StateWalker
from tb4.watchdog.sniffer import (
    KnownDeviceTarget,
    LocalProbe,
    Reachability,
)
from tb4.watchdog.ssh_bootstrap import (
    BootstrapTarget,
    DoorScratchOutcome,
    DoorScratcher,
)
from tb4.watchdog.wol import (
    BoneThrowOutcome,
    BoneThrower,
    WakeTarget,
)


class WakeManagerError(RuntimeError):
    pass


class WakeManagerOutcome(StrEnum):
    DONE = "DONE"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    STALE = "STALE"


@dataclass(frozen=True, slots=True)
class WakeManagerReport:
    outcome: WakeManagerOutcome
    reason_code: str
    operation_id: str
    generation: int


@dataclass(frozen=True, slots=True)
class WakeTiming:
    wol_initial_wait_s: float
    probe_interval_s: float
    wake_deadline_s: float
    pulse_stale_s: int
    clock_skew_tolerance_s: int

    def __post_init__(self) -> None:
        if self.wol_initial_wait_s < 0:
            raise ValueError("wol_initial_wait_s must be non-negative")
        if self.probe_interval_s <= 0:
            raise ValueError("probe_interval_s must be positive")
        if self.wake_deadline_s <= 0:
            raise ValueError("wake_deadline_s must be positive")
        if self.pulse_stale_s <= 0:
            raise ValueError("pulse_stale_s must be positive")
        if self.clock_skew_tolerance_s < 0:
            raise ValueError("clock_skew_tolerance_s must be non-negative")


@dataclass(slots=True)
class WakeManager:
    backend: DriveBackend
    state_walker: StateWalker
    body_keeper: BodyKeeper
    bone_thrower: BoneThrower
    door_scratcher: DoorScratcher
    local_probe: LocalProbe
    wake_bone_object_id: str
    dog_pulse_object_id: str
    target_device_id: str
    probe_target: KnownDeviceTarget
    wake_target: WakeTarget
    bootstrap_target: BootstrapTarget
    timing: WakeTiming
    monotonic_now: Callable[[], float]
    epoch_now: Callable[[], int]
    sleeper: Callable[[float], None]
    schema_store: SchemaStore | None = None

    def process_toss(self) -> WakeManagerReport:
        body = self._read_wake_body()
        metadata = self.backend.get_metadata(self.wake_bone_object_id)
        if not metadata.ok or metadata.value is None:
            raise WakeManagerError(
                f"WAKE_BONE metadata read failed: {metadata.outcome.value}"
            )
        if metadata.value.name != "WAKE_BONE_TOSS":
            raise WakeManagerError(
                f"WAKE_BONE is not TOSS: {metadata.value.name!r}"
            )
        if body["target_device_id"] != self.target_device_id:
            raise WakeManagerError("WAKE_BONE target_device_id does not match manager target")

        operation_id = OperationId(str(body["operation_id"]))
        generation = Generation(int(body["generation"]))
        toss_fence = self._fence(operation_id, generation, "TOSS")

        now_epoch = int(self.epoch_now())
        if now_epoch >= int(body["expires_at"]):
            moved = self.state_walker.walk(
                object_id=self.wake_bone_object_id,
                logical_object=LogicalObject.WAKE_BONE,
                expected_state="TOSS",
                target_state="FAILED",
                actor=Role.WATCHDOG,
                expected_fence=toss_fence,
                fence_reader=self._fence_reader,
            )
            if not moved.success:
                if moved.outcome.value == "STALE_FENCE":
                    return self._report(WakeManagerOutcome.STALE, "STALE_REQUEST", operation_id, generation)
                raise WakeManagerError(f"expired request terminalization failed: {moved.outcome.value}")

            failed_fence = self._fence(operation_id, generation, "FAILED")
            failed_body = self._terminal_body(
                body,
                result_code="FAILED",
                reason_code="REQUEST_EXPIRED",
                finished_at=now_epoch,
            )
            written = self.body_keeper.replace_verified(
                object_id=self.wake_bone_object_id,
                logical_object=LogicalObject.WAKE_BONE,
                state="FAILED",
                actor=Role.WATCHDOG,
                schema_name="wake-bone.schema.json",
                body=failed_body,
                expected_fence=failed_fence,
                fence_reader=self._fence_reader,
            )
            if not written.success:
                raise WakeManagerError(
                    f"expired failure body write failed: {written.outcome.value}"
                )
            return self._report(WakeManagerOutcome.EXPIRED, "REQUEST_EXPIRED", operation_id, generation)

        claim = self.state_walker.walk(
            object_id=self.wake_bone_object_id,
            logical_object=LogicalObject.WAKE_BONE,
            expected_state="TOSS",
            target_state="CHEW",
            actor=Role.WATCHDOG,
            expected_fence=toss_fence,
            fence_reader=self._fence_reader,
        )
        if not claim.success:
            if claim.outcome.value == "STALE_FENCE":
                return self._report(WakeManagerOutcome.STALE, "STALE_REQUEST", operation_id, generation)
            raise WakeManagerError(f"WAKE_BONE claim failed: {claim.outcome.value}: {claim.message}")

        chew_fence = self._fence(operation_id, generation, "CHEW")
        working = dict(body)
        working["started_at"] = int(self.epoch_now())
        started = self.body_keeper.replace_verified(
            object_id=self.wake_bone_object_id,
            logical_object=LogicalObject.WAKE_BONE,
            state="CHEW",
            actor=Role.WATCHDOG,
            schema_name="wake-bone.schema.json",
            body=working,
            expected_fence=chew_fence,
            fence_reader=self._fence_reader,
        )
        if not started.success:
            if started.outcome.value == "STALE_FENCE":
                return self._report(WakeManagerOutcome.STALE, "STALE_REQUEST", operation_id, generation)
            raise WakeManagerError(f"WAKE_BONE started_at write failed: {started.outcome.value}")

        remaining_epoch = max(0, int(body["expires_at"]) - int(self.epoch_now()))
        run_limit = int(body["run_limit_s"])
        duration = min(float(self.timing.wake_deadline_s), float(run_limit), float(remaining_epoch))
        deadline = MonotonicDeadline(self.monotonic_now(), duration)

        if self._fresh_pulse():
            working["pulse_confirmed_at"] = int(self.epoch_now())
            return self._finish(working, chew_fence, operation_id, generation, "DONE", "FETCHER_READY")

        try:
            observation = self.local_probe.probe(self.probe_target)
        except Exception:
            observation = None

        if observation is not None and observation.reachability is Reachability.ONLINE:
            working["host_seen_at"] = int(self.epoch_now())
            ready = self._ensure_fetcher_or_wait(working, deadline)
            if ready:
                working["pulse_confirmed_at"] = int(self.epoch_now())
                return self._finish(working, chew_fence, operation_id, generation, "DONE", "FETCHER_READY")
        else:
            bone = self.bone_thrower.throw(self.wake_target)
            if bone.outcome is BoneThrowOutcome.NOT_CAPABLE:
                return self._finish(working, chew_fence, operation_id, generation, "FAILED", "TARGET_OFFLINE_NO_WOL")
            if bone.outcome is not BoneThrowOutcome.SENT:
                return self._finish(working, chew_fence, operation_id, generation, "FAILED", "WOL_ERROR")
            if not self._sleep_bounded(self.timing.wol_initial_wait_s, deadline):
                return self._finish(working, chew_fence, operation_id, generation, "FAILED", "WAKE_DEADLINE")

        bootstrap_attempted = working.get("fetcher_started_at", 0) > 0
        while not deadline.expired(self.monotonic_now()):
            try:
                observation = self.local_probe.probe(self.probe_target)
            except Exception:
                observation = None

            if observation is not None and observation.reachability is Reachability.ONLINE:
                if not working["host_seen_at"]:
                    working["host_seen_at"] = int(self.epoch_now())

                if self._fresh_pulse():
                    working["pulse_confirmed_at"] = int(self.epoch_now())
                    return self._finish(working, chew_fence, operation_id, generation, "DONE", "FETCHER_READY")

                mode = working.get("fetcher_start_mode")
                if mode != "DO_NOT_START" and not bootstrap_attempted:
                    bootstrap_attempted = True
                    door = self.door_scratcher.scratch(self.bootstrap_target)
                    if door.outcome in {
                        DoorScratchOutcome.STARTED,
                        DoorScratchOutcome.ALREADY_RUNNING,
                    }:
                        if door.outcome is DoorScratchOutcome.STARTED:
                            working["fetcher_started_at"] = int(self.epoch_now())
                    elif door.outcome is DoorScratchOutcome.NOT_CAPABLE:
                        if mode == "REQUIRE_START":
                            return self._finish(
                                working, chew_fence, operation_id, generation,
                                "FAILED", "FETCHER_BOOTSTRAP_UNSUPPORTED"
                            )
                    elif door.outcome is DoorScratchOutcome.AUTH_ERROR:
                        return self._finish(
                            working, chew_fence, operation_id, generation,
                            "FAILED", "SSH_AUTH"
                        )
                    elif door.outcome in {
                        DoorScratchOutcome.START_ERROR,
                        DoorScratchOutcome.LOCAL_ERROR,
                    }:
                        return self._finish(
                            working, chew_fence, operation_id, generation,
                            "FAILED", "FETCHER_START_ERROR"
                        )

            if not self._sleep_bounded(self.timing.probe_interval_s, deadline):
                break

        return self._finish(
            working,
            chew_fence,
            operation_id,
            generation,
            "FAILED",
            "WAKE_DEADLINE",
        )

    def _ensure_fetcher_or_wait(self, working: dict[str, Any], deadline: MonotonicDeadline) -> bool:
        if self._fresh_pulse():
            return True
        if working.get("fetcher_start_mode") == "DO_NOT_START":
            return False

        door = self.door_scratcher.scratch(self.bootstrap_target)
        if door.outcome is DoorScratchOutcome.STARTED:
            working["fetcher_started_at"] = int(self.epoch_now())
        # Even ALREADY_RUNNING is not readiness; DOG_PULSE decides.
        return self._fresh_pulse()

    def _fresh_pulse(self) -> bool:
        remote = self.backend.read_text(self.dog_pulse_object_id)
        if not remote.ok or remote.value is None:
            return False
        try:
            body = json.loads(remote.value.text)
            if not isinstance(body, dict):
                return False
            self._store().validate("dog-pulse.schema.json", body)
            if body["device_id"] != self.target_device_id:
                return False
            return not is_stale(
                int(self.epoch_now()),
                int(body["emitted_at"]),
                self.timing.pulse_stale_s,
                clock_skew_tolerance_s=self.timing.clock_skew_tolerance_s,
            )
        except Exception:
            return False

    def _finish(
        self,
        working: dict[str, Any],
        chew_fence: FenceToken,
        operation_id: OperationId,
        generation: Generation,
        result_code: str,
        reason_code: str,
    ) -> WakeManagerReport:
        finished = self._terminal_body(
            working,
            result_code=result_code,
            reason_code=reason_code,
            finished_at=int(self.epoch_now()),
        )
        written = self.body_keeper.replace_verified(
            object_id=self.wake_bone_object_id,
            logical_object=LogicalObject.WAKE_BONE,
            state="CHEW",
            actor=Role.WATCHDOG,
            schema_name="wake-bone.schema.json",
            body=finished,
            expected_fence=chew_fence,
            fence_reader=self._fence_reader,
        )
        if not written.success:
            if written.outcome.value == "STALE_FENCE":
                return self._report(WakeManagerOutcome.STALE, "STALE_REQUEST", operation_id, generation)
            raise WakeManagerError(f"WAKE_BONE result body write failed: {written.outcome.value}")

        terminal = "DONE" if result_code == "DONE" else "FAILED"
        moved = self.state_walker.walk(
            object_id=self.wake_bone_object_id,
            logical_object=LogicalObject.WAKE_BONE,
            expected_state="CHEW",
            target_state=terminal,
            actor=Role.WATCHDOG,
            expected_fence=chew_fence,
            fence_reader=self._fence_reader,
        )
        if not moved.success:
            if moved.outcome.value == "STALE_FENCE":
                return self._report(WakeManagerOutcome.STALE, "STALE_REQUEST", operation_id, generation)
            raise WakeManagerError(f"WAKE_BONE terminal publish failed: {moved.outcome.value}")

        outcome = WakeManagerOutcome.DONE if terminal == "DONE" else WakeManagerOutcome.FAILED
        return self._report(outcome, reason_code, operation_id, generation)

    def _terminal_body(
        self,
        source: dict[str, Any],
        *,
        result_code: str,
        reason_code: str,
        finished_at: int,
    ) -> dict[str, Any]:
        body = dict(source)
        body["finished_at"] = finished_at
        body["result_code"] = result_code
        body["reason_code"] = reason_code
        hash_body = dict(body)
        hash_body["result_sha256"] = None
        body["result_sha256"] = hashlib.sha256(
            canonical_json_text(hash_body).encode("utf-8")
        ).hexdigest()
        return body

    def _read_wake_body(self) -> dict[str, Any]:
        remote = self.backend.read_text(self.wake_bone_object_id)
        if not remote.ok or remote.value is None:
            raise WakeManagerError(f"WAKE_BONE body read failed: {remote.outcome.value}")
        try:
            body = json.loads(remote.value.text)
            if not isinstance(body, dict):
                raise ValueError("body is not an object")
            self._store().validate("wake-bone.schema.json", body)
            return body
        except Exception as exc:
            raise WakeManagerError(f"WAKE_BONE body invalid: {exc}") from exc

    def _fence_reader(self, object_id: str) -> BackendResult[FenceToken]:
        metadata = self.backend.get_metadata(object_id)
        if not metadata.ok or metadata.value is None:
            return BackendResult.failure(metadata.outcome, message=metadata.message)
        remote = self.backend.read_text(object_id)
        if not remote.ok or remote.value is None:
            return BackendResult.failure(remote.outcome, message=remote.message)
        try:
            body = json.loads(remote.value.text)
            op = OperationId(str(body["operation_id"]))
            generation = Generation(int(body["generation"]))
            prefix = "WAKE_BONE_"
            if not metadata.value.name.startswith(prefix):
                raise ValueError("object name is not WAKE_BONE state")
            state = metadata.value.name[len(prefix):]
            return BackendResult.success(self._fence(op, generation, state))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return BackendResult.failure(BackendOutcome.CONFLICT, message=str(exc))

    def _fence(self, operation_id: OperationId, generation: Generation, state: str) -> FenceToken:
        return FenceToken(
            object_id=self.wake_bone_object_id,
            operation_id=operation_id,
            generation=generation,
            expected_state=ObjectStateRef(LogicalObject.WAKE_BONE, state),
        )

    def _sleep_bounded(self, requested_s: float, deadline: MonotonicDeadline) -> bool:
        remaining = deadline.remaining(self.monotonic_now())
        if remaining <= 0:
            return False
        self.sleeper(min(float(requested_s), remaining))
        return not deadline.expired(self.monotonic_now())

    def _store(self) -> SchemaStore:
        return self.schema_store if self.schema_store is not None else load_schema_store()

    @staticmethod
    def _report(
        outcome: WakeManagerOutcome,
        reason: str,
        operation_id: OperationId,
        generation: Generation,
    ) -> WakeManagerReport:
        return WakeManagerReport(outcome, reason, operation_id.value, generation.value)
