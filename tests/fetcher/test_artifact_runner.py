from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

from tb4.fetcher.artifact_runner import (
    ArtifactDescriptor,
    ArtifactExecutionError,
    ArtifactRunner,
)
from tb4.fetcher.execution_models import ExecutionDisposition
from tb4.fetcher.subprocess_runner import SubprocessRunner


def descriptor(
    content: bytes,
    *,
    artifact_id: str = "desc-001",
    hint: str = "python",
    suffix: str = ".py",
    expires_at: int = 2000,
) -> ArtifactDescriptor:
    return ArtifactDescriptor(
        descriptor_object_id=artifact_id,
        artifact_id=artifact_id,
        kind="REQUEST_SCRIPT",
        content_object_id="content-001",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        interpreter_hint=hint,
        safe_suffix=suffix,
        created_at=1000,
        expires_at=expires_at,
        complete=True,
    )


def test_large_multiline_script_executes_from_local_file_and_cleans_up(tmp_path: Path) -> None:
    payload = (
        "values = []\n"
        "for i in range(3000):\n"
        "    values.append(str(i))\n"
        "print('lines=' + str(len(values)))\n"
    ).encode("utf-8")
    runner = ArtifactRunner(tmp_path, SubprocessRunner())

    result = runner.run_script(
        descriptor(payload),
        payload,
        run_limit_s=5,
        now_epoch_s=1500,
    )

    assert result.disposition is ExecutionDisposition.EXITED
    assert result.exit_code == 0
    assert "lines=3000" in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_descriptor_identity_must_match_exact_object_id() -> None:
    payload = b"print('x')\n"
    with pytest.raises(ArtifactExecutionError, match="exact descriptor object ID"):
        ArtifactDescriptor(
            descriptor_object_id="drive-real-id",
            artifact_id="claimed-other-id",
            kind="REQUEST_SCRIPT",
            content_object_id="content",
            size_bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            interpreter_hint="python",
            safe_suffix=".py",
            created_at=1,
            expires_at=2,
            complete=True,
        )


def test_hash_mismatch_refuses_before_materialization(tmp_path: Path) -> None:
    payload = b"print('safe')\n"
    desc = descriptor(payload)
    with pytest.raises(ArtifactExecutionError, match="hash"):
        ArtifactRunner(tmp_path, SubprocessRunner()).run_script(
            desc,
            b"print('tampered')\n",
            run_limit_s=5,
            now_epoch_s=1500,
        )
    assert list(tmp_path.iterdir()) == []


def test_interpreter_suffix_mismatch_is_rejected(tmp_path: Path) -> None:
    payload = b"print('safe')\n"
    with pytest.raises(ArtifactExecutionError, match="does not match interpreter"):
        ArtifactRunner(tmp_path, SubprocessRunner()).run_script(
            descriptor(payload, suffix=".sh"),
            payload,
            run_limit_s=5,
            now_epoch_s=1500,
        )


def test_expired_artifact_is_not_executed(tmp_path: Path) -> None:
    payload = b"print('late')\n"
    with pytest.raises(ArtifactExecutionError, match="expired"):
        ArtifactRunner(tmp_path, SubprocessRunner()).run_script(
            descriptor(payload, expires_at=1200),
            payload,
            run_limit_s=5,
            now_epoch_s=1500,
        )
    assert list(tmp_path.iterdir()) == []


def test_artifact_size_policy_is_checked_before_temp_file(tmp_path: Path) -> None:
    payload = b"x" * 20
    with pytest.raises(ArtifactExecutionError, match="size policy"):
        ArtifactRunner(
            tmp_path,
            SubprocessRunner(),
            max_script_bytes=10,
        ).run_script(
            descriptor(payload),
            payload,
            run_limit_s=5,
            now_epoch_s=1500,
        )
    assert list(tmp_path.iterdir()) == []


def test_timeout_cleans_temporary_script(tmp_path: Path) -> None:
    payload = b"import time\ntime.sleep(30)\n"
    result = ArtifactRunner(tmp_path, SubprocessRunner()).run_script(
        descriptor(payload),
        payload,
        run_limit_s=0.15,
        now_epoch_s=1500,
    )
    assert result.disposition in {
        ExecutionDisposition.TIMED_OUT,
        ExecutionDisposition.TERMINATION_FAILED,
    }
    assert list(tmp_path.iterdir()) == []


def test_cancel_cleans_temporary_script(tmp_path: Path) -> None:
    payload = b"import time\ntime.sleep(30)\n"
    calls = 0

    def cancel() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 2

    result = ArtifactRunner(tmp_path, SubprocessRunner()).run_script(
        descriptor(payload),
        payload,
        run_limit_s=5,
        now_epoch_s=1500,
        cancel_requested=cancel,
    )
    assert result.disposition in {
        ExecutionDisposition.CANCELLED,
        ExecutionDisposition.TERMINATION_FAILED,
    }
    assert list(tmp_path.iterdir()) == []


def test_remote_identifier_never_becomes_local_filename(tmp_path: Path) -> None:
    payload = b"print('safe')\n"
    hostile_id = "..:..:outside"
    result = ArtifactRunner(tmp_path, SubprocessRunner()).run_script(
        descriptor(payload, artifact_id=hostile_id),
        payload,
        run_limit_s=5,
        now_epoch_s=1500,
    )
    assert result.exit_code == 0
    assert not (tmp_path.parent / "outside").exists()
    assert list(tmp_path.iterdir()) == []
