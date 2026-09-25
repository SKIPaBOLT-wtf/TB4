from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from tb4.core.deadlines import MonotonicDeadline
from tb4.core.fencing import (
    FenceDisposition,
    FenceToken,
    compare_fence,
)
from tb4.core.protocol_names import LogicalObject, Role, state_filename
from tb4.core.retry import (
    OperationAttemptBudget,
    ProbeDisposition,
    RetryPolicy,
    RetryStopReason,
    confirm_with_backoff,
)
from tb4.core.state_machine import (
    StateMachineRegistry,
    TransitionDisposition,
    load_state_machines,
)

from .backend import DriveBackend, ObjectMetadata
from .errors import BackendOutcome, BackendResult


class StateWalkOutcome(StrEnum):
    NEW_SUCCESS = "NEW_SUCCESS"
    IDEMPOTENT_SUCCESS = "IDEMPOTENT_SUCCESS"
    STATE_CONFLICT = "STATE_CONFLICT"
    STALE_FENCE = "STALE_FENCE"
    UNCONFIRMED = "UNCONFIRMED"
    FAILURE = "FAILURE"


@dataclass(frozen=True, slots=True)
class StateWalkReport:
    outcome: StateWalkOutcome
    object_id: str
    expected_name: str
    target_name: str
    observed_name: str | None = None
    message: str | None = None
    mutation_attempts: int = 0
    confirmation_probes: int = 0

    @property
    def success(self) -> bool:
        return self.outcome in {
            StateWalkOutcome.NEW_SUCCESS,
            StateWalkOutcome.IDEMPOTENT_SUCCESS,
        }


FenceReader = Callable[[str], BackendResult[FenceToken]]


