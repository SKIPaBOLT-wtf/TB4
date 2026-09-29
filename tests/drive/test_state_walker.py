from __future__ import annotations

from dataclasses import dataclass

from tb4.core.fencing import FenceToken
from tb4.core.models import Generation, ObjectStateRef, OperationId
from tb4.core.protocol_names import LogicalObject, Role
from tb4.core.retry import RetryPolicy
from tb4.drive.errors import BackendOutcome, BackendResult
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.drive.state_walker import StateWalkOutcome, StateWalker


@dataclass
class FakeTime:
    now: float = 100.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _walker(
    backend: InMemoryDriveBackend,
    clock: FakeTime,
    *,
    policy: RetryPolicy | None = None,
) -> StateWalker:
    return StateWalker(
        backend=backend,
        retry_policy=policy or RetryPolicy((0.25, 0.5, 1.0), 3),
        monotonic_now=clock.monotonic,
        sleeper=clock.sleep,
    )


def _ball(backend: InMemoryDriveBackend, name: str = "FETCH_BALL_READY") -> str:
    result = backend.create_text(backend.root_id, name, "{}")
    assert result.ok and result.value is not None
    backend.reset_operation_counts()
    return result.value.metadata.object_id


def _fence(object_id: str, generation: int, state: str = "READY") -> FenceToken:
    return FenceToken(
        object_id=object_id,
        operation_id=OperationId("job-1700000000-a1b2c3d4"),
        generation=Generation(generation),
        expected_state=ObjectStateRef(LogicalObject.FETCH_BALL, state),
    )


def test_immediate_success_uses_exact_object_only() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    object_id = _ball(backend)

    report = _walker(backend, clock).walk(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="READY",
        target_state="LOADING",
        actor=Role.COACH,
    )

    assert report.outcome is StateWalkOutcome.NEW_SUCCESS
    assert backend.operation_counts["rename"] == 1
    assert backend.operation_counts.get("list_children", 0) == 0
    assert backend.operation_counts.get("replace_text", 0) == 0

    metadata = backend.get_metadata(object_id)
    assert metadata.value is not None
    assert metadata.value.name == "FETCH_BALL_LOADING"


def test_delayed_visibility_confirms_without_second_rename() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    object_id = _ball(backend)
    backend.delay_next_mutation_visibility(reads=2)

    report = _walker(backend, clock).walk(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="READY",
        target_state="LOADING",
        actor=Role.COACH,
    )

    assert report.outcome is StateWalkOutcome.NEW_SUCCESS
    assert report.confirmation_probes == 3
    assert backend.operation_counts["rename"] == 1
    assert backend.operation_counts.get("list_children", 0) == 0


def test_ambiguous_rename_that_applied_is_reconciled_without_replay() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    object_id = _ball(backend)
    backend.inject_outcome("rename", BackendOutcome.AMBIGUOUS)

    report = _walker(backend, clock).walk(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="READY",
        target_state="LOADING",
        actor=Role.COACH,
    )

    assert report.outcome is StateWalkOutcome.NEW_SUCCESS
    assert backend.operation_counts["rename"] == 1


def test_ambiguous_rename_never_replays_when_visibility_budget_exhausts() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    object_id = _ball(backend)
    backend.delay_next_mutation_visibility(reads=100)
    backend.inject_outcome("rename", BackendOutcome.AMBIGUOUS)

    report = _walker(
        backend,
        clock,
        policy=RetryPolicy((0.1, 0.2), 3),
    ).walk(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="READY",
        target_state="LOADING",
        actor=Role.COACH,
    )

    assert report.outcome is StateWalkOutcome.UNCONFIRMED
    assert backend.operation_counts["rename"] == 1


def test_true_transient_rename_failure_may_use_next_bounded_attempt() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    object_id = _ball(backend)
    backend.inject_outcome("rename", BackendOutcome.TRANSIENT_ERROR)

    report = _walker(backend, clock).walk(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="READY",
        target_state="LOADING",
        actor=Role.COACH,
    )

    assert report.outcome is StateWalkOutcome.NEW_SUCCESS
    assert report.mutation_attempts == 2
    assert backend.operation_counts["rename"] == 2
    assert clock.now == 100.25


def test_wrong_expected_state_is_conflict_without_mutation() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    object_id = _ball(backend)

    report = _walker(backend, clock).walk(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="TOSS",
        target_state="CHEW",
        actor=Role.FETCHER,
    )

    assert report.outcome is StateWalkOutcome.STATE_CONFLICT
    assert backend.operation_counts.get("rename", 0) == 0


def test_illegal_transition_is_conflict_without_remote_mutation() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    object_id = _ball(backend)

    report = _walker(backend, clock).walk(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="READY",
        target_state="DONE",
        actor=Role.COACH,
    )

    assert report.outcome is StateWalkOutcome.STATE_CONFLICT
    assert backend.operation_counts.get("rename", 0) == 0


def test_stale_generation_fence_blocks_rename() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    object_id = _ball(backend)
    expected = _fence(object_id, 7)

    def fence_reader(_: str) -> BackendResult[FenceToken]:
        return BackendResult.success(_fence(object_id, 8))

    report = _walker(backend, clock).walk(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="READY",
        target_state="LOADING",
        actor=Role.COACH,
        expected_fence=expected,
        fence_reader=fence_reader,
    )

    assert report.outcome is StateWalkOutcome.STALE_FENCE
    assert backend.operation_counts.get("rename", 0) == 0


def test_retry_exhaustion_is_failure_with_exact_attempt_count() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    object_id = _ball(backend)
    backend.inject_outcome("rename", BackendOutcome.TRANSIENT_ERROR, times=3)

    report = _walker(backend, clock).walk(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="READY",
        target_state="LOADING",
        actor=Role.COACH,
    )

    assert report.outcome is StateWalkOutcome.FAILURE
    assert report.mutation_attempts == 3
    assert backend.operation_counts["rename"] == 3


def test_already_visible_target_is_idempotent_success_without_rename() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    object_id = _ball(backend, "FETCH_BALL_LOADING")

    report = _walker(backend, clock).walk(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="READY",
        target_state="LOADING",
        actor=Role.COACH,
    )

    assert report.outcome is StateWalkOutcome.IDEMPOTENT_SUCCESS
    assert backend.operation_counts.get("rename", 0) == 0
