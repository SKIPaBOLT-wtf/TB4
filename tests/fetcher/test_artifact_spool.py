from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tb4.drive.errors import BackendOutcome
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.fetcher.artifact_spool import ArtifactSpool, ArtifactSpoolError
from tb4.fetcher.execution_models import ExecutionRequest, ExecutionSource, Interpreter
from tb4.fetcher.subprocess_runner import SubprocessRunner


def python_request(code: str) -> ExecutionRequest:
    return ExecutionRequest(
        source=ExecutionSource.INLINE,
        interpreter=Interpreter.PYTHON,
        run_limit_s=5,
        inline_command=code,
    )


def make_spool(tmp_path: Path, *, inline_limit: int = 256):
    backend = InMemoryDriveBackend()
    toy = backend.create_folder(backend.root_id, "TOY_BOX")
    assert toy.ok and toy.value is not None
    spool = ArtifactSpool(
        backend=backend,
        toy_box_folder_id=toy.value.metadata.object_id,
        temp_root=tmp_path,
        inline_result_max_bytes=inline_limit,
        result_tail_max_chars=64,
        max_result_artifact_bytes=1024 * 1024,
    )
    return backend, spool


def execute_with_capture(spool: ArtifactSpool, request: ExecutionRequest):
    capture = spool.new_capture()
    runner = SubprocessRunner(capture_limit_bytes=128, output_observer=capture.observe)
    report = runner.run(request)
    return report, capture


def test_small_output_stays_inline_and_capture_is_cleaned(tmp_path: Path) -> None:
    backend, spool = make_spool(tmp_path, inline_limit=1024)
    report, capture = execute_with_capture(spool, python_request("print('small ball')"))

    bounded = spool.finalize(
        report,
        capture,
        job_id="job-small",
        now_epoch_s=1000,
        retention_s=3600,
    )

    assert bounded.result_artifact_id is None
    assert bounded.full_output_preserved is True
    assert "small ball" in bounded.stdout_tail
    assert list(tmp_path.iterdir()) == []
    assert backend.operation_counts.get("create_text", 0) == 0  # Inline result creates no TOY_BOX artifact text.


def test_large_stdout_is_preserved_in_verified_result_artifact(tmp_path: Path) -> None:
    backend, spool = make_spool(tmp_path, inline_limit=128)
    report, capture = execute_with_capture(
        spool,
        python_request("print('A' * 5000)"),
    )

    bounded = spool.finalize(
        report,
        capture,
        job_id="job-large-stdout",
        now_epoch_s=1000,
        retention_s=3600,
    )

    assert bounded.result_artifact_id is not None
    assert bounded.result_artifact_sha256 is not None
    assert len(bounded.stdout_tail) <= 64
    assert list(tmp_path.iterdir()) == []

    descriptor_read = backend.read_text(bounded.result_artifact_id)
    assert descriptor_read.ok and descriptor_read.value is not None
    descriptor = json.loads(descriptor_read.value.text)
    content_read = backend.read_text(descriptor["content_object_id"])
    assert content_read.ok and content_read.value is not None
    content_bytes = content_read.value.text.encode("utf-8")
    assert hashlib.sha256(content_bytes).hexdigest() == descriptor["sha256"]
    payload = json.loads(content_read.value.text)
    assert len(payload["stdout"]) > 5000
    assert payload["stderr"] == ""


def test_large_stderr_and_mixed_output_share_one_result_artifact(tmp_path: Path) -> None:
    backend, spool = make_spool(tmp_path, inline_limit=128)
    code = (
        "import sys\n"
        "print('OUT-' + 'x' * 1000)\n"
        "print('ERR-' + 'y' * 1000, file=sys.stderr)\n"
    )
    report, capture = execute_with_capture(spool, python_request(code))

    bounded = spool.finalize(
        report,
        capture,
        job_id="job-mixed",
        now_epoch_s=1000,
        retention_s=3600,
    )

    assert bounded.result_artifact_id is not None
    descriptor_read = backend.read_text(bounded.result_artifact_id)
    assert descriptor_read.ok and descriptor_read.value is not None
    descriptor = json.loads(descriptor_read.value.text)
    content_read = backend.read_text(descriptor["content_object_id"])
    assert content_read.ok and content_read.value is not None
    payload = json.loads(content_read.value.text)
    assert payload["stdout"].startswith("OUT-")
    assert payload["stderr"].startswith("ERR-")
    assert len(bounded.stdout_tail) <= 64
    assert len(bounded.stderr_tail) <= 64


def test_artifact_backend_failure_is_explicit_and_claims_no_result(tmp_path: Path) -> None:
    backend, spool = make_spool(tmp_path, inline_limit=64)
    report, capture = execute_with_capture(
        spool,
        python_request("print('A' * 1000)"),
    )
    backend.inject_outcome("create_text", BackendOutcome.TRANSIENT_ERROR)

    with pytest.raises(ArtifactSpoolError, match="create result content failed"):
        spool.finalize(
            report,
            capture,
            job_id="job-backend-fail",
            now_epoch_s=1000,
            retention_s=3600,
        )

    assert list(tmp_path.iterdir()) == []


def test_output_over_local_spool_ceiling_is_explicit_failure(tmp_path: Path) -> None:
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
    report, capture = execute_with_capture(
        spool,
        python_request("print('Z' * 5000)"),
    )

    with pytest.raises(ArtifactSpoolError, match="max_total_bytes"):
        spool.finalize(
            report,
            capture,
            job_id="job-too-large",
            now_epoch_s=1000,
            retention_s=3600,
        )

    assert list(tmp_path.iterdir()) == []
