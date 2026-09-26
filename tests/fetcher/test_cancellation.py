from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from tb4.core.retry import RetryPolicy
from tb4.drive.body_keeper import BodyKeeper
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.drive.state_walker import StateWalker
from tb4.fetcher.cancellation import (
    CancellationOutcome,
    StopBallCancellation,
)
from tb4.fetcher.execution_models import (
    ExecutionDisposition,
    ExecutionRequest,
    ExecutionSource,
    Interpreter,
)
from tb4.fetcher.subprocess_runner import SubprocessRunner


ROOT = Path(__file__).resolve().parents[2]


@dataclass
class FakeClock:
    monotonic_value: float = 100.0
    epoch_value: int = 1_700_002_001

    def monotonic(self) -> float:
        return self.monotonic_value

    def epoch(self) -> int:
        value = self.epoch_value
        self.epoch_value += 1
        return value

    def sleep(self, seconds: float) -> None:
        self.monotonic_value += seconds

    def advance(self, seconds: float) -> None:
        self.monotonic_value += seconds
        self.epoch_value += int(seconds)


def load_requested() -> dict:
    return json.loads(
        (ROOT / "protocol" / "examples" / "stop-ball" / "requested.json").read_text(
            encoding="utf-8"
        )
    )


def setup_objects(
    backend: InMemoryDriveBackend,
    *,
    fetch_state: str = "CHEW",
    fetch_generation: int = 11,
) -> tuple[str, str]:
    fetch_body = {
        "schema_version": 1,
        "protocol_major": 1,
        "protocol_minor": 0,
        "generation": fetch_generation,
        "operation_id": "job-1700000400-e1f2a3b4",
        "given_at": 1700002000,
        "expires_at": 1700003000,
        "started_at": 1700002001,
        "finished_at": 0,
        "run_limit_s": 300,
        "payload_sha256": "a" * 64,
        "result_sha256": None,
        "artifact_refs": [],
        "payload_source": "INLINE",
        "payload_type": "SHELL",
        "inline_payload": "sleep 30",
        "payload_artifact_id": None,
        "runtime_hint": "sh",
        "result_code": None,
        "reason_code": None,
        "exit_code": None,
        "stdout_tail": None,
        "stderr_tail": None,
        "effects_known": None,
        "completed_effects": [],
        "result_artifact_ids": [],
    }
    fetch = backend.create_text(
        backend.root_id,
        f"FETCH_BALL_{fetch_state}",
        json.dumps(fetch_body, sort_keys=True, separators=(",", ":")),
    )
    assert fetch.ok and fetch.value is not None

    stop_body = load_requested()
    stop_body["fetch_ball_object_id"] = fetch.value.metadata.object_id
    stop_body["job_id"] = fetch_body["operation_id"]
    stop_body["generation"] = fetch_generation
    stop_body["expires_at"] = 1_700_003_000
    stop = backend.create_text(
        backend.root_id,
        "STOP_BALL_REQUESTED",
        json.dumps(stop_body, sort_keys=True, separators=(",", ":")),
    )
    assert stop.ok and stop.value is not None
    backend.reset_operation_counts()
    return fetch.value.metadata.object_id, stop.value.metadata.object_id


def monitor(
    backend: InMemoryDriveBackend,
    fetch_id: str,
    stop_id: str,
    clock: FakeClock,
    *,
    job_id: str = "job-1700000400-e1f2a3b4",
    generation: int = 11,
) -> StopBallCancellation:
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
    return StopBallCancellation(
        backend=backend,
        state_walker=walker,
        body_keeper=keeper,
        stop_ball_object_id=stop_id,
        fetch_ball_object_id=fetch_id,
        job_id=job_id,
        generation=generation,
        monotonic_now=clock.monotonic,
        epoch_now=clock.epoch,
        poll_interval_s=1.0,
    )


