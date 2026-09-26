from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable

from .execution_models import ExecutionReport, ExecutionRequest


CancelCheck = Callable[[], bool]


@runtime_checkable
class Runner(Protocol):
    """Local execution boundary used by FETCHER.

    A Runner knows nothing about Google Drive, FETCH_BALL filenames, PARK_MAP,
    WATCHDOG, or any other TB4 control-plane state. It receives an already
    validated local execution request and returns execution evidence only.
    """

    def run(
        self,
        request: ExecutionRequest,
        *,
        cancel_requested: CancelCheck | None = None,
    ) -> ExecutionReport:
        ...


@runtime_checkable
class ProcessTreeController(Protocol):
    """Platform-specific process-tree termination boundary."""

    def terminate_tree(self, process_id: int) -> bool:
        ...


@dataclass(slots=True)
class FakeRunner:
    """Deterministic Runner test double.

    It proves the interface shape without embedding subprocess behavior in the
    contract step. Real inline/script execution is implemented in later steps.
    """

    report: ExecutionReport
    calls: list[ExecutionRequest] | None = None

    def __post_init__(self) -> None:
        if self.calls is None:
            self.calls = []

    def run(
        self,
        request: ExecutionRequest,
        *,
        cancel_requested: CancelCheck | None = None,
    ) -> ExecutionReport:
        assert self.calls is not None
        self.calls.append(request)
        if cancel_requested is not None:
            cancel_requested()
        return self.report
