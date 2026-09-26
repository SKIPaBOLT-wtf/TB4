from __future__ import annotations

import json

import pytest

from tb4.core.clock import ClockSkewError, assert_clock_skew_sane
from tb4.core.fencing import FenceToken
from tb4.core.models import Generation, ObjectStateRef, OperationId
from tb4.core.protocol_names import LogicalObject, Role
from tb4.core.retry import RetryPolicy
from tb4.core.schemas import canonical_json_text
from tb4.drive.body_keeper import BodyKeeper
from tb4.drive.bootstrap import BootstrapError, bootstrap_tree
from tb4.drive.errors import BackendOutcome, BackendResult
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.drive.state_walker import StateWalkOutcome, StateWalker
from tb4.drive.tree_healer import RepairOutcome, TreeHealer
from tb4.fetcher.artifact_spool import ArtifactSpool, ArtifactSpoolError
from tb4.fetcher.ball_pipeline import BallPipelineError
from tb4.fetcher.execution_models import (
    ExecutionDisposition,
    ExecutionRequest,
    ExecutionSource,
    Interpreter,
)
from tb4.fetcher.subprocess_runner import SubprocessRunner
from tb4.testing.simulation import SimulationHarness
from tb4.watchdog.health import (
    FaultSignal,
    HealthOutcome,
    WatchdogHealth,
    classify_fault_code,
)


def _clean_fault_body(now: int = 1_700_100_000) -> dict[str, object]:
    return {
        "schema_version": 1,
        "protocol_major": 1,
        "reported_at": now,
        "source": "WATCHDOG",
        "scope": "NONE",
        "fault_code": None,
        "description": None,
        "invariant_key": None,
        "first_seen_at": 0,
        "last_seen_at": 0,
        "occurrence_count": 0,
    }


def _health_for(backend: InMemoryDriveBackend, clock) -> tuple[WatchdogHealth, str]:
    created = backend.create_text(
        backend.root_id,
        "DOG_SHIT_CLEAN",
        canonical_json_text(_clean_fault_body()),
    )
    assert created.ok and created.value is not None
    policy = RetryPolicy((0.01, 0.02, 0.04), 3)
    walker = StateWalker(backend, policy, clock.monotonic, clock.sleep)
    keeper = BodyKeeper(backend, policy, clock.monotonic, clock.sleep)
    return (
        WatchdogHealth(
            backend=backend,
            state_walker=walker,
            body_keeper=keeper,
            dog_shit_object_id=created.value.metadata.object_id,
            epoch_now=clock.epoch,
        ),
        created.value.metadata.object_id,
    )


def test_fetcher_loss_during_chew_becomes_gone_and_is_not_blindly_replayed() -> None:
    sim = SimulationHarness()
    target = sim.add_target("target-a")
    sim.toss_job(target)
    sim.mark_job_gone(target)

    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_GONE"

    with pytest.raises(BallPipelineError, match="not TOSS"):
        sim.run_job(
            target,
            report=__import__(
                "tb4.testing.simulation",
                fromlist=["execution_report"],
            ).execution_report(ExecutionDisposition.EXITED, exit_code=0),
        )

    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_GONE"


def test_stale_old_worker_cannot_return_into_newer_generation() -> None:
    sim = SimulationHarness()
    target = sim.add_target("target-a")

    first = sim.toss_job(target, generation=1)
    sim.mark_job_gone(target)
    sim.recycle_job(target)

    second = sim.toss_job(target, generation=2)
    claim = sim.walker.walk(
        object_id=target.fetch_ball_id,
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="TOSS",
        target_state="CHEW",
        actor=Role.FETCHER,
    )
    assert claim.success

    old_fence = FenceToken(
        object_id=target.fetch_ball_id,
        operation_id=OperationId(first["operation_id"]),
        generation=Generation(1),
        expected_state=ObjectStateRef(LogicalObject.FETCH_BALL, "CHEW"),
    )
    current_fence = FenceToken(
        object_id=target.fetch_ball_id,
        operation_id=OperationId(second["operation_id"]),
        generation=Generation(2),
        expected_state=ObjectStateRef(LogicalObject.FETCH_BALL, "CHEW"),
    )

    report = sim.walker.walk(
        object_id=target.fetch_ball_id,
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="CHEW",
        target_state="RETURNING",
        actor=Role.FETCHER,
        expected_fence=old_fence,
        fence_reader=lambda _: BackendResult.success(current_fence),
    )

    assert report.outcome is StateWalkOutcome.STALE_FENCE
    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_CHEW"


def test_ambiguous_drive_rename_is_reconciled_without_duplicate_mutation() -> None:
    sim = SimulationHarness()
    target = sim.add_target("target-a")
    sim.reset_operation_counts()
    sim.backend.inject_outcome("rename", BackendOutcome.AMBIGUOUS)

    sim.toss_job(target)

    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_TOSS"
    assert sim.backend.operation_counts["rename"] == 2
    assert sim.backend.operation_counts.get("list_children", 0) == 0


