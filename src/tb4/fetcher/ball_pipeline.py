from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Mapping, Any

from tb4.core.fencing import FenceToken
from tb4.core.models import Generation, ObjectStateRef, OperationId
from tb4.core.protocol_names import LogicalObject, Role
from tb4.core.schemas import SchemaStore, canonical_json_text, load_schema_store
from tb4.drive.backend import DriveBackend
from tb4.drive.body_keeper import BodyKeeper
from tb4.drive.errors import BackendOutcome, BackendResult
from tb4.drive.state_walker import StateWalker

from .artifact_runner import ArtifactDescriptor, ArtifactRunner
from .artifact_spool import ArtifactSpool, BoundedResult
from .execution_models import ExecutionRequest, ExecutionSource, Interpreter
from .result_judge import FetchBallTerminal, judge_result
from .subprocess_runner import SubprocessRunner


class BallPipelineError(RuntimeError):
    pass


class BallPipelineStatus(StrEnum):
    RETURNED = "RETURNED"
    EXPIRED = "EXPIRED"
    STALE = "STALE"


@dataclass(frozen=True, slots=True)
class BallPipelineResult:
    status: BallPipelineStatus
    terminal_state: str | None = None
    operation_id: str | None = None
    generation: int | None = None


@dataclass(frozen=True, slots=True)
class LocalExecution:
    report: Any
    bounded: BoundedResult


_INLINE_INTERPRETERS = {
    "pwsh": Interpreter.PWSH,
    "powershell": Interpreter.POWERSHELL,
    "bash": Interpreter.BASH,
    "sh": Interpreter.SH,
    "python3": Interpreter.PYTHON3,
    "python": Interpreter.PYTHON,
}


