from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Collection

from tb4.core.deadlines import MonotonicDeadline
from tb4.core.retry import (
    OperationAttemptBudget,
    ProbeDisposition,
    RetryPolicy,
    RetryStopReason,
    confirm_with_backoff,
)

from .backend import DriveBackend
from .errors import BackendOutcome


class DeleteOutcome(StrEnum):
    VERIFIED_DELETED = "VERIFIED_DELETED"
    ALREADY_GONE = "ALREADY_GONE"
    SCOPE_CONFLICT = "SCOPE_CONFLICT"
    STATE_CONFLICT = "STATE_CONFLICT"
    UNCONFIRMED = "UNCONFIRMED"
    FAILURE = "FAILURE"


@dataclass(frozen=True, slots=True)
class DeleteReport:
    outcome: DeleteOutcome
    object_id: str
    message: str | None = None
    mutation_attempts: int = 0
    confirmation_probes: int = 0

    @property
    def success(self) -> bool:
        return self.outcome in {
            DeleteOutcome.VERIFIED_DELETED,
            DeleteOutcome.ALREADY_GONE,
        }


@dataclass(slots=True)
class DeleteKeeper:
    """Verified maintenance-only deletion.

    This helper is deliberately not a state-transition primitive. Live control
    objects use rename-based state machines. Permanent deletion is reserved for
    callers that prove an object is inside an explicit maintenance scope such
    as BONEYARD or TOY_BOX.
    """

    backend: DriveBackend
    retry_policy: RetryPolicy
    monotonic_now: Callable[[], float]
    sleeper: Callable[[float], None]

    def delete_verified(
        self,
        *,
        object_id: str,
        allowed_parent_ids: Collection[str],
        deadline: MonotonicDeadline | None = None,
    ) -> DeleteReport:
        allowed = frozenset(allowed_parent_ids)
        if not allowed:
            return DeleteReport(
                DeleteOutcome.SCOPE_CONFLICT,
                object_id,
                "at least one allowed parent ID is required",
            )

        budget = OperationAttemptBudget(
            self.retry_policy,
            self.monotonic_now,
            deadline,
        )

        while True:
            metadata = self.backend.get_metadata(object_id)
            if metadata.outcome is BackendOutcome.NOT_FOUND:
                return DeleteReport(
                    DeleteOutcome.ALREADY_GONE,
                    object_id,
                    "object already absent",
                    mutation_attempts=budget.claimed,
                )
            if not metadata.ok or metadata.value is None:
                return DeleteReport(
                    DeleteOutcome.UNCONFIRMED
                    if metadata.outcome is BackendOutcome.AMBIGUOUS
                    else DeleteOutcome.FAILURE,
                    object_id,
                    metadata.message or metadata.outcome.value,
                    mutation_attempts=budget.claimed,
                )

            observed = metadata.value
            if observed.parent_ids not in {(parent_id,) for parent_id in allowed}:
                return DeleteReport(
                    DeleteOutcome.SCOPE_CONFLICT,
                    object_id,
                    f"object parent {observed.parent_ids!r} is outside deletion scope",
                    mutation_attempts=budget.claimed,
                )
            if observed.is_folder:
                return DeleteReport(
                    DeleteOutcome.SCOPE_CONFLICT,
                    object_id,
                    "retention deletion accepts files only",
                    mutation_attempts=budget.claimed,
                )

            attempt = budget.claim()
            if attempt is None:
                return DeleteReport(
                    DeleteOutcome.FAILURE,
                    object_id,
                    "delete attempt budget exhausted or deadline expired",
                    mutation_attempts=budget.claimed,
                )

            result = self.backend.delete(
                object_id,
                expected_version_token=observed.version_token,
            )

            if result.outcome is BackendOutcome.CONFLICT:
                return DeleteReport(
                    DeleteOutcome.STATE_CONFLICT,
                    object_id,
                    result.message or "delete version conflict",
                    mutation_attempts=attempt,
                )

            if result.outcome is BackendOutcome.TRANSIENT_ERROR:
                if attempt >= self.retry_policy.operation_attempts:
                    return DeleteReport(
                        DeleteOutcome.FAILURE,
                        object_id,
                        "transient delete failure exhausted operation attempts",
                        mutation_attempts=attempt,
                    )
                delay = self.retry_policy.confirmation_backoff_s[0]
                if deadline is not None and delay >= deadline.remaining(self.monotonic_now()):
                    return DeleteReport(
                        DeleteOutcome.FAILURE,
                        object_id,
                        "deadline expired before delete retry",
                        mutation_attempts=attempt,
                    )
                self.sleeper(delay)
                continue

            if result.outcome in {
                BackendOutcome.PERMISSION_DENIED,
                BackendOutcome.NOT_FOUND,
            }:
                if result.outcome is BackendOutcome.NOT_FOUND:
                    return DeleteReport(
                        DeleteOutcome.ALREADY_GONE,
                        object_id,
                        "object disappeared before delete",
                        mutation_attempts=attempt,
                    )
                return DeleteReport(
                    DeleteOutcome.FAILURE,
                    object_id,
                    result.message or result.outcome.value,
                    mutation_attempts=attempt,
                )

            if result.outcome not in {
                BackendOutcome.SUCCESS,
                BackendOutcome.AMBIGUOUS,
            }:
                return DeleteReport(
                    DeleteOutcome.FAILURE,
                    object_id,
                    f"unsupported delete outcome {result.outcome.value}",
                    mutation_attempts=attempt,
                )

            unexpected: list[str] = []

            def probe() -> ProbeDisposition:
                check = self.backend.get_metadata(object_id)
                if check.outcome is BackendOutcome.NOT_FOUND:
                    return ProbeDisposition.CONFIRMED
                if check.outcome is BackendOutcome.TRANSIENT_ERROR:
                    return ProbeDisposition.NOT_VISIBLE
                if check.ok and check.value is not None:
                    if check.value.parent_ids not in {
                        (parent_id,) for parent_id in allowed
                    }:
                        unexpected.append("object moved outside allowed parent during delete")
                        return ProbeDisposition.AMBIGUOUS
                    return ProbeDisposition.NOT_VISIBLE
                unexpected.append(check.message or check.outcome.value)
                return ProbeDisposition.AMBIGUOUS

            confirmation = confirm_with_backoff(
                probe,
                policy=self.retry_policy,
                monotonic_now=self.monotonic_now,
                sleeper=self.sleeper,
                deadline=deadline,
            )
            if confirmation.reason is RetryStopReason.CONFIRMED:
                return DeleteReport(
                    DeleteOutcome.VERIFIED_DELETED,
                    object_id,
                    "delete remotely confirmed by exact NOT_FOUND",
                    mutation_attempts=attempt,
                    confirmation_probes=confirmation.probe_count,
                )

            return DeleteReport(
                DeleteOutcome.UNCONFIRMED,
                object_id,
                unexpected[-1] if unexpected else "delete could not be remotely confirmed",
                mutation_attempts=attempt,
                confirmation_probes=confirmation.probe_count,
            )
