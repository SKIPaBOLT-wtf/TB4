from __future__ import annotations

import pytest

from tb4.fetcher.execution_models import ExecutionDisposition, ExecutionReport
from tb4.fetcher.result_judge import (
    FetchBallTerminal,
    ResultClassificationError,
    judge_result,
)


def report(
    disposition: ExecutionDisposition,
    *,
    exit_code: int | None,
    effects: tuple[str, ...] = (),
    stdout: str = "",
    stderr: str = "",
) -> ExecutionReport:
    started = None if disposition is ExecutionDisposition.START_FAILED else 1.0
    return ExecutionReport(
        disposition=disposition,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        started_monotonic_s=started,
        finished_monotonic_s=2.0,
        known_effects=effects,
    )


def test_zero_exit_is_done() -> None:
    judgement = judge_result(
        report(ExecutionDisposition.EXITED, exit_code=0)
    )
    assert judgement.terminal is FetchBallTerminal.DONE
    assert judgement.reason_code == "EXIT_ZERO"


def test_nonzero_without_known_effects_is_failed() -> None:
    judgement = judge_result(
        report(ExecutionDisposition.EXITED, exit_code=7)
    )
    assert judgement.terminal is FetchBallTerminal.FAILED


def test_nonzero_with_known_effects_is_partial() -> None:
    judgement = judge_result(
        report(
            ExecutionDisposition.EXITED,
            exit_code=7,
            effects=("created target directory", "wrote configuration"),
        )
    )
    assert judgement.terminal is FetchBallTerminal.PARTIAL
    assert judgement.known_effects == (
        "created target directory",
        "wrote configuration",
    )


def test_timeout_with_known_effect_is_partial() -> None:
    judgement = judge_result(
        report(
            ExecutionDisposition.TIMED_OUT,
            exit_code=None,
            effects=("package A installed",),
        )
    )
    assert judgement.terminal is FetchBallTerminal.PARTIAL
    assert judgement.reason_code == "TIMEOUT_WITH_KNOWN_EFFECTS"


def test_timeout_without_effects_is_failed() -> None:
    judgement = judge_result(
        report(ExecutionDisposition.TIMED_OUT, exit_code=None)
    )
    assert judgement.terminal is FetchBallTerminal.FAILED


def test_cancellation_remains_cancelled_even_with_known_effects() -> None:
    judgement = judge_result(
        report(
            ExecutionDisposition.CANCELLED,
            exit_code=None,
            effects=("first stage completed",),
        )
    )
    assert judgement.terminal is FetchBallTerminal.CANCELLED
    assert judgement.known_effects == ("first stage completed",)


def test_stdout_prose_is_never_guessed_as_side_effect() -> None:
    judgement = judge_result(
        report(
            ExecutionDisposition.EXITED,
            exit_code=1,
            stdout="Successfully changed everything before error",
            stderr="failure",
        )
    )
    assert judgement.terminal is FetchBallTerminal.FAILED
    assert judgement.known_effects == ()


def test_start_failure_is_failed() -> None:
    judgement = judge_result(
        report(ExecutionDisposition.START_FAILED, exit_code=None)
    )
    assert judgement.terminal is FetchBallTerminal.FAILED
    assert judgement.reason_code == "START_FAILED"


def test_start_failure_cannot_claim_known_effects() -> None:
    with pytest.raises(ResultClassificationError, match="START_FAILED"):
        judge_result(
            report(
                ExecutionDisposition.START_FAILED,
                exit_code=None,
                effects=("impossible effect",),
            )
        )


def test_termination_failed_is_not_misclassified_as_gone_or_failed() -> None:
    with pytest.raises(ResultClassificationError, match="not trustworthy"):
        judge_result(
            report(ExecutionDisposition.TERMINATION_FAILED, exit_code=None)
        )