@dataclass(slots=True)
class LocalJobExecutor:
    backend: DriveBackend
    process_runner: SubprocessRunner
    artifact_runner: ArtifactRunner
    artifact_spool: ArtifactSpool
    result_retention_s: int = 7 * 24 * 60 * 60

    def execute(
        self,
        body: Mapping[str, Any],
        *,
        now_epoch_s: int,
        cancel_requested=None,
    ) -> LocalExecution:
        capture = self.artifact_spool.new_capture()
        observed_runner = SubprocessRunner(
            capture_limit_bytes=self.process_runner.capture_limit_bytes,
            monotonic_now=self.process_runner.monotonic_now,
            output_observer=capture.observe,
        )

        source = body["payload_source"]
        run_limit_s = float(body["run_limit_s"])
        operation_id = str(body["operation_id"])

        if source == "INLINE":
            payload = body["inline_payload"]
            hint = body["runtime_hint"]
            if not isinstance(payload, str) or not isinstance(hint, str):
                capture.cleanup()
                raise BallPipelineError("inline payload requires text and runtime_hint")
            interpreter = _INLINE_INTERPRETERS.get(hint)
            if interpreter is None:
                capture.cleanup()
                raise BallPipelineError(f"unsupported inline runtime_hint {hint!r}")
            expected_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if expected_hash != body["payload_sha256"]:
                capture.cleanup()
                raise BallPipelineError("inline payload sha256 mismatch")
            request = ExecutionRequest(
                source=ExecutionSource.INLINE,
                interpreter=interpreter,
                run_limit_s=run_limit_s,
                inline_command=payload,
            )
            report = observed_runner.run(
                request,
                cancel_requested=cancel_requested,
            )

        elif source == "ARTIFACT":
            artifact_id = body["payload_artifact_id"]
            if not isinstance(artifact_id, str):
                capture.cleanup()
                raise BallPipelineError("artifact payload requires payload_artifact_id")
            descriptor_read = self.backend.read_text(artifact_id)
            if not descriptor_read.ok or descriptor_read.value is None:
                capture.cleanup()
                raise BallPipelineError(
                    f"artifact descriptor read failed: {descriptor_read.outcome.value}"
                )
            try:
                raw = json.loads(descriptor_read.value.text)
                descriptor = ArtifactDescriptor(
                    descriptor_object_id=artifact_id,
                    artifact_id=raw["artifact_id"],
                    kind=raw["kind"],
                    content_object_id=raw["content_object_id"],
                    size_bytes=raw["size_bytes"],
                    sha256=raw["sha256"],
                    interpreter_hint=raw["interpreter_hint"],
                    safe_suffix=raw["safe_suffix"],
                    created_at=raw["created_at"],
                    expires_at=raw["expires_at"],
                    complete=raw["complete"],
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                capture.cleanup()
                raise BallPipelineError(f"invalid artifact descriptor: {exc}") from exc

            if descriptor.sha256 != body["payload_sha256"]:
                capture.cleanup()
                raise BallPipelineError("artifact payload sha256 mismatch")

            content_read = self.backend.read_text(descriptor.content_object_id)
            if not content_read.ok or content_read.value is None:
                capture.cleanup()
                raise BallPipelineError(
                    f"artifact content read failed: {content_read.outcome.value}"
                )

            observed_artifact_runner = ArtifactRunner(
                temp_root=self.artifact_runner.temp_root,
                process_runner=observed_runner,
                max_script_bytes=self.artifact_runner.max_script_bytes,
                preserve_failed_temp=self.artifact_runner.preserve_failed_temp,
            )
            report = observed_artifact_runner.run_script(
                descriptor,
                content_read.value.text.encode("utf-8"),
                run_limit_s=run_limit_s,
                now_epoch_s=now_epoch_s,
                cancel_requested=cancel_requested,
            )
        else:
            capture.cleanup()
            raise BallPipelineError(f"unsupported payload source {source!r}")

        bounded = self.artifact_spool.finalize(
            report,
            capture,
            job_id=operation_id,
            now_epoch_s=now_epoch_s,
            retention_s=self.result_retention_s,
        )
        return LocalExecution(report=report, bounded=bounded)


@dataclass(slots=True)
class BallPipeline:
    backend: DriveBackend
    state_walker: StateWalker
    body_keeper: BodyKeeper
    executor: LocalJobExecutor
    epoch_now: Callable[[], int]
    schema_store: SchemaStore | None = None

    def process_one(
        self,
        fetch_ball_object_id: str,
        *,
        cancel_requested=None,
    ) -> BallPipelineResult:
        body = self._read_body(fetch_ball_object_id)
        metadata = self.backend.get_metadata(fetch_ball_object_id)
        if not metadata.ok or metadata.value is None:
            raise BallPipelineError(
                f"FETCH_BALL metadata read failed: {metadata.outcome.value}"
            )
        if metadata.value.name != "FETCH_BALL_TOSS":
            raise BallPipelineError(
                f"FETCH_BALL is not TOSS: {metadata.value.name!r}"
            )

        now = self.epoch_now()
        if int(body["expires_at"]) <= now:
            return BallPipelineResult(
                BallPipelineStatus.EXPIRED,
                operation_id=str(body["operation_id"]),
                generation=int(body["generation"]),
            )

        operation_id = OperationId(str(body["operation_id"]))
        generation = Generation(int(body["generation"]))
        toss_fence = self._fence(
            fetch_ball_object_id,
            operation_id,
            generation,
            "TOSS",
        )

        claim = self.state_walker.walk(
            object_id=fetch_ball_object_id,
            logical_object=LogicalObject.FETCH_BALL,
            expected_state="TOSS",
            target_state="CHEW",
            actor=Role.FETCHER,
            expected_fence=toss_fence,
            fence_reader=self._fence_reader,
        )
        if not claim.success:
            if claim.outcome.value == "STALE_FENCE":
                return BallPipelineResult(
                    BallPipelineStatus.STALE,
                    operation_id=operation_id.value,
                    generation=generation.value,
                )
            raise BallPipelineError(f"FETCH_BALL claim failed: {claim.outcome.value}: {claim.message}")

        chew_fence = self._fence(
            fetch_ball_object_id,
            operation_id,
            generation,
            "CHEW",
        )
        chew_body = dict(body)
        chew_body["started_at"] = self.epoch_now()
        started = self.body_keeper.replace_verified(
            object_id=fetch_ball_object_id,
            logical_object=LogicalObject.FETCH_BALL,
            state="CHEW",
            actor=Role.FETCHER,
            schema_name="fetch-ball.schema.json",
            body=chew_body,
            expected_fence=chew_fence,
            fence_reader=self._fence_reader,
        )
        if not started.success:
            if started.outcome.value == "STALE_FENCE":
                return BallPipelineResult(
                    BallPipelineStatus.STALE,
                    operation_id=operation_id.value,
                    generation=generation.value,
                )
            raise BallPipelineError(
                f"started_at write failed: {started.outcome.value}: {started.message}"
            )

        execution = self.executor.execute(
            chew_body,
            now_epoch_s=self.epoch_now(),
            cancel_requested=cancel_requested,
        )
        judgement = judge_result(execution.report)

        returning = self.state_walker.walk(
            object_id=fetch_ball_object_id,
            logical_object=LogicalObject.FETCH_BALL,
            expected_state="CHEW",
            target_state="RETURNING",
            actor=Role.FETCHER,
            expected_fence=chew_fence,
            fence_reader=self._fence_reader,
        )
        if not returning.success:
            if returning.outcome.value == "STALE_FENCE":
                return BallPipelineResult(
                    BallPipelineStatus.STALE,
                    operation_id=operation_id.value,
                    generation=generation.value,
                )
            raise BallPipelineError(
                f"RETURNING transition failed: {returning.outcome.value}: {returning.message}"
            )

        returning_fence = self._fence(
            fetch_ball_object_id,
            operation_id,
            generation,
            "RETURNING",
        )
        result_body = self._terminal_body(
            chew_body,
            execution,
            judgement.terminal,
            judgement.reason_code,
            finished_at=self.epoch_now(),
        )

        result_write = self.body_keeper.replace_verified(
            object_id=fetch_ball_object_id,
            logical_object=LogicalObject.FETCH_BALL,
            state="RETURNING",
            actor=Role.FETCHER,
            schema_name="fetch-ball.schema.json",
            body=result_body,
            expected_fence=returning_fence,
            fence_reader=self._fence_reader,
        )
        if not result_write.success:
            if result_write.outcome.value == "STALE_FENCE":
                return BallPipelineResult(
                    BallPipelineStatus.STALE,
                    operation_id=operation_id.value,
                    generation=generation.value,
                )
            raise BallPipelineError(
                f"terminal body write failed: {result_write.outcome.value}: {result_write.message}"
            )

        terminal = judgement.terminal.value
        publish = self.state_walker.walk(
            object_id=fetch_ball_object_id,
            logical_object=LogicalObject.FETCH_BALL,
            expected_state="RETURNING",
            target_state=terminal,
            actor=Role.FETCHER,
            expected_fence=returning_fence,
            fence_reader=self._fence_reader,
        )
        if not publish.success:
            if publish.outcome.value == "STALE_FENCE":
                return BallPipelineResult(
                    BallPipelineStatus.STALE,
                    operation_id=operation_id.value,
                    generation=generation.value,
                )
            raise BallPipelineError(
                f"terminal publish failed: {publish.outcome.value}: {publish.message}"
            )

        return BallPipelineResult(
            BallPipelineStatus.RETURNED,
            terminal_state=terminal,
            operation_id=operation_id.value,
            generation=generation.value,
        )

    def _read_body(self, object_id: str) -> dict[str, Any]:
        result = self.backend.read_text(object_id)
        if not result.ok or result.value is None:
            raise BallPipelineError(f"FETCH_BALL body read failed: {result.outcome.value}")
        try:
            body = json.loads(result.value.text)
        except json.JSONDecodeError as exc:
            raise BallPipelineError(f"FETCH_BALL body is invalid JSON: {exc}") from exc
        if not isinstance(body, dict):
            raise BallPipelineError("FETCH_BALL body must be an object")
        store = self.schema_store if self.schema_store is not None else load_schema_store()
        try:
            store.validate("fetch-ball.schema.json", body)
        except Exception as exc:
            raise BallPipelineError(f"FETCH_BALL schema invalid: {exc}") from exc
        if body.get("operation_id") is None:
            raise BallPipelineError("TOSS requires operation_id")
        return body

    def _fence_reader(self, object_id: str) -> BackendResult[FenceToken]:
        metadata = self.backend.get_metadata(object_id)
        if not metadata.ok or metadata.value is None:
            return BackendResult.failure(metadata.outcome, message=metadata.message)
        body_result = self.backend.read_text(object_id)
        if not body_result.ok or body_result.value is None:
            return BackendResult.failure(body_result.outcome, message=body_result.message)
        try:
            body = json.loads(body_result.value.text)
            operation_id = OperationId(str(body["operation_id"]))
            generation = Generation(int(body["generation"]))
            prefix = "FETCH_BALL_"
            if not metadata.value.name.startswith(prefix):
                raise ValueError("object name is not FETCH_BALL state")
            state = metadata.value.name[len(prefix):]
            token = self._fence(object_id, operation_id, generation, state)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return BackendResult.failure(BackendOutcome.CONFLICT, message=str(exc))
        return BackendResult.success(token)

    @staticmethod
    def _fence(
        object_id: str,
        operation_id: OperationId,
        generation: Generation,
        state: str,
    ) -> FenceToken:
        return FenceToken(
            object_id=object_id,
            operation_id=operation_id,
            generation=generation,
            expected_state=ObjectStateRef(LogicalObject.FETCH_BALL, state),
        )

    @staticmethod
    def _terminal_body(
        chew_body: Mapping[str, Any],
        execution: LocalExecution,
        terminal: FetchBallTerminal,
        reason_code: str,
        *,
        finished_at: int,
    ) -> dict[str, Any]:
        report = execution.report
        bounded = execution.bounded
        body = dict(chew_body)
        body["finished_at"] = finished_at
        body["result_code"] = terminal.value
        body["reason_code"] = reason_code
        body["exit_code"] = report.exit_code
        body["stdout_tail"] = bounded.stdout_tail
        body["stderr_tail"] = bounded.stderr_tail
        body["completed_effects"] = list(report.known_effects)
        if terminal is FetchBallTerminal.DONE:
            body["effects_known"] = "KNOWN"
        elif terminal is FetchBallTerminal.PARTIAL:
            body["effects_known"] = "PARTIAL"
        elif terminal is FetchBallTerminal.CANCELLED:
            body["effects_known"] = "PARTIAL" if report.known_effects else "NONE"
        else:
            body["effects_known"] = "NONE"

        artifact_ids: list[str] = []
        artifact_refs = list(body.get("artifact_refs", []))
        if bounded.result_artifact_id is not None:
            artifact_ids.append(bounded.result_artifact_id)
            artifact_refs.append(
                {
                    "artifact_id": bounded.result_artifact_id,
                    "kind": "RESULT_TEXT",
                    "size_bytes": bounded.result_artifact_size_bytes,
                    "sha256": bounded.result_artifact_sha256,
                }
            )
        body["result_artifact_ids"] = artifact_ids
        body["artifact_refs"] = artifact_refs

        hash_body = dict(body)
        hash_body["result_sha256"] = None
        body["result_sha256"] = hashlib.sha256(
            canonical_json_text(hash_body).encode("utf-8")
        ).hexdigest()
        return body
