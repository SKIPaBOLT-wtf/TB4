from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import BinaryIO, Callable

from .execution_models import (
    ExecutionDisposition,
    ExecutionReport,
    ExecutionRequest,
    ExecutionSource,
    Interpreter,
)
from .runner import CancelCheck


DEFAULT_CAPTURE_LIMIT_BYTES = 65_536
POLL_INTERVAL_S = 0.05
TERMINATION_GRACE_S = 1.0

OutputObserver = Callable[[str, bytes], None]


class RunnerConfigurationError(ValueError):
    pass


@dataclass(slots=True)
class _TailBuffer:
    limit: int
    data: bytearray

    @classmethod
    def create(cls, limit: int) -> "_TailBuffer":
        if limit <= 0:
            raise ValueError("capture limit must be positive")
        return cls(limit=limit, data=bytearray())

    def append(self, chunk: bytes) -> None:
        if not chunk:
            return
        self.data.extend(chunk)
        overflow = len(self.data) - self.limit
        if overflow > 0:
            del self.data[:overflow]

    def text(self) -> str:
        return bytes(self.data).decode("utf-8", errors="replace")


def _read_stream(
    stream: BinaryIO,
    buffer: _TailBuffer,
    *,
    stream_name: str,
    observer: OutputObserver | None,
) -> None:
    try:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                return
            buffer.append(chunk)
            if observer is not None:
                observer(stream_name, chunk)
    finally:
        stream.close()


