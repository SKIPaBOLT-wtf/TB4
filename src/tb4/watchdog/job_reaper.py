from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Any

from tb4.core.deadlines import is_stale
from tb4.core.fencing import FenceToken
from tb4.core.models import Generation, ObjectStateRef, OperationId
from tb4.core.protocol_names import LogicalObject, Role
from tb4.core.schemas import canonical_json_text, load_schema_store
from tb4.drive.backend import DriveBackend
from tb4.drive.body_keeper import BodyKeeper
from tb4.drive.errors import BackendOutcome, BackendResult
from tb4.drive.state_walker import StateWalker


class JobReaperOutcome(StrEnum):
    NOT_CHEWING = "NOT_CHEWING"
    PULSE_FRESH = "PULSE_FRESH"
    GRACE_ACTIVE = "GRACE_ACTIVE"
    GONE = "GONE"
    STALE = "STALE"
    FAILURE = "FAILURE"


@dataclass(frozen=True, slots=True)
class JobReaperReport:
    outcome: JobReaperOutcome
    message: str | None = None
    operation_id: str | None = None
    generation: int | None = None


@dataclass(slots=True)
class JobReaper:
    """Conservatively terminalize abandoned CHEW work as FETCH_BALL_GONE.

    GONE means execution evidence was lost, not that no side effect happened.
    This helper never replays work.
    """

    backend: DriveBackend
    state_walker: StateWalker
    body_keeper: BodyKeeper
    fetch_ball_object_id: str
    dog_pulse_object_id: str
    target_device_id: str
    stale_after_s: int
    gone_grace_s: int
    clock_skew_tolerance_s: int
    epoch_now: Callable[[], int]

    def __post_init__(self) -> None:
        if self.stale_after_s <= 0:
            raise ValueError("stale_after_s must be positive")
        if self.gone_grace_s < 0:
            raise ValueError("gone_grace_s must be non-negative")
        if self.clock_skew_tolerance_s < 0:
            raise ValueError("clock_skew_tolerance_s must be non-negative")

    def check_once(self) -> JobReaperReport:
        metadata = self.backend.get_metadata(self.fetch_ball_object_id)
        if not metadata.ok or metadata.value is None:
            return JobReaperReport(
                JobReaperOutcome.FAILURE,
                metadata.message or metadata.outcome.value,
            )
        if metadata.value.name != "FETCH_BALL_CHEW":
            return JobReaperReport(JobReaperOutcome.NOT_CHEWING)

        body_read = self.backend.read_text(self.fetch_ball_object_id)
        if not body_read.ok or body_read.value is None:
            return JobReaperReport(
                JobReaperOutcome.FAILURE,
                body_read.message or body_read.outcome.value,
            )
        try:
            body = json.loads(body_read.value.text)
            load_schema_store().validate("fetch-ball.schema.json", body)
            operation_id = OperationId(str(body["operation_id"]))
            generation = Generation(int(body["generation"]))
            started_at = int(body["started_at"])
            if started_at <= 0:
                raise ValueError("CHEW requires positive started_at")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return JobReaperReport(JobReaperOutcome.FAILURE, f"invalid CHEW body: {exc}")

        pulse_read = self.backend.read_text(self.dog_pulse_object_id)
        if not pulse_read.ok or pulse_read.value is None:
            return JobReaperReport(
                JobReaperOutcome.FAILURE,
                pulse_read.message or pulse_read.outcome.value,
                operation_id.value,
                generation.value,
            )
        try:
            pulse = json.loads(pulse_read.value.text)
            load_schema_store().validate("dog-pulse.schema.json", pulse)
            if pulse["device_id"] != self.target_device_id:
                raise ValueError("DOG_PULSE belongs to another device")
            emitted_at = int(pulse["emitted_at"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return JobReaperReport(
                JobReaperOutcome.FAILURE,
                f"invalid DOG_PULSE: {exc}",
                operation_id.value,
                generation.value,
            )

        now = int(self.epoch_now())
        try:
            pulse_stale = is_stale(
                now,
                emitted_at,
                self.stale_after_s,
                clock_skew_tolerance_s=self.clock_skew_tolerance_s,
            )
            beyond_grace = is_stale(
                now,
                emitted_at,
                self.stale_after_s + self.gone_grace_s,
                clock_skew_tolerance_s=self.clock_skew_tolerance_s,
            )
        except (ValueError, RuntimeError) as exc:
            return JobReaperReport(
                JobReaperOutcome.FAILURE,
                f"pulse age cannot be trusted: {exc}",
                operation_id.value,
                generation.value,
            )

        if not pulse_stale:
            return JobReaperReport(
                JobReaperOutcome.PULSE_FRESH,
                operation_id=operation_id.value,
                generation=generation.value,
            )
        if not beyond_grace:
            return JobReaperReport(
                JobReaperOutcome.GRACE_ACTIVE,
                operation_id=operation_id.value,
                generation=generation.value,
            )

        chew_fence = self._fence(operation_id, generation, "CHEW")
        moved = self.state_walker.walk(
            object_id=self.fetch_ball_object_id,
            logical_object=LogicalObject.FETCH_BALL,
            expected_state="CHEW",
            target_state="GONE",
            actor=Role.WATCHDOG,
            expected_fence=chew_fence,
            fence_reader=self._fence_reader,
        )
        if not moved.success:
            if moved.outcome.value == "STALE_FENCE":
                return JobReaperReport(
                    JobReaperOutcome.STALE,
                    moved.message,
                    operation_id.value,
                    generation.value,
                )
            return JobReaperReport(
                JobReaperOutcome.FAILURE,
                f"GONE transition failed: {moved.outcome.value}: {moved.message or ''}",
                operation_id.value,
                generation.value,
            )

        terminal = dict(body)
        terminal.update(
            finished_at=now,
            result_code="GONE",
            reason_code="FETCHER_LOST",
            exit_code=None,
            stdout_tail=None,
            stderr_tail=None,
            effects_known="UNKNOWN",
            completed_effects=[],
            result_artifact_ids=[],
        )
        hash_body = dict(terminal)
        hash_body["result_sha256"] = None
        terminal["result_sha256"] = hashlib.sha256(
            canonical_json_text(hash_body).encode("utf-8")
        ).hexdigest()

        gone_fence = self._fence(operation_id, generation, "GONE")
        written = self.body_keeper.replace_verified(
            object_id=self.fetch_ball_object_id,
            logical_object=LogicalObject.FETCH_BALL,
            state="GONE",
            actor=Role.WATCHDOG,
            schema_name="fetch-ball.schema.json",
            body=terminal,
            expected_fence=gone_fence,
            fence_reader=self._fence_reader,
        )
        if not written.success:
            if written.outcome.value == "STALE_FENCE":
                return JobReaperReport(
                    JobReaperOutcome.STALE,
                    written.message,
                    operation_id.value,
                    generation.value,
                )
            return JobReaperReport(
                JobReaperOutcome.FAILURE,
                f"GONE body write failed: {written.outcome.value}: {written.message or ''}",
                operation_id.value,
                generation.value,
            )

        return JobReaperReport(
            JobReaperOutcome.GONE,
            operation_id=operation_id.value,
            generation=generation.value,
        )

    def _fence_reader(self, object_id: str) -> BackendResult[FenceToken]:
        metadata = self.backend.get_metadata(object_id)
        if not metadata.ok or metadata.value is None:
            return BackendResult.failure(metadata.outcome, message=metadata.message)
        body_read = self.backend.read_text(object_id)
        if not body_read.ok or body_read.value is None:
            return BackendResult.failure(body_read.outcome, message=body_read.message)
        try:
            body = json.loads(body_read.value.text)
            operation_id = OperationId(str(body["operation_id"]))
            generation = Generation(int(body["generation"]))
            prefix = "FETCH_BALL_"
            if not metadata.value.name.startswith(prefix):
                raise ValueError("object name is not FETCH_BALL state")
            state = metadata.value.name[len(prefix):]
            return BackendResult.success(self._fence(operation_id, generation, state))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return BackendResult.failure(BackendOutcome.CONFLICT, message=str(exc))

    def _fence(
        self,
        operation_id: OperationId,
        generation: Generation,
        state: str,
    ) -> FenceToken:
        return FenceToken(
            object_id=self.fetch_ball_object_id,
            operation_id=operation_id,
            generation=generation,
            expected_state=ObjectStateRef(LogicalObject.FETCH_BALL, state),
        )
