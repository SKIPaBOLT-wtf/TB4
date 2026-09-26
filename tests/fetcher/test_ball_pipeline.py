from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tb4.core.retry import RetryPolicy
from tb4.drive.body_keeper import BodyKeeper
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.drive.state_walker import StateWalker
from tb4.fetcher.artifact_spool import BoundedResult
from tb4.fetcher.ball_pipeline import (
    BallPipeline,
    BallPipelineStatus,
    LocalExecution,
)
from tb4.fetcher.execution_models import ExecutionDisposition, ExecutionReport


ROOT = Path(__file__).resolve().parents[2]


@dataclass
class FakeTime:
    monotonic_value: float = 100.0
    epoch_value: int = 1_700_000_001

    def monotonic(self) -> float:
        return self.monotonic_value

    def sleep(self, seconds: float) -> None:
        self.monotonic_value += seconds

    def epoch(self) -> int:
        value = self.epoch_value
        self.epoch_value += 1
        return value


@dataclass
class FakeExecutor:
    report: ExecutionReport
    backend: InMemoryDriveBackend | None = None
    mutate_generation_to: int | None = None
    calls: int = 0

    def execute(self, body, *, now_epoch_s: int, cancel_requested=None) -> LocalExecution:
        self.calls += 1
        if self.backend is not None and self.mutate_generation_to is not None:
            object_id = self._find_ball_id()
            remote = self.backend.read_text(object_id)
            assert remote.ok and remote.value is not None
            changed = json.loads(remote.value.text)
            changed["generation"] = self.mutate_generation_to
            write = self.backend.replace_text(
                object_id,
                json.dumps(changed, sort_keys=True, separators=(",", ":")),
                expected_version_token=remote.value.metadata.version_token,
            )
            assert write.ok
        return LocalExecution(
            report=self.report,
            bounded=BoundedResult(
                stdout_tail=self.report.stdout,
                stderr_tail=self.report.stderr,
                result_artifact_id=None,
                result_artifact_sha256=None,
                result_artifact_size_bytes=None,
                full_output_preserved=True,
            ),
        )

    def _find_ball_id(self) -> str:
        assert self.backend is not None
        children = self.backend.list_children(self.backend.root_id)
        assert children.ok and children.value is not None
        for child in children.value:
            if child.name.startswith("FETCH_BALL_"):
                return child.object_id
        raise AssertionError("FETCH_BALL not found")


def toss_body() -> dict:
    return json.loads(
        (ROOT / "protocol" / "examples" / "fetch-ball" / "inline-toss.json").read_text(
            encoding="utf-8"
        )
    )


def make_pipeline(backend: InMemoryDriveBackend, executor: FakeExecutor, clock: FakeTime) -> BallPipeline:
    policy = RetryPolicy((0.01, 0.02, 0.04), 3)
    walker = StateWalker(
        backend=backend,
        retry_policy=policy,
        monotonic_now=clock.monotonic,
        sleeper=clock.sleep,
    )
    keeper = BodyKeeper(
        backend=backend,
        retry_policy=policy,
        monotonic_now=clock.monotonic,
        sleeper=clock.sleep,
    )
    return BallPipeline(
        backend=backend,
        state_walker=walker,
        body_keeper=keeper,
        executor=executor,
        epoch_now=clock.epoch,
    )


def add_ball(backend: InMemoryDriveBackend, body: dict) -> str:
    created = backend.create_text(
        backend.root_id,
        "FETCH_BALL_TOSS",
        json.dumps(body, sort_keys=True, separators=(",", ":")),
    )
    assert created.ok and created.value is not None
    backend.reset_operation_counts()
    return created.value.metadata.object_id


def exited(exit_code: int, *, effects: tuple[str, ...] = ()) -> ExecutionReport:
    return ExecutionReport(
        disposition=ExecutionDisposition.EXITED,
        exit_code=exit_code,
        stdout="out",
        stderr="" if exit_code == 0 else "err",
        started_monotonic_s=1.0,
        finished_monotonic_s=2.0,
        known_effects=effects,
    )


def test_done_flow_returns_verified_terminal_state_without_folder_scan() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    executor = FakeExecutor(exited(0))
    ball_id = add_ball(backend, toss_body())

    result = make_pipeline(backend, executor, clock).process_one(ball_id)

    assert result.status is BallPipelineStatus.RETURNED
    assert result.terminal_state == "DONE"
    metadata = backend.get_metadata(ball_id)
    assert metadata.ok and metadata.value is not None
    assert metadata.value.name == "FETCH_BALL_DONE"
    body = backend.read_text(ball_id)
    assert body.ok and body.value is not None
    terminal = json.loads(body.value.text)
    assert terminal["result_code"] == "DONE"
    assert terminal["started_at"] > 0
    assert terminal["finished_at"] > 0
    assert terminal["result_sha256"] is not None
    assert backend.operation_counts.get("list_children", 0) == 0


def test_partial_flow_preserves_known_effects() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    executor = FakeExecutor(exited(3, effects=("created directory",)))
    ball_id = add_ball(backend, toss_body())

    result = make_pipeline(backend, executor, clock).process_one(ball_id)

    assert result.terminal_state == "PARTIAL"
    body = backend.read_text(ball_id)
    assert body.ok and body.value is not None
    terminal = json.loads(body.value.text)
    assert terminal["effects_known"] == "PARTIAL"
    assert terminal["completed_effects"] == ["created directory"]


def test_failed_flow_has_no_fabricated_effects() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    executor = FakeExecutor(exited(9))
    ball_id = add_ball(backend, toss_body())

    result = make_pipeline(backend, executor, clock).process_one(ball_id)

    assert result.terminal_state == "FAILED"
    body = backend.read_text(ball_id)
    assert body.ok and body.value is not None
    terminal = json.loads(body.value.text)
    assert terminal["effects_known"] == "NONE"
    assert terminal["completed_effects"] == []


def test_expired_toss_is_not_claimed_or_executed() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime(epoch_value=1_700_000_500)
    executor = FakeExecutor(exited(0))
    ball_id = add_ball(backend, toss_body())

    result = make_pipeline(backend, executor, clock).process_one(ball_id)

    assert result.status is BallPipelineStatus.EXPIRED
    assert executor.calls == 0
    metadata = backend.get_metadata(ball_id)
    assert metadata.ok and metadata.value is not None
    assert metadata.value.name == "FETCH_BALL_TOSS"
    assert backend.operation_counts.get("rename", 0) == 0


def test_stale_generation_during_execution_cannot_publish_result() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    executor = FakeExecutor(
        exited(0),
        backend=backend,
        mutate_generation_to=8,
    )
    ball_id = add_ball(backend, toss_body())

    result = make_pipeline(backend, executor, clock).process_one(ball_id)

    assert result.status is BallPipelineStatus.STALE
    metadata = backend.get_metadata(ball_id)
    assert metadata.ok and metadata.value is not None
    assert metadata.value.name == "FETCH_BALL_CHEW"
    body = backend.read_text(ball_id)
    assert body.ok and body.value is not None
    current = json.loads(body.value.text)
    assert current["generation"] == 8
    assert current["result_code"] is None


def test_delayed_claim_visibility_is_confirmed_before_started_at_write() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeTime()
    executor = FakeExecutor(exited(0))
    ball_id = add_ball(backend, toss_body())
    backend.delay_next_mutation_visibility(reads=2)

    result = make_pipeline(backend, executor, clock).process_one(ball_id)

    assert result.terminal_state == "DONE"
    assert executor.calls == 1
    assert backend.operation_counts.get("list_children", 0) == 0
