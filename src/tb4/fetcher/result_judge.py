from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .execution_models import ExecutionDisposition, ExecutionReport


class FetchBallTerminal(StrEnum):
    DONE = "DONE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ResultClassificationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ResultJudgement:
    terminal: FetchBallTerminal
    reason_code: str
    known_effects: tuple[str, ...]


def judge_result(report: ExecutionReport) -> ResultJudgement:
    """Classify trustworthy local execution evidence.

    This function never returns GONE. GONE means trustworthy terminal execution
    evidence did not return and belongs to WATCHDOG/recovery logic.

    The classifier never infers side effects from stdout/stderr prose. Only the
    explicit known_effects field can establish meaningful partial effects.
    """

    effects = report.known_effects

    if report.disposition is ExecutionDisposition.TERMINATION_FAILED:
        raise ResultClassificationError(
            "TERMINATION_FAILED is not trustworthy terminal evidence; "
            "loss/recovery logic must resolve it"
        )

    if report.disposition is ExecutionDisposition.CANCELLED:
        return ResultJudgement(
            terminal=FetchBallTerminal.CANCELLED,
            reason_code="CANCELLED_BY_REQUEST",
            known_effects=effects,
        )

    if report.disposition is ExecutionDisposition.EXITED:
        assert report.exit_code is not None
        if report.exit_code == 0:
            return ResultJudgement(
                terminal=FetchBallTerminal.DONE,
                reason_code="EXIT_ZERO",
                known_effects=effects,
            )
        if effects:
            return ResultJudgement(
                terminal=FetchBallTerminal.PARTIAL,
                reason_code="NONZERO_EXIT_WITH_KNOWN_EFFECTS",
                known_effects=effects,
            )
        return ResultJudgement(
            terminal=FetchBallTerminal.FAILED,
            reason_code="NONZERO_EXIT_NO_KNOWN_EFFECTS",
            known_effects=(),
        )

    if report.disposition is ExecutionDisposition.TIMED_OUT:
        if effects:
            return ResultJudgement(
                terminal=FetchBallTerminal.PARTIAL,
                reason_code="TIMEOUT_WITH_KNOWN_EFFECTS",
                known_effects=effects,
            )
        return ResultJudgement(
            terminal=FetchBallTerminal.FAILED,
            reason_code="TIMEOUT_NO_KNOWN_EFFECTS",
            known_effects=(),
        )

    if report.disposition is ExecutionDisposition.START_FAILED:
        if effects:
            raise ResultClassificationError(
                "START_FAILED cannot carry trustworthy known effects"
            )
        return ResultJudgement(
            terminal=FetchBallTerminal.FAILED,
            reason_code="START_FAILED",
            known_effects=(),
        )

    raise ResultClassificationError(
        f"unsupported execution disposition {report.disposition.value!r}"
    )