def test_matching_request_is_acknowledged_and_latched() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeClock()
    fetch_id, stop_id = setup_objects(backend)
    cancel = monitor(backend, fetch_id, stop_id, clock)

    assert cancel.should_cancel() is True
    assert cancel.cancellation_latched is True
    assert cancel.last_report is not None
    assert cancel.last_report.outcome is CancellationOutcome.SIGNALLED

    metadata = backend.get_metadata(stop_id)
    assert metadata.ok and metadata.value is not None
    assert metadata.value.name == "STOP_BALL_ACKNOWLEDGED"
    body = backend.read_text(stop_id)
    assert body.ok and body.value is not None
    acknowledged = json.loads(body.value.text)
    assert acknowledged["ack_code"] == "CANCEL_SIGNALLED"
    assert acknowledged["result_sha256"] is not None

    writes = backend.operation_counts.get("replace_text", 0)
    assert cancel.should_cancel() is True
    assert backend.operation_counts.get("replace_text", 0) == writes


def test_stale_generation_is_acknowledged_no_match_and_never_cancels() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeClock()
    fetch_id, stop_id = setup_objects(backend, fetch_generation=12)
    cancel = monitor(backend, fetch_id, stop_id, clock, generation=12)

    remote = backend.read_text(stop_id)
    assert remote.ok and remote.value is not None
    body = json.loads(remote.value.text)
    body["generation"] = 11
    rewrite = backend.replace_text(
        stop_id,
        json.dumps(body, sort_keys=True, separators=(",", ":")),
        expected_version_token=remote.value.metadata.version_token,
    )
    assert rewrite.ok

    report = cancel.check_once()

    assert report.outcome is CancellationOutcome.NO_MATCH
    assert report.should_cancel is False
    state = backend.get_metadata(stop_id)
    assert state.ok and state.value is not None
    assert state.value.name == "STOP_BALL_ACKNOWLEDGED"
    ack = backend.read_text(stop_id)
    assert ack.ok and ack.value is not None
    assert json.loads(ack.value.text)["ack_code"] == "NO_MATCH"


def test_already_terminal_job_is_acknowledged_without_cancel_signal() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeClock()
    fetch_id, stop_id = setup_objects(backend, fetch_state="DONE")
    cancel = monitor(backend, fetch_id, stop_id, clock)

    report = cancel.check_once()

    assert report.outcome is CancellationOutcome.NO_MATCH
    assert report.should_cancel is False
    assert report.ack_code == "ALREADY_TERMINAL"
    ack = backend.read_text(stop_id)
    assert ack.ok and ack.value is not None
    assert json.loads(ack.value.text)["ack_code"] == "ALREADY_TERMINAL"


def test_poll_gate_bounds_remote_reads() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeClock()
    fetch_id, stop_id = setup_objects(backend)
    cancel = monitor(backend, fetch_id, stop_id, clock)

    # Make request non-actionable so the first check does not latch.
    state = backend.rename(stop_id, "STOP_BALL_READY")
    assert state.ok
    backend.reset_operation_counts()

    assert cancel.should_cancel() is False
    reads_after_first = dict(backend.operation_counts)
    assert cancel.should_cancel() is False
    assert backend.operation_counts == reads_after_first

    clock.advance(1.1)
    assert cancel.should_cancel() is False
    assert backend.operation_counts["get_metadata"] == reads_after_first["get_metadata"] + 1


def test_expired_request_is_durable_no_match_ack() -> None:
    backend = InMemoryDriveBackend()
    clock = FakeClock(epoch_value=1_700_004_000)
    fetch_id, stop_id = setup_objects(backend)
    cancel = monitor(backend, fetch_id, stop_id, clock)

    report = cancel.check_once()

    assert report.should_cancel is False
    assert report.ack_code == "NO_MATCH"
    state = backend.get_metadata(stop_id)
    assert state.ok and state.value is not None
    assert state.value.name == "STOP_BALL_ACKNOWLEDGED"


@pytest.mark.skipif(os.name == "nt", reason="SIGTERM ignore behavior is POSIX-specific")
def test_runner_forces_kill_when_cancelled_process_ignores_sigterm() -> None:
    calls = 0

    def cancel_requested() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 8

    request = ExecutionRequest(
        source=ExecutionSource.INLINE,
        interpreter=Interpreter.PYTHON,
        run_limit_s=10,
        inline_command=(
            "import signal,time;"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
            "time.sleep(30)"
        ),
    )

    result = SubprocessRunner().run(
        request,
        cancel_requested=cancel_requested,
    )

    assert result.disposition is ExecutionDisposition.CANCELLED
    assert result.message == "process tree required forced termination"
