from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Any

from tb4.core.fencing import FenceToken
from tb4.core.models import Generation, ObjectStateRef, OperationId
from tb4.core.protocol_names import LogicalObject, Role
from tb4.core.schemas import canonical_json_text, load_schema_store
from tb4.drive.backend import DriveBackend
from tb4.drive.body_keeper import BodyKeeper
from tb4.drive.errors import BackendOutcome, BackendResult
from tb4.drive.state_walker import StateWalker


class CancellationOutcome(StrEnum):
    NOT_DUE = "NOT_DUE"
    NO_REQUEST = "NO_REQUEST"
    NO_MATCH = "NO_MATCH"
    SIGNALLED = "SIGNALLED"
    ALREADY_ACKNOWLEDGED = "ALREADY_ACKNOWLEDGED"
    FAILURE = "FAILURE"


@dataclass(frozen=True, slots=True)
class CancellationReport:
    outcome: CancellationOutcome
    should_cancel: bool
    ack_code: str | None = None
    message: str | None = None


@dataclass(slots=True)
class StopBallCancellation:
    """Bounded exact-ID STOP_BALL observer for one active FETCH_BALL generation.

    Instances are scoped to one active job. RUNNER may call should_cancel()
    frequently; remote Drive reads are gated by poll_interval_s.
    """

    backend: DriveBackend
    state_walker: StateWalker
    body_keeper: BodyKeeper
    stop_ball_object_id: str
    fetch_ball_object_id: str
    job_id: str
    generation: int
    monotonic_now: Callable[[], float]
    epoch_now: Callable[[], int]
    poll_interval_s: float = 1.0
    last_poll_monotonic_s: float | None = None
    cancellation_latched: bool = False
    last_report: CancellationReport | None = None

    def __post_init__(self) -> None:
        if self.poll_interval_s <= 0:
            raise ValueError("poll_interval_s must be positive")

    def should_cancel(self) -> bool:
        if self.cancellation_latched:
            return True

        now = self.monotonic_now()
        if (
            self.last_poll_monotonic_s is not None
            and now - self.last_poll_monotonic_s < self.poll_interval_s
        ):
            self.last_report = CancellationReport(
                CancellationOutcome.NOT_DUE,
                should_cancel=False,
            )
            return False
        self.last_poll_monotonic_s = now

        report = self.check_once()
        self.last_report = report
        if report.should_cancel:
            self.cancellation_latched = True
        return report.should_cancel

    def check_once(self) -> CancellationReport:
        metadata = self.backend.get_metadata(self.stop_ball_object_id)
        if not metadata.ok or metadata.value is None:
            return CancellationReport(
                CancellationOutcome.FAILURE,
                False,
                message=metadata.message or metadata.outcome.value,
            )

        if metadata.value.name == "STOP_BALL_READY":
            return CancellationReport(CancellationOutcome.NO_REQUEST, False)

        if metadata.value.name == "STOP_BALL_ACKNOWLEDGED":
            body = self._read_body()
            if self._matches_target(body) and body.get("ack_code") == "CANCEL_SIGNALLED":
                return CancellationReport(
                    CancellationOutcome.ALREADY_ACKNOWLEDGED,
                    True,
                    ack_code="CANCEL_SIGNALLED",
                )
            return CancellationReport(
                CancellationOutcome.NO_MATCH,
                False,
                ack_code=body.get("ack_code"),
            )

        if metadata.value.name != "STOP_BALL_REQUESTED":
            return CancellationReport(
                CancellationOutcome.NO_REQUEST,
                False,
                message=f"STOP_BALL state {metadata.value.name!r} is not actionable",
            )

        body = self._read_body()
        now_epoch = self.epoch_now()
        if int(body["expires_at"]) <= now_epoch:
            return self._acknowledge(
                body,
                ack_code="NO_MATCH",
                should_cancel=False,
                message="cancellation request expired",
            )

        if not self._matches_target(body):
            return self._acknowledge(
                body,
                ack_code="NO_MATCH",
                should_cancel=False,
                message="cancellation request does not match active job",
            )

        return self._acknowledge(
            body,
            ack_code="CANCEL_SIGNALLED",
            should_cancel=True,
            message="matching cancellation request acknowledged",
        )

    def _acknowledge(
        self,
        body: dict[str, Any],
        *,
        ack_code: str,
        should_cancel: bool,
        message: str,
    ) -> CancellationReport:
        operation_id = OperationId(str(body["operation_id"]))
        generation = Generation(int(body["generation"]))
        requested_fence = self._fence(operation_id, generation, "REQUESTED")

        claimed = self.state_walker.walk(
            object_id=self.stop_ball_object_id,
            logical_object=LogicalObject.STOP_BALL,
            expected_state="REQUESTED",
            target_state="RETURNING",
            actor=Role.FETCHER,
            expected_fence=requested_fence,
            fence_reader=self._fence_reader,
        )
        if not claimed.success:
            return CancellationReport(
                CancellationOutcome.FAILURE,
                False,
                message=f"STOP_BALL claim failed: {claimed.outcome.value}: {claimed.message}",
            )

        returning_fence = self._fence(operation_id, generation, "RETURNING")
        ack_body = dict(body)
        ack_body["ack_code"] = ack_code
        ack_body["acknowledged_at"] = self.epoch_now()
        ack_body["finished_at"] = ack_body["acknowledged_at"]

        hash_body = dict(ack_body)
        hash_body["result_sha256"] = None
        ack_body["result_sha256"] = hashlib.sha256(
            canonical_json_text(hash_body).encode("utf-8")
        ).hexdigest()

        written = self.body_keeper.replace_verified(
            object_id=self.stop_ball_object_id,
            logical_object=LogicalObject.STOP_BALL,
            state="RETURNING",
            actor=Role.FETCHER,
            schema_name="stop-ball.schema.json",
            body=ack_body,
            expected_fence=returning_fence,
            fence_reader=self._fence_reader,
        )
        if not written.success:
            return CancellationReport(
                CancellationOutcome.FAILURE,
                False,
                message=f"STOP_BALL acknowledgement write failed: {written.outcome.value}: {written.message}",
            )

        published = self.state_walker.walk(
            object_id=self.stop_ball_object_id,
            logical_object=LogicalObject.STOP_BALL,
            expected_state="RETURNING",
            target_state="ACKNOWLEDGED",
            actor=Role.FETCHER,
            expected_fence=returning_fence,
            fence_reader=self._fence_reader,
        )
        if not published.success:
            return CancellationReport(
                CancellationOutcome.FAILURE,
                False,
                message=f"STOP_BALL acknowledgement publish failed: {published.outcome.value}: {published.message}",
            )

        return CancellationReport(
            CancellationOutcome.SIGNALLED if should_cancel else CancellationOutcome.NO_MATCH,
            should_cancel,
            ack_code=ack_code,
            message=message,
        )

    def _read_body(self) -> dict[str, Any]:
        remote = self.backend.read_text(self.stop_ball_object_id)
        if not remote.ok or remote.value is None:
            raise RuntimeError(
                f"STOP_BALL body read failed: {remote.outcome.value}: {remote.message or ''}".rstrip()
            )
        try:
            body = json.loads(remote.value.text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"STOP_BALL body is invalid JSON: {exc}") from exc
        if not isinstance(body, dict):
            raise RuntimeError("STOP_BALL body is not an object")
        load_schema_store().validate("stop-ball.schema.json", body)
        return body

    def _matches_target(self, body: dict[str, Any]) -> bool:
        return (
            body.get("fetch_ball_object_id") == self.fetch_ball_object_id
            and body.get("job_id") == self.job_id
            and int(body.get("generation", -1)) == self.generation
        )

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
            prefix = "STOP_BALL_"
            if not metadata.value.name.startswith(prefix):
                raise ValueError("object name is not STOP_BALL state")
            state = metadata.value.name[len(prefix):]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return BackendResult.failure(BackendOutcome.CONFLICT, message=str(exc))
        return BackendResult.success(self._fence(op, generation, state))

    def _fence(
        self,
        operation_id: OperationId,
        generation: Generation,
        state: str,
    ) -> FenceToken:
        return FenceToken(
            object_id=self.stop_ball_object_id,
            operation_id=operation_id,
            generation=generation,
            expected_state=ObjectStateRef(LogicalObject.STOP_BALL, state),
        )
