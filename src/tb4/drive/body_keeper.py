from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Mapping

from tb4.core.deadlines import MonotonicDeadline
from tb4.core.fencing import FenceDisposition, FenceToken, compare_fence
from tb4.core.protocol_names import LogicalObject, Role, state_filename
from tb4.core.retry import (
    OperationAttemptBudget,
    ProbeDisposition,
    RetryPolicy,
    RetryStopReason,
    confirm_with_backoff,
)
from tb4.core.schemas import (
    SchemaStore,
    SchemaValidationError,
    canonical_json_text,
    load_schema_store,
)
from tb4.core.state_machine import StateMachineRegistry, load_state_machines

from .backend import DriveBackend
from .errors import BackendOutcome, BackendResult


MAX_CONTROL_BODY_BYTES = 65_536


class BodyWriteOutcome(StrEnum):
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    STATE_CONFLICT = "STATE_CONFLICT"
    STALE_FENCE = "STALE_FENCE"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    HASH_MISMATCH = "HASH_MISMATCH"
    UNCONFIRMED = "UNCONFIRMED"
    FAILURE = "FAILURE"


@dataclass(frozen=True, slots=True)
class BodyWriteReport:
    outcome: BodyWriteOutcome
    object_id: str
    body_sha256: str
    message: str | None = None
    mutation_attempts: int = 0
    confirmation_probes: int = 0

    @property
    def success(self) -> bool:
        return self.outcome is BodyWriteOutcome.VERIFIED_SUCCESS


FenceReader = Callable[[str], BackendResult[FenceToken]]