@dataclass(slots=True)
class SubprocessRunner:
    """Platform-neutral local subprocess runner for bounded inline commands.

    This module does no Drive access and no TB4 lifecycle transitions.
    """

    capture_limit_bytes: int = DEFAULT_CAPTURE_LIMIT_BYTES
    monotonic_now: Callable[[], float] = time.monotonic
    output_observer: OutputObserver | None = None

    def __post_init__(self) -> None:
        if self.capture_limit_bytes <= 0:
            raise ValueError("capture_limit_bytes must be positive")

    def run(
        self,
        request: ExecutionRequest,
        *,
        cancel_requested: CancelCheck | None = None,
    ) -> ExecutionReport:
        if request.source is not ExecutionSource.INLINE:
            raise RunnerConfigurationError(
                "SubprocessRunner.run accepts only INLINE requests; use run_script for SCRIPT_FILE"
            )
        return self._run_argv(
            request,
            self._inline_argv(request),
            cancel_requested=cancel_requested,
        )

    def run_script(
        self,
        request: ExecutionRequest,
        *,
        cancel_requested: CancelCheck | None = None,
    ) -> ExecutionReport:
        if request.source is not ExecutionSource.SCRIPT_FILE:
            raise RunnerConfigurationError("run_script requires SCRIPT_FILE request")
        return self._run_argv(
            request,
            self._script_argv(request),
            cancel_requested=cancel_requested,
        )

    def _run_argv(
        self,
        request: ExecutionRequest,
        argv: list[str],
        *,
        cancel_requested: CancelCheck | None = None,
    ) -> ExecutionReport:
        env = os.environ.copy()
        env.update(dict(request.environment))

        popen_kwargs: dict[str, object] = {
            "args": argv,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "cwd": request.working_directory,
            "env": env,
            "text": False,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        try:
            process = subprocess.Popen(**popen_kwargs)
        except (OSError, ValueError) as exc:
            now = self.monotonic_now()
            return ExecutionReport(
                disposition=ExecutionDisposition.START_FAILED,
                exit_code=None,
                stdout="",
                stderr="",
                started_monotonic_s=None,
                finished_monotonic_s=now,
                message=str(exc),
            )

        started = self.monotonic_now()
        stdout_tail = _TailBuffer.create(self.capture_limit_bytes)
        stderr_tail = _TailBuffer.create(self.capture_limit_bytes)
        assert process.stdout is not None
        assert process.stderr is not None
        readers = [
            threading.Thread(
                target=_read_stream,
                args=(process.stdout, stdout_tail),
                kwargs={"stream_name": "stdout", "observer": self.output_observer},
                daemon=True,
            ),
            threading.Thread(
                target=_read_stream,
                args=(process.stderr, stderr_tail),
                kwargs={"stream_name": "stderr", "observer": self.output_observer},
                daemon=True,
            ),
        ]
        for reader in readers:
            reader.start()

        disposition: ExecutionDisposition | None = None
        termination_message: str | None = None

        while process.poll() is None:
            now = self.monotonic_now()
            if cancel_requested is not None and cancel_requested():
                disposition, termination_message = self._terminate(
                    process,
                    requested=ExecutionDisposition.CANCELLED,
                )
                break
            if now - started >= request.run_limit_s:
                disposition, termination_message = self._terminate(
                    process,
                    requested=ExecutionDisposition.TIMED_OUT,
                )
                break
            time.sleep(POLL_INTERVAL_S)

        if process.poll() is None:
            # Defensive: _terminate should have produced a stopped process.
            disposition, termination_message = self._terminate(
                process,
                requested=ExecutionDisposition.TERMINATION_FAILED,
            )

        for reader in readers:
            reader.join(timeout=TERMINATION_GRACE_S)

        finished = self.monotonic_now()
        stdout = stdout_tail.text()
        stderr = stderr_tail.text()

        if disposition is None:
            return ExecutionReport(
                disposition=ExecutionDisposition.EXITED,
                exit_code=process.returncode,
                stdout=stdout,
                stderr=stderr,
                started_monotonic_s=started,
                finished_monotonic_s=finished,
            )

        return ExecutionReport(
            disposition=disposition,
            exit_code=None,
            stdout=stdout,
            stderr=stderr,
            started_monotonic_s=started,
            finished_monotonic_s=finished,
            message=termination_message,
        )

    def _script_argv(self, request: ExecutionRequest) -> list[str]:
        path = request.script_path
        assert path is not None
        path_arg = os.fspath(path)

        if request.interpreter is Interpreter.PWSH:
            return [self._require("pwsh"), "-NoLogo", "-NoProfile", "-NonInteractive", "-File", path_arg]
        if request.interpreter is Interpreter.POWERSHELL:
            executable = "powershell.exe" if os.name == "nt" else "powershell"
            return [self._require(executable), "-NoLogo", "-NoProfile", "-NonInteractive", "-File", path_arg]
        if request.interpreter is Interpreter.BASH:
            return [self._require("bash"), path_arg]
        if request.interpreter is Interpreter.SH:
            return [self._require("sh"), path_arg]
        if request.interpreter is Interpreter.PYTHON3:
            return [self._require("python3"), path_arg]
        if request.interpreter is Interpreter.PYTHON:
            return [self._require("python"), path_arg]
        if request.interpreter is Interpreter.EXEC:
            return [path_arg]
        raise RunnerConfigurationError(
            f"interpreter {request.interpreter.value!r} is not valid for script files"
        )

    def _inline_argv(self, request: ExecutionRequest) -> list[str]:
        command = request.inline_command
        assert command is not None

        if request.interpreter is Interpreter.PWSH:
            return [self._require("pwsh"), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command]
        if request.interpreter is Interpreter.POWERSHELL:
            executable = "powershell.exe" if os.name == "nt" else "powershell"
            return [self._require(executable), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command]
        if request.interpreter is Interpreter.BASH:
            return [self._require("bash"), "-c", command]
        if request.interpreter is Interpreter.SH:
            return [self._require("sh"), "-c", command]
        if request.interpreter is Interpreter.PYTHON3:
            return [self._require("python3"), "-c", command]
        if request.interpreter is Interpreter.PYTHON:
            return [self._require("python"), "-c", command]
        if request.interpreter is Interpreter.SHELL:
            if os.name == "nt":
                return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command]
            return [self._require("sh"), "-c", command]

        raise RunnerConfigurationError(
            f"interpreter {request.interpreter.value!r} is not valid for inline text"
        )

    @staticmethod
    def _require(executable: str) -> str:
        resolved = shutil.which(executable)
        if resolved is None:
            raise RunnerConfigurationError(f"interpreter {executable!r} is unavailable")
        return resolved

    def _terminate(
        self,
        process: subprocess.Popen[bytes],
        *,
        requested: ExecutionDisposition,
    ) -> tuple[ExecutionDisposition, str | None]:
        if process.poll() is not None:
            return requested, None

        try:
            if os.name == "nt":
                process.terminate()
            else:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=TERMINATION_GRACE_S)
            return requested, None
        except (OSError, subprocess.TimeoutExpired):
            try:
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=TERMINATION_GRACE_S)
                return requested, "process tree required forced termination"
            except (OSError, subprocess.TimeoutExpired) as exc:
                return ExecutionDisposition.TERMINATION_FAILED, str(exc)
