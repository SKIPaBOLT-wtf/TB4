from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tb4.core.fencing import FenceToken
from tb4.core.models import Generation, ObjectStateRef, OperationId
from tb4.core.protocol_names import LogicalObject, Role
from tb4.core.retry import RetryPolicy
from tb4.core.schemas import canonical_json_text
from tb4.drive.body_keeper import BodyKeeper, BodyWriteOutcome
from tb4.drive.errors import BackendOutcome, BackendResult
from tb4.drive.memory_backend import InMemoryDriveBackend


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "protocol" / "examples" / "fetch-ball" / "inline-toss.json"


@dataclass
class FakeTime:
    now: float = 100.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _body(*, generation: int = 7, operation_id: str = "job-1700000000-a1b2c3d4") -> dict:
    body = json.loads(FIXTURE.read_text(encoding="utf-8"))
    body["generation"] = generation
    body["operation_id"] = operation_id
    return body


def _fence(
    object_id: str,
    *,
    generation: int = 7,
    operation_id: str = "job-1700000000-a1b2c3d4",
) -> FenceToken:
    return FenceToken(
        object_id=object_id,
        operation_id=OperationId(operation_id),
        generation=Generation(generation),
        expected_state=ObjectStateRef(LogicalObject.FETCH_BALL, "LOADING"),
    )


def _setup(old_text: str | None = None) -> tuple[InMemoryDriveBackend, str, FakeTime]:
    backend = InMemoryDriveBackend()
    if old_text is None:
        old_text = canonical_json_text(
            _body(generation=6, operation_id="job-1699999999-oldbeef")
        )
    created = backend.create_text(
        backend.root_id,
        "FETCH_BALL_LOADING",
        old_text,
    )
    assert created.ok and created.value is not None
    backend.reset_operation_counts()
    return backend, created.value.metadata.object_id, FakeTime()


def _keeper(
    backend: InMemoryDriveBackend,
    clock: FakeTime,
    *,
    policy: RetryPolicy | None = None,
    max_body_bytes: int = 65_536,
) -> BodyKeeper:
    return BodyKeeper(
        backend=backend,
        retry_policy=policy or RetryPolicy((0.25, 0.5, 1.0), 3),
        monotonic_now=clock.monotonic,
        sleeper=clock.sleep,
        max_body_bytes=max_body_bytes,
    )


def _stable_fence_reader(token: FenceToken):
    def reader(_: str) -> BackendResult[FenceToken]:
        return BackendResult.success(token)
    return reader


def test_successful_replace_is_schema_and_hash_verified() -> None:
    backend, object_id, clock = _setup()
    token = _fence(object_id)
    body = _body()

    report = _keeper(backend, clock).replace_verified(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.COACH,
        schema_name="fetch-ball.schema.json",
        body=body,
        expected_fence=token,
        fence_reader=_stable_fence_reader(token),
    )

    assert report.outcome is BodyWriteOutcome.VERIFIED_SUCCESS
    assert backend.operation_counts["replace_text"] == 1
    assert backend.operation_counts.get("list_children", 0) == 0

    remote = backend.read_text(object_id)
    assert remote.ok and remote.value is not None
    assert remote.value.text == canonical_json_text(body)


def test_delayed_visibility_retries_readback_not_write() -> None:
    backend, object_id, clock = _setup()
    backend.delay_next_mutation_visibility(reads=2)

    report = _keeper(backend, clock).replace_verified(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.COACH,
        schema_name="fetch-ball.schema.json",
        body=_body(),
    )

    assert report.outcome is BodyWriteOutcome.VERIFIED_SUCCESS
    assert report.confirmation_probes == 3
    assert backend.operation_counts["replace_text"] == 1


def test_ambiguous_write_that_applied_is_reconciled_without_second_write() -> None:
    backend, object_id, clock = _setup()
    backend.inject_outcome("replace_text", BackendOutcome.AMBIGUOUS)

    report = _keeper(backend, clock).replace_verified(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.COACH,
        schema_name="fetch-ball.schema.json",
        body=_body(),
    )

    assert report.outcome is BodyWriteOutcome.VERIFIED_SUCCESS
    assert backend.operation_counts["replace_text"] == 1


def test_persistent_valid_but_wrong_readback_hash_is_hash_mismatch() -> None:
    backend, object_id, clock = _setup()
    backend.delay_next_mutation_visibility(reads=100)

    report = _keeper(
        backend,
        clock,
        policy=RetryPolicy((0.1, 0.2), 2),
    ).replace_verified(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.COACH,
        schema_name="fetch-ball.schema.json",
        body=_body(),
    )

    assert report.outcome is BodyWriteOutcome.HASH_MISMATCH
    assert backend.operation_counts["replace_text"] == 1


