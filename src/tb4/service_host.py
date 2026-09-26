from __future__ import annotations

import signal
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from types import FrameType
from typing import Protocol


class ManagedRuntime(Protocol):
    """Role runtime hosted by a platform service wrapper."""

    def run(self, stop_event: threading.Event) -> int:
        """Run until stop_event is set or the runtime finishes."""


Cleanup = Callable[[], None]


@dataclass(slots=True)
class ServiceHost:
    """Small platform-neutral service lifecycle wrapper.

    The host owns process-level shutdown mechanics, not TB4 protocol logic.
    Runtime composition is injected by higher-level code so systemd/Windows
    packaging can stay stable while WATCHDOG/FETCHER internals evolve.
    """

    runtime: ManagedRuntime
    cleanup: list[Cleanup] = field(default_factory=list)
    stop_event: threading.Event = field(default_factory=threading.Event)
    _shutdown_started: bool = False

    def request_stop(
        self,
        signum: int | None = None,
        frame: FrameType | None = None,
    ) -> None:
        del signum, frame
        self.stop_event.set()

    def add_cleanup(self, callback: Cleanup) -> None:
        self.cleanup.append(callback)

    def install_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)

    def run(self, *, install_signal_handlers: bool = True) -> int:
        if install_signal_handlers:
            self.install_signal_handlers()
        try:
            return int(self.runtime.run(self.stop_event))
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Run registered cleanup exactly once, newest registration first."""
        if self._shutdown_started:
            return
        self._shutdown_started = True
        self.stop_event.set()
        errors: list[BaseException] = []
        for callback in reversed(self.cleanup):
            try:
                callback()
            except BaseException as exc:  # cleanup must continue
                errors.append(exc)
        if errors:
            raise RuntimeError(
                f"{len(errors)} service cleanup callback(s) failed"
            ) from errors[0]