@dataclass(slots=True)
class StateWalker:
    backend: DriveBackend
    retry_policy: RetryPolicy
    monotonic_now: Callable[[], float]
    sleeper: Callable[[float], None]
    registry: StateMachineRegistry | None = None

    def walk(
        self,
        *,
        object_id: str,
        logical_object: LogicalObject,
        expected_state: str,
        target_state: str,
        actor: Role,
        expected_fence: FenceToken | None = None,
        fence_reader: FenceReader | None = None,
        deadline: MonotonicDeadline | None = None,
    ) -> StateWalkReport:
        registry = self.registry if self.registry is not None else load_state_machines()
        expected_state = expected_state.upper()
        target_state = target_state.upper()
        expected_name = state_filename(logical_object, expected_state)
        target_name = state_filename(logical_object, target_state)

        transition = registry.validate_transition(
            logical_object,
            expected_state,
            target_state,
            actor,
        )
        if transition.disposition is TransitionDisposition.ILLEGAL:
            return self._report(
                StateWalkOutcome.STATE_CONFLICT,
                object_id,
                expected_name,
                target_name,
                message=transition.reason,
            )

        budget = OperationAttemptBudget(
            self.retry_policy,
            self.monotonic_now,
            deadline,
        )

        while True:
            metadata_result = self.backend.get_metadata(object_id)
            if not metadata_result.ok:
                return self._backend_read_failure(
                    metadata_result,
                    object_id,
                    expected_name,
                    target_name,
                    budget.claimed,
                )

            metadata = metadata_result.value
            assert metadata is not None

            if metadata.name not in {expected_name, target_name}:
                return self._report(
                    StateWalkOutcome.STATE_CONFLICT,
                    object_id,
                    expected_name,
                    target_name,
                    observed_name=metadata.name,
                    message="remote object is neither expected nor target state",
                    mutation_attempts=budget.claimed,
                )

            fence_report = self._check_fence(
                object_id=object_id,
                logical_object=logical_object,
                expected_fence=expected_fence,
                fence_reader=fence_reader,
                expected_name=expected_name,
                target_name=target_name,
                observed_name=metadata.name,
                mutation_attempts=budget.claimed,
            )
            if fence_report is not None:
                return fence_report

            if metadata.name == target_name:
                return self._report(
                    StateWalkOutcome.IDEMPOTENT_SUCCESS,
                    object_id,
                    expected_name,
                    target_name,
                    observed_name=metadata.name,
                    message="target state already remotely visible",
                    mutation_attempts=budget.claimed,
                )

            attempt = budget.claim()
            if attempt is None:
                return self._report(
                    StateWalkOutcome.FAILURE,
                    object_id,
                    expected_name,
                    target_name,
                    observed_name=metadata.name,
                    message="mutation attempt budget exhausted or deadline expired",
                    mutation_attempts=budget.claimed,
                )

            rename_result = self.backend.rename(
                object_id,
                target_name,
                expected_version_token=metadata.version_token,
            )

            if rename_result.outcome is BackendOutcome.CONFLICT:
                return self._report(
                    StateWalkOutcome.STATE_CONFLICT,
                    object_id,
                    expected_name,
                    target_name,
                    observed_name=metadata.name,
                    message=rename_result.message or "rename precondition conflict",
                    mutation_attempts=attempt,
                )

            if rename_result.outcome is BackendOutcome.TRANSIENT_ERROR:
                if attempt >= self.retry_policy.operation_attempts:
                    return self._report(
                        StateWalkOutcome.FAILURE,
                        object_id,
                        expected_name,
                        target_name,
                        observed_name=metadata.name,
                        message="transient rename failure exhausted operation attempts",
                        mutation_attempts=attempt,
                    )
                if not self._sleep_before_operation_retry(deadline):
                    return self._report(
                        StateWalkOutcome.FAILURE,
                        object_id,
                        expected_name,
                        target_name,
                        observed_name=metadata.name,
                        message="deadline expired before rename retry",
                        mutation_attempts=attempt,
                    )
                continue

            if rename_result.outcome in {
                BackendOutcome.NOT_FOUND,
                BackendOutcome.PERMISSION_DENIED,
            }:
                return self._report(
                    StateWalkOutcome.FAILURE,
                    object_id,
                    expected_name,
                    target_name,
                    observed_name=metadata.name,
                    message=rename_result.message or rename_result.outcome.value,
                    mutation_attempts=attempt,
                )

            if rename_result.outcome not in {
                BackendOutcome.SUCCESS,
                BackendOutcome.AMBIGUOUS,
            }:
                return self._report(
                    StateWalkOutcome.FAILURE,
                    object_id,
                    expected_name,
                    target_name,
                    observed_name=metadata.name,
                    message=f"unsupported rename outcome {rename_result.outcome.value}",
                    mutation_attempts=attempt,
                )

            unexpected_name: list[str] = []
            read_failure: list[BackendOutcome] = []

            def probe() -> ProbeDisposition:
                observed = self.backend.get_metadata(object_id)
                if not observed.ok:
                    if observed.outcome is BackendOutcome.TRANSIENT_ERROR:
                        return ProbeDisposition.NOT_VISIBLE
                    read_failure.append(observed.outcome)
                    return ProbeDisposition.AMBIGUOUS

                value = observed.value
                assert value is not None
                if value.name == target_name:
                    return ProbeDisposition.CONFIRMED
                if value.name == expected_name:
                    return ProbeDisposition.NOT_VISIBLE
                unexpected_name.append(value.name)
                return ProbeDisposition.AMBIGUOUS

            confirmation = confirm_with_backoff(
                probe,
                policy=self.retry_policy,
                monotonic_now=self.monotonic_now,
                sleeper=self.sleeper,
                deadline=deadline,
            )

            if confirmation.reason is RetryStopReason.CONFIRMED:
                return self._report(
                    StateWalkOutcome.NEW_SUCCESS,
                    object_id,
                    expected_name,
                    target_name,
                    observed_name=target_name,
                    message="rename remotely confirmed",
                    mutation_attempts=attempt,
                    confirmation_probes=confirmation.probe_count,
                )

            if unexpected_name:
                return self._report(
                    StateWalkOutcome.STATE_CONFLICT,
                    object_id,
                    expected_name,
                    target_name,
                    observed_name=unexpected_name[-1],
                    message="reconciliation observed an unexpected state",
                    mutation_attempts=attempt,
                    confirmation_probes=confirmation.probe_count,
                )

            if read_failure:
                return self._report(
                    StateWalkOutcome.UNCONFIRMED,
                    object_id,
                    expected_name,
                    target_name,
                    message=f"confirmation read ended with {read_failure[-1].value}",
                    mutation_attempts=attempt,
                    confirmation_probes=confirmation.probe_count,
                )

            # SUCCESS whose target never becomes visible is still unconfirmed.
            # AMBIGUOUS is never automatically replayed: the first mutation may
            # have applied but not yet be visible.
            if rename_result.outcome is BackendOutcome.AMBIGUOUS:
                return self._report(
                    StateWalkOutcome.UNCONFIRMED,
                    object_id,
                    expected_name,
                    target_name,
                    observed_name=expected_name,
                    message="ambiguous rename could not be reconciled within budget",
                    mutation_attempts=attempt,
                    confirmation_probes=confirmation.probe_count,
                )

            return self._report(
                StateWalkOutcome.UNCONFIRMED,
                object_id,
                expected_name,
                target_name,
                observed_name=expected_name,
                message=f"rename success not remotely confirmed: {confirmation.reason.value}",
                mutation_attempts=attempt,
                confirmation_probes=confirmation.probe_count,
            )

    def _check_fence(
        self,
        *,
        object_id: str,
        logical_object: LogicalObject,
        expected_fence: FenceToken | None,
        fence_reader: FenceReader | None,
        expected_name: str,
        target_name: str,
        observed_name: str,
        mutation_attempts: int,
    ) -> StateWalkReport | None:
        if expected_fence is None:
            return None

        if fence_reader is None:
            return self._report(
                StateWalkOutcome.FAILURE,
                object_id,
                expected_name,
                target_name,
                observed_name=observed_name,
                message="expected fence supplied without fence reader",
                mutation_attempts=mutation_attempts,
            )

        if expected_fence.object_id != object_id:
            return self._report(
                StateWalkOutcome.STATE_CONFLICT,
                object_id,
                expected_name,
                target_name,
                observed_name=observed_name,
                message="fence object ID does not match requested object",
                mutation_attempts=mutation_attempts,
            )

        if expected_fence.expected_state.logical_object is not logical_object:
            return self._report(
                StateWalkOutcome.STATE_CONFLICT,
                object_id,
                expected_name,
                target_name,
                observed_name=observed_name,
                message="fence logical object does not match requested object",
                mutation_attempts=mutation_attempts,
            )

        observed = fence_reader(object_id)
        if not observed.ok:
            outcome = (
                StateWalkOutcome.UNCONFIRMED
                if observed.outcome is BackendOutcome.AMBIGUOUS
                else StateWalkOutcome.FAILURE
            )
            return self._report(
                outcome,
                object_id,
                expected_name,
                target_name,
                observed_name=observed_name,
                message=observed.message or f"fence read failed: {observed.outcome.value}",
                mutation_attempts=mutation_attempts,
            )

        current_fence = observed.value
        assert current_fence is not None
        decision = compare_fence(expected_fence, current_fence)

        if decision.disposition is FenceDisposition.STALE:
            return self._report(
                StateWalkOutcome.STALE_FENCE,
                object_id,
                expected_name,
                target_name,
                observed_name=observed_name,
                message=decision.reason,
                mutation_attempts=mutation_attempts,
            )
        if decision.disposition is FenceDisposition.MISMATCH:
            return self._report(
                StateWalkOutcome.STATE_CONFLICT,
                object_id,
                expected_name,
                target_name,
                observed_name=observed_name,
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
    def _backend_read_failure(
        result: BackendResult[ObjectMetadata],
        object_id: str,
        expected_name: str,
        target_name: str,
        mutation_attempts: int,
    ) -> StateWalkReport:
        outcome = (
            StateWalkOutcome.UNCONFIRMED
            if result.outcome is BackendOutcome.AMBIGUOUS
            else StateWalkOutcome.FAILURE
        )
        return StateWalker._report(
            outcome,
            object_id,
            expected_name,
            target_name,
            message=result.message or result.outcome.value,
            mutation_attempts=mutation_attempts,
        )

    @staticmethod
    def _report(
        outcome: StateWalkOutcome,
        object_id: str,
        expected_name: str,
        target_name: str,
        *,
        observed_name: str | None = None,
        message: str | None = None,
        mutation_attempts: int = 0,
        confirmation_probes: int = 0,
    ) -> StateWalkReport:
        return StateWalkReport(
            outcome=outcome,
            object_id=object_id,
            expected_name=expected_name,
            target_name=target_name,
            observed_name=observed_name,
            message=message,
            mutation_attempts=mutation_attempts,
            confirmation_probes=confirmation_probes,
        )
