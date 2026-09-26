from __future__ import annotations

import os
import sys

import pytest

from tb4.fetcher.execution_models import (
    ExecutionDisposition,
    ExecutionRequest,
    ExecutionSource,
    Interpreter,
)
from tb4.fetcher.subprocess_runner import SubprocessRunner


def python_request(code: str, *, timeout: float = 5.0) -> ExecutionRequest:
    return ExecutionRequest(
        source=ExecutionSource.INLINE,
        interpreter=Interpreter.PYTHON,
        run_limit_s=timeout,
        inline_command=code,
    )


def test_successful_inline_command() -> None:
    result = SubprocessRunner().run(python_request("print('ball returned')"))
    assert result.disposition is ExecutionDisposition.EXITED
    assert result.exit_code == 0
    assert "ball returned" in result.stdout


def test_nonzero_exit_is_execution_evidence_not_tb4_classification() -> None:
    result = SubprocessRunner().run(
        python_request("import sys; print('bad', file=sys.stderr); sys.exit(7)")
    )
    assert result.disposition is ExecutionDisposition.EXITED
    assert result.exit_code == 7
    assert "bad" in result.stderr


def test_stdout_and_stderr_are_captured_separately() -> None:
    result = SubprocessRunner().run(
        python_request(
            "import sys; print('OUT'); print('ERR', file=sys.stderr)"
        )
    )
    assert "OUT" in result.stdout
    assert "ERR" in result.stderr


def test_unicode_output_round_trips() -> None:
    result = SubprocessRunner().run(python_request("print('šuo grįžo 🐕')"))
    assert result.disposition is ExecutionDisposition.EXITED
    assert "šuo grįžo" in result.stdout


def test_capture_keeps_only_bounded_tail() -> None:
    runner = SubprocessRunner(capture_limit_bytes=128)
    result = runner.run(
        python_request("print('A' * 10000); import sys; print('B' * 10000, file=sys.stderr)")
    )
    assert len(result.stdout.encode("utf-8")) <= 128
    assert len(result.stderr.encode("utf-8")) <= 128
    assert "A" in result.stdout
    assert "B" in result.stderr


def test_timeout_terminates_process() -> None:
    result = SubprocessRunner().run(
        python_request("import time; time.sleep(30)", timeout=0.15)
    )
    assert result.disposition in {
        ExecutionDisposition.TIMED_OUT,
        ExecutionDisposition.TERMINATION_FAILED,
    }
    assert result.exit_code is None


def test_cancel_request_terminates_process() -> None:
    calls = 0

    def cancel() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 2

    result = SubprocessRunner().run(
        python_request("import time; time.sleep(30)"),
        cancel_requested=cancel,
    )
    assert result.disposition in {
        ExecutionDisposition.CANCELLED,
        ExecutionDisposition.TERMINATION_FAILED,
    }
    assert calls >= 2


def test_inline_runner_rejects_exec_interpreter() -> None:
    request = ExecutionRequest(
        source=ExecutionSource.INLINE,
        interpreter=Interpreter.EXEC,
        run_limit_s=5,
        inline_command="not interpreted",
    )
    with pytest.raises(ValueError, match="not valid for inline"):
        SubprocessRunner().run(request)


def test_inline_runner_rejects_script_file_source() -> None:
    from pathlib import Path

    request = ExecutionRequest(
        source=ExecutionSource.SCRIPT_FILE,
        interpreter=Interpreter.PYTHON,
        run_limit_s=5,
        script_path=Path("/controlled/script.py"),
    )
    with pytest.raises(ValueError, match="only INLINE"):
        SubprocessRunner().run(request)