def test_schema_invalid_readback_is_not_accepted() -> None:
    backend, object_id, clock = _setup(old_text="{}")
    backend.delay_next_mutation_visibility(reads=100)

    report = _keeper(
        backend,
        clock,
        policy=RetryPolicy((0.1, 0.2), 2),
    ).replace_verified(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.COACH,
        schema_name="fetch-ball.schema.json",
        body=_body(),
    )

    assert report.outcome is BodyWriteOutcome.SCHEMA_INVALID


def test_schema_invalid_local_body_is_rejected_before_write() -> None:
    backend, object_id, clock = _setup()
    body = _body()
    del body["generation"]

    report = _keeper(backend, clock).replace_verified(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.COACH,
        schema_name="fetch-ball.schema.json",
        body=body,
    )

    assert report.outcome is BodyWriteOutcome.SCHEMA_INVALID
    assert backend.operation_counts.get("replace_text", 0) == 0


def test_wrong_body_writer_is_rejected_before_write() -> None:
    backend, object_id, clock = _setup()

    report = _keeper(backend, clock).replace_verified(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.FETCHER,
        schema_name="fetch-ball.schema.json",
        body=_body(),
    )

    assert report.outcome is BodyWriteOutcome.STATE_CONFLICT
    assert backend.operation_counts.get("replace_text", 0) == 0


def test_stale_fence_before_write_prevents_mutation() -> None:
    backend, object_id, clock = _setup()
    expected = _fence(object_id, generation=7)
    current = _fence(object_id, generation=8)

    report = _keeper(backend, clock).replace_verified(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.COACH,
        schema_name="fetch-ball.schema.json",
        body=_body(),
        expected_fence=expected,
        fence_reader=_stable_fence_reader(current),
    )

    assert report.outcome is BodyWriteOutcome.STALE_FENCE
    assert backend.operation_counts.get("replace_text", 0) == 0


def test_stale_fence_after_verified_readback_blocks_success() -> None:
    backend, object_id, clock = _setup()
    expected = _fence(object_id, generation=7)
    calls = 0

    def fence_reader(_: str) -> BackendResult[FenceToken]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return BackendResult.success(expected)
        return BackendResult.success(_fence(object_id, generation=8))

    report = _keeper(backend, clock).replace_verified(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.COACH,
        schema_name="fetch-ball.schema.json",
        body=_body(),
        expected_fence=expected,
        fence_reader=fence_reader,
    )

    assert report.outcome is BodyWriteOutcome.STALE_FENCE
    assert backend.operation_counts["replace_text"] == 1


def test_body_identity_must_match_fence_before_write() -> None:
    backend, object_id, clock = _setup()
    expected = _fence(object_id, generation=7)

    report = _keeper(backend, clock).replace_verified(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.COACH,
        schema_name="fetch-ball.schema.json",
        body=_body(generation=8),
        expected_fence=expected,
        fence_reader=_stable_fence_reader(expected),
    )

    assert report.outcome is BodyWriteOutcome.STATE_CONFLICT
    assert backend.operation_counts.get("replace_text", 0) == 0


def test_transient_write_exhaustion_is_bounded() -> None:
    backend, object_id, clock = _setup()
    backend.inject_outcome("replace_text", BackendOutcome.TRANSIENT_ERROR, times=3)

    report = _keeper(backend, clock).replace_verified(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.COACH,
        schema_name="fetch-ball.schema.json",
        body=_body(),
    )

    assert report.outcome is BodyWriteOutcome.FAILURE
    assert report.mutation_attempts == 3
    assert backend.operation_counts["replace_text"] == 3


def test_caller_hash_mismatch_is_rejected_before_write() -> None:
    backend, object_id, clock = _setup()

    report = _keeper(backend, clock).replace_verified(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.COACH,
        schema_name="fetch-ball.schema.json",
        body=_body(),
        expected_body_sha256="0" * 64,
    )

    assert report.outcome is BodyWriteOutcome.HASH_MISMATCH
    assert backend.operation_counts.get("replace_text", 0) == 0


def test_control_body_hard_limit_is_enforced() -> None:
    backend, object_id, clock = _setup()

    report = _keeper(backend, clock, max_body_bytes=64).replace_verified(
        object_id=object_id,
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.COACH,
        schema_name="fetch-ball.schema.json",
        body=_body(),
    )

    assert report.outcome is BodyWriteOutcome.FAILURE
    assert "exceeds" in (report.message or "")
    assert backend.operation_counts.get("replace_text", 0) == 0