def test_duplicate_live_object_is_quarantined_and_canonical_identity_survives() -> None:
    backend = InMemoryDriveBackend()
    boot = bootstrap_tree(backend, root_id=backend.root_id)
    dog_house = boot.park_map.lookup("DOG_HOUSE")
    canonical = boot.park_map.lookup("DOG_HOUSE.DOG_PULSE")
    duplicate = backend.create_text(dog_house, "DOG_PULSE", "{}\n")
    assert duplicate.ok and duplicate.value is not None

    repaired = TreeHealer(backend).repair(
        root_id=backend.root_id,
        park_map=boot.park_map,
    )

    assert repaired.outcome is RepairOutcome.REPAIRED
    assert repaired.park_map.lookup("DOG_HOUSE.DOG_PULSE") == canonical
    assert duplicate.value.metadata.object_id in repaired.quarantined_ids
    moved = backend.get_metadata(duplicate.value.metadata.object_id)
    assert moved.ok and moved.value is not None
    assert moved.value.parent_ids == (repaired.park_map.lookup("DOG_POUND"),)


def test_corrupt_fetch_ball_body_fails_closed_without_claiming_job() -> None:
    sim = SimulationHarness()
    target = sim.add_target("target-a")
    sim.toss_job(target)

    meta = sim.backend.get_metadata(target.fetch_ball_id)
    assert meta.ok and meta.value is not None
    damaged = sim.backend.replace_text(
        target.fetch_ball_id,
        "{not-json",
        expected_version_token=meta.value.version_token,
    )
    assert damaged.ok

    with pytest.raises(BallPipelineError, match="invalid JSON"):
        sim.run_job(
            target,
            __import__(
                "tb4.testing.simulation",
                fromlist=["execution_report"],
            ).execution_report(ExecutionDisposition.EXITED, exit_code=0),
        )

    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_TOSS"


def test_drive_disconnect_before_claim_leaves_job_tossed_for_reconciliation() -> None:
    sim = SimulationHarness()
    target = sim.add_target("target-a")
    sim.toss_job(target)
    sim.backend.inject_outcome("read_text", BackendOutcome.TRANSIENT_ERROR)

    with pytest.raises(BallPipelineError, match="body read failed"):
        sim.run_job(
            target,
            __import__(
                "tb4.testing.simulation",
                fromlist=["execution_report"],
            ).execution_report(ExecutionDisposition.EXITED, exit_code=0),
        )

    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_TOSS"


def test_unsafe_clock_skew_promotes_to_watchdog_blocking_fault() -> None:
    sim = SimulationHarness()
    health, dog_shit_id = _health_for(sim.backend, sim.clock)

    with pytest.raises(ClockSkewError):
        assert_clock_skew_sane(1_000, 1_020, 10)

    signal = FaultSignal(
        code="CLOCK_UNSAFE_FOR_TTL",
        description="remote wall clock exceeds TTL safety tolerance",
        scope=classify_fault_code("CLOCK_UNSAFE_FOR_TTL"),
        invariant_key="clock.ttl_safe",
    )
    report = health.report(signal)

    assert report.outcome is HealthOutcome.BLOCKING_SET
    assert sim.state(dog_shit_id) == "DOG_SHIT_BLOCKING"


def test_interrupted_bootstrap_resumes_without_duplicate_control_tree() -> None:
    backend = InMemoryDriveBackend()
    backend.inject_outcome("create_folder", BackendOutcome.TRANSIENT_ERROR)

    with pytest.raises(BootstrapError):
        bootstrap_tree(backend, root_id=backend.root_id)

    recovered = bootstrap_tree(backend, root_id=backend.root_id)
    root_children = backend.list_children(backend.root_id)
    assert root_children.ok and root_children.value is not None
    names = [item.name for item in root_children.value]

    assert len(names) == len(set(names))
    assert recovered.park_map.lookup("DOG_HOUSE")
    assert recovered.park_map.lookup("BALL_PARK")


def test_oversized_output_with_artifact_failure_leaves_no_false_result_artifact(
    tmp_path,
) -> None:
    backend = InMemoryDriveBackend()
    toy = backend.create_folder(backend.root_id, "TOY_BOX")
    assert toy.ok and toy.value is not None
    spool = ArtifactSpool(
        backend=backend,
        toy_box_folder_id=toy.value.metadata.object_id,
        temp_root=tmp_path,
        inline_result_max_bytes=64,
        result_tail_max_chars=32,
        max_result_artifact_bytes=128,
    )
    capture = spool.new_capture()
    runner = SubprocessRunner(capture_limit_bytes=128, output_observer=capture.observe)
    request = ExecutionRequest(
        source=ExecutionSource.INLINE,
        interpreter=Interpreter.PYTHON,
        run_limit_s=5,
        inline_command="print('Z' * 5000)",
    )
    report = runner.run(request)

    with pytest.raises(ArtifactSpoolError, match="max_total_bytes"):
        spool.finalize(
            report,
            capture,
            job_id="job-too-large-failure-injection",
            now_epoch_s=1000,
            retention_s=3600,
        )

    assert list(tmp_path.iterdir()) == []
    assert backend.operation_counts.get("create_text", 0) == 0
