from __future__ import annotations

from pathlib import Path

import pytest

from tb4.fetcher.execution_models import (
    ExecutionDisposition,
    ExecutionReport,
    ExecutionRequest,
    ExecutionSource,
    Interpreter,
)
from tb4.fetcher.runner import FakeRunner, Runner


def exited_report() -> ExecutionReport:
    return ExecutionReport(
        disposition=ExecutionDisposition.EXITED,
        exit_code=0,
        stdout="ok",
        stderr="",
        started_monotonic_s=10.0,
        finished_monotonic_s=11.0,
        known_effects=("read configuration",),
    )


def test_fake_runner_satisfies_runner_contract() -> None:
    fake = FakeRunner(exited_report())
    assert isinstance(fake, Runner)

    request = ExecutionRequest(
        source=ExecutionSource.INLINE,
        interpreter=Interpreter.PWSH,
        run_limit_s=30,
        inline_command="Get-Date",
    )
    result = fake.run(request)

    assert result.exit_code == 0
    assert fake.calls == [request]


def test_inline_request_cannot_smuggle_script_path() -> None:
    with pytest.raises(ValueError, match="cannot carry script_path"):
        ExecutionRequest(
            source=ExecutionSource.INLINE,
            interpreter=Interpreter.BASH,
            run_limit_s=10,
            inline_command="true",
            script_path=Path("/tmp/not-allowed"),
        )


def test_script_request_requires_explicit_interpreter() -> None:
    with pytest.raises(ValueError, match="explicit interpreter"):
        ExecutionRequest(
            source=ExecutionSource.SCRIPT_FILE,
            interpreter=Interpreter.SHELL,
            run_limit_s=10,
            script_path=Path("/controlled/tmp/script.sh"),
        )


def test_script_request_does_not_accept_inline_command() -> None:
    with pytest.raises(ValueError, match="cannot carry inline_command"):
        ExecutionRequest(
            source=ExecutionSource.SCRIPT_FILE,
            interpreter=Interpreter.BASH,
            run_limit_s=10,
            script_path=Path("/controlled/tmp/script.sh"),
            inline_command="echo nope",
        )


@pytest.mark.parametrize(
    "disposition",
    [
        ExecutionDisposition.TIMED_OUT,
        ExecutionDisposition.CANCELLED,
        ExecutionDisposition.TERMINATION_FAILED,
    ],
)
def test_timeout_and_cancel_reports_do_not_invent_exit_code(
    disposition: ExecutionDisposition,
) -> None:
    report = ExecutionReport(
        disposition=disposition,
        exit_code=None,
        stdout="partial",
        stderr="",
        started_monotonic_s=2.0,
        finished_monotonic_s=5.0,
    )
    assert report.exit_code is None


def test_start_failed_does_not_claim_process_started() -> None:
    report = ExecutionReport(
        disposition=ExecutionDisposition.START_FAILED,
        exit_code=None,
        stdout="",
        stderr="could not start",
        started_monotonic_s=None,
        finished_monotonic_s=3.0,
    )
    assert report.started_monotonic_s is None


def test_non_exit_report_rejects_exit_code() -> None:
    with pytest.raises(ValueError, match="must not invent"):
        ExecutionReport(
            disposition=ExecutionDisposition.TIMED_OUT,
            exit_code=1,
            stdout="",
            stderr="",
            started_monotonic_s=1.0,
            finished_monotonic_s=2.0,
        )


def test_environment_rejects_duplicate_or_malformed_keys() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        ExecutionRequest(
            source=ExecutionSource.INLINE,
            interpreter=Interpreter.PYTHON3,
            run_limit_s=10,
            inline_command="print(1)",
            environment=(("A", "1"), ("A", "2")),
        )

    with pytest.raises(ValueError, match="environment key"):
        ExecutionRequest(
            source=ExecutionSource.INLINE,
            interpreter=Interpreter.PYTHON3,
            run_limit_s=10,
            inline_command="print(1)",
            environment=(("A=B", "1"),),
        )


def test_runner_contract_contains_no_drive_protocol_methods() -> None:
    assert not hasattr(Runner, "rename")
    assert not hasattr(Runner, "replace_text")
    assert not hasattr(Runner, "fetch_ball")
    assert not hasattr(Runner, "park_map")