@dataclass(slots=True)
class BodyKeeper:
    backend: DriveBackend
    retry_policy: RetryPolicy
    monotonic_now: Callable[[], float]
    sleeper: Callable[[float], None]
    schema_store: SchemaStore | None = None
    registry: StateMachineRegistry | None = None
    max_body_bytes: int = MAX_CONTROL_BODY_BYTES

    def replace_verified(
        self,
        *,
        object_id: str,
        logical_object: LogicalObject,
        state: str,
        actor: Role,
        schema_name: str,
        body: Mapping[str, Any],
        expected_body_sha256: str | None = None,
        expected_fence: FenceToken | None = None,
        fence_reader: FenceReader | None = None,
        deadline: MonotonicDeadline | None = None,
    ) -> BodyWriteReport:
        state = state.upper()
        body_text = canonical_json_text(body)
        body_bytes = body_text.encode("utf-8")
        body_hash = hashlib.sha256(body_bytes).hexdigest()

        if len(body_bytes) > self.max_body_bytes:
            return self._report(
                BodyWriteOutcome.FAILURE,
                object_id,
                body_hash,
                message=f"control body exceeds {self.max_body_bytes} bytes",
            )

        if expected_body_sha256 is not None and expected_body_sha256 != body_hash:
            return self._report(
                BodyWriteOutcome.HASH_MISMATCH,
                object_id,
                body_hash,
                message="caller expected hash does not match canonical local body",
            )

        store = self.schema_store if self.schema_store is not None else load_schema_store()
        try:
            store.validate(schema_name, body)
        except SchemaValidationError as exc:
            return self._report(
                BodyWriteOutcome.SCHEMA_INVALID,
                object_id,
                body_hash,
                message=str(exc),
            )

        registry = self.registry if self.registry is not None else load_state_machines()
        if not registry.can_write_body(logical_object, state, actor):
            return self._report(
                BodyWriteOutcome.STATE_CONFLICT,
                object_id,
                body_hash,
                message=f"{actor.value} is not a canonical body writer in {logical_object.value}_{state}",
            )

        expected_name = state_filename(logical_object, state)

        if expected_fence is not None:
            if expected_fence.object_id != object_id:
                return self._report(
                    BodyWriteOutcome.STATE_CONFLICT,
                    object_id,
                    body_hash,
                    message="fence object ID does not match requested object",
                )
            if expected_fence.expected_state.logical_object is not logical_object:
                return self._report(
                    BodyWriteOutcome.STATE_CONFLICT,
                    object_id,
                    body_hash,
                    message="fence logical object does not match requested object",
                )
            if expected_fence.expected_state.state != state:
                return self._report(
                    BodyWriteOutcome.STATE_CONFLICT,
                    object_id,
                    body_hash,
                    message="fence state does not match requested body-write state",
                )
            if body.get("operation_id") != expected_fence.operation_id.value:
                return self._report(
                    BodyWriteOutcome.STATE_CONFLICT,
                    object_id,
                    body_hash,
                    message="body operation_id does not match fence",
                )
            if body.get("generation") != expected_fence.generation.value:
                return self._report(
                    BodyWriteOutcome.STATE_CONFLICT,
                    object_id,
                    body_hash,
                    message="body generation does not match fence",
                )

        budget = OperationAttemptBudget(
            self.retry_policy,
            self.monotonic_now,
            deadline,
        )

        while True:
            metadata_result = self.backend.get_metadata(object_id)
            if not metadata_result.ok:
                return self._backend_failure(
                    metadata_result.outcome,
                    object_id,
                    body_hash,
                    metadata_result.message,
                    budget.claimed,
                )
            metadata = metadata_result.value
            assert metadata is not None

            if metadata.name != expected_name:
                return self._report(
                    BodyWriteOutcome.STATE_CONFLICT,
                    object_id,
                    body_hash,
                    message=f"expected filename {expected_name!r}, observed {metadata.name!r}",
                    mutation_attempts=budget.claimed,
                )

            pre_fence = self._check_fence(
                object_id,
                expected_fence,
                fence_reader,
                body_hash,
                budget.claimed,
            )
            if pre_fence is not None:
                return pre_fence

            attempt = budget.claim()
            if attempt is None:
                return self._report(
                    BodyWriteOutcome.FAILURE,
                    object_id,
                    body_hash,
                    message="body mutation attempt budget exhausted or deadline expired",
                    mutation_attempts=budget.claimed,
                )

            write = self.backend.replace_text(
                object_id,
                body_text,
                expected_version_token=metadata.version_token,
            )

            if write.outcome is BackendOutcome.CONFLICT:
                return self._report(
                    BodyWriteOutcome.STATE_CONFLICT,
                    object_id,
                    body_hash,
                    message=write.message or "body replace precondition conflict",
                    mutation_attempts=attempt,
                )

            if write.outcome is BackendOutcome.TRANSIENT_ERROR:
                if attempt >= self.retry_policy.operation_attempts:
                    return self._report(
                        BodyWriteOutcome.FAILURE,
                        object_id,
                        body_hash,
                        message="transient body replace exhausted operation attempts",
                        mutation_attempts=attempt,
                    )
                if not self._sleep_before_operation_retry(deadline):
                    return self._report(
                        BodyWriteOutcome.FAILURE,
                        object_id,
                        body_hash,
                        message="deadline expired before body replace retry",
                        mutation_attempts=attempt,
                    )
                continue

            if write.outcome in {
                BackendOutcome.NOT_FOUND,
                BackendOutcome.PERMISSION_DENIED,
            }:
                return self._backend_failure(
                    write.outcome,
                    object_id,
                    body_hash,
                    write.message,
                    attempt,
                )

            if write.outcome not in {
                BackendOutcome.SUCCESS,
                BackendOutcome.AMBIGUOUS,
            }:
                return self._report(
                    BodyWriteOutcome.FAILURE,
                    object_id,
                    body_hash,
                    message=f"unsupported body replace outcome {write.outcome.value}",
                    mutation_attempts=attempt,
                )

            last_remote_hash: list[str] = []
            last_schema_error: list[str] = []
            read_failure: list[BackendOutcome] = []

            def probe() -> ProbeDisposition:
                remote = self.backend.read_text(object_id)
                if not remote.ok:
                    if remote.outcome is BackendOutcome.TRANSIENT_ERROR:
                        return ProbeDisposition.NOT_VISIBLE
                    read_failure.append(remote.outcome)
                    return ProbeDisposition.AMBIGUOUS

                value = remote.value
                assert value is not None
                try:
                    parsed = json.loads(value.text)
                    if not isinstance(parsed, dict):
                        raise SchemaValidationError("remote body is not a JSON object")
                    store.validate(schema_name, parsed)
                except (json.JSONDecodeError, SchemaValidationError) as exc:
                    last_schema_error[:] = [str(exc)]
                    return ProbeDisposition.NOT_VISIBLE

                remote_hash = hashlib.sha256(value.text.encode("utf-8")).hexdigest()
                if remote_hash != body_hash:
                    last_remote_hash[:] = [remote_hash]
                    return ProbeDisposition.NOT_VISIBLE

                return ProbeDisposition.CONFIRMED

            confirmation = confirm_with_backoff(
                probe,
                policy=self.retry_policy,
                monotonic_now=self.monotonic_now,
                sleeper=self.sleeper,
                deadline=deadline,
            )

            if confirmation.reason is RetryStopReason.CONFIRMED:
                post_fence = self._check_fence(
                    object_id,
                    expected_fence,
                    fence_reader,
                    body_hash,
                    attempt,
                )
                if post_fence is not None:
                    return post_fence

                return self._report(
                    BodyWriteOutcome.VERIFIED_SUCCESS,
                    object_id,
                    body_hash,
                    message="body remotely read back, schema-valid, and hash-confirmed",
                    mutation_attempts=attempt,
                    confirmation_probes=confirmation.probe_count,
                )

            if read_failure:
                return self._report(
                    BodyWriteOutcome.UNCONFIRMED,
                    object_id,
                    body_hash,
                    message=f"readback ended with {read_failure[-1].value}",
                    mutation_attempts=attempt,
                    confirmation_probes=confirmation.probe_count,
                )

            if write.outcome is BackendOutcome.AMBIGUOUS:
                return self._report(
                    BodyWriteOutcome.UNCONFIRMED,
                    object_id,
                    body_hash,
                    message="ambiguous body replace could not be reconciled within budget",
                    mutation_attempts=attempt,
                    confirmation_probes=confirmation.probe_count,
                )

            if last_schema_error:
                return self._report(
                    BodyWriteOutcome.SCHEMA_INVALID,
                    object_id,
                    body_hash,
                    message=f"remote readback remained schema-invalid: {last_schema_error[-1]}",
                    mutation_attempts=attempt,
                    confirmation_probes=confirmation.probe_count,
                )

            if last_remote_hash:
                return self._report(
                    BodyWriteOutcome.HASH_MISMATCH,
                    object_id,
                    body_hash,
                    message=f"remote hash remained {last_remote_hash[-1]}",
                    mutation_attempts=attempt,
                    confirmation_probes=confirmation.probe_count,
                )

            return self._report(
                BodyWriteOutcome.UNCONFIRMED,
                object_id,
                body_hash,
                message=f"body replace not confirmed: {confirmation.reason.value}",
                mutation_attempts=attempt,
                confirmation_probes=confirmation.probe_count,
            )

    def _check_fence(
        self,
        object_id: str,
        expected_fence: FenceToken | None,
        fence_reader: FenceReader | None,
        body_hash: str,
        mutation_attempts: int,
    ) -> BodyWriteReport | None:
        if expected_fence is None:
            return None
        if fence_reader is None:
            return self._report(
                BodyWriteOutcome.FAILURE,
                object_id,
                body_hash,
                message="expected fence supplied without fence reader",
                mutation_attempts=mutation_attempts,
            )

        observed = fence_reader(object_id)
        if not observed.ok:
            return self._backend_failure(
                observed.outcome,
                object_id,
                body_hash,
                observed.message or "fence read failed",
                mutation_attempts,
            )
        current = observed.value
        assert current is not None
        decision = compare_fence(expected_fence, current)
        if decision.disposition is FenceDisposition.STALE:
            return self._report(
                BodyWriteOutcome.STALE_FENCE,
                object_id,
                body_hash,
                message=decision.reason,
                mutation_attempts=mutation_attempts,
            )
        if decision.disposition is FenceDisposition.MISMATCH:
            return self._report(
                BodyWriteOutcome.STATE_CONFLICT,
                object_id,
                body_hash,
                message=decision.reason,
                mutation_attempts=mutation_attempts,
            )
        return None

    def _sleep_before_operation_retry(
        self,
        deadline: MonotonicDeadline | None,
    ) -> bool:
        delay = self.retry_policy.confirmation_backoff_s[0]
        if deadline is not None and delay >= deadline.remaining(self.monotonic_now()):
            return False
        self.sleeper(delay)
        return True

    @staticmethod
    def _backend_failure(
        outcome: BackendOutcome,
        object_id: str,
        body_hash: str,
        message: str | None,
        mutation_attempts: int,
    ) -> BodyWriteReport:
        mapped = (
            BodyWriteOutcome.UNCONFIRMED
            if outcome is BackendOutcome.AMBIGUOUS
            else BodyWriteOutcome.FAILURE
        )
        return BodyKeeper._report(
            mapped,
            object_id,
            body_hash,
            message=message or outcome.value,
            mutation_attempts=mutation_attempts,
        )

    @staticmethod
    def _report(
        outcome: BodyWriteOutcome,
        object_id: str,
        body_hash: str,
        *,
        message: str | None = None,
        mutation_attempts: int = 0,
        confirmation_probes: int = 0,
    ) -> BodyWriteReport:
        return BodyWriteReport(
            outcome=outcome,
            object_id=object_id,
            body_sha256=body_hash,
            message=message,
            mutation_attempts=mutation_attempts,
            confirmation_probes=confirmation_probes,
        )
