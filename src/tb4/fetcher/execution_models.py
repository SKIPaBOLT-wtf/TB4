from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Sequence


class ExecutionSource(StrEnum):
    INLINE = "INLINE"
    SCRIPT_FILE = "SCRIPT_FILE"


class Interpreter(StrEnum):
    SHELL = "shell"
    POWERSHELL = "powershell"
    PWSH = "pwsh"
    BASH = "bash"
    SH = "sh"
    PYTHON3 = "python3"
    PYTHON = "python"
    EXEC = "exec"


class ExecutionDisposition(StrEnum):
    EXITED = "EXITED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    START_FAILED = "START_FAILED"
    TERMINATION_FAILED = "TERMINATION_FAILED"


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    source: ExecutionSource
    interpreter: Interpreter
    run_limit_s: float
    inline_command: str | None = None
    script_path: Path | None = None
    environment: tuple[tuple[str, str], ...] = ()
    working_directory: Path | None = None

    def __post_init__(self) -> None:
        if self.run_limit_s <= 0:
            raise ValueError("run_limit_s must be positive")
        if self.source is ExecutionSource.INLINE:
            if not self.inline_command:
                raise ValueError("INLINE execution requires inline_command")
            if self.script_path is not None:
                raise ValueError("INLINE execution cannot carry script_path")
        elif self.source is ExecutionSource.SCRIPT_FILE:
            if self.script_path is None:
                raise ValueError("SCRIPT_FILE execution requires script_path")
            if self.inline_command is not None:
                raise ValueError("SCRIPT_FILE execution cannot carry inline_command")

        if self.source is ExecutionSource.SCRIPT_FILE and self.interpreter is Interpreter.SHELL:
            raise ValueError("SCRIPT_FILE requires an explicit interpreter family")

        keys = [key for key, _ in self.environment]
        if len(keys) != len(set(keys)):
            raise ValueError("environment contains duplicate keys")
        for key, value in self.environment:
            if not key or "\x00" in key or "=" in key:
                raise ValueError("invalid environment key")
            if "\x00" in value:
                raise ValueError("invalid environment value")


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    disposition: ExecutionDisposition
    exit_code: int | None
    stdout: str
    stderr: str
    started_monotonic_s: float | None
    finished_monotonic_s: float
    known_effects: tuple[str, ...] = ()
    message: str | None = None

    def __post_init__(self) -> None:
        if self.finished_monotonic_s < 0:
            raise ValueError("finished_monotonic_s must be non-negative")
        if self.started_monotonic_s is not None:
            if self.started_monotonic_s < 0:
                raise ValueError("started_monotonic_s must be non-negative")
            if self.finished_monotonic_s < self.started_monotonic_s:
                raise ValueError("finish cannot precede start")

        if self.disposition is ExecutionDisposition.EXITED:
            if self.started_monotonic_s is None:
                raise ValueError("EXITED report requires start time")
            if self.exit_code is None:
                raise ValueError("EXITED report requires exit_code")
        elif self.exit_code is not None:
            raise ValueError(
                f"{self.disposition.value} report must not invent an exit_code"
            )

        if self.disposition is ExecutionDisposition.START_FAILED and self.started_monotonic_s is not None:
            raise ValueError("START_FAILED must not claim that execution started")

        if len(self.known_effects) > 32:
            raise ValueError("known_effects is bounded to 32 entries")
        if any(not item or len(item) > 256 for item in self.known_effects):
            raise ValueError("known_effect entries must be 1..256 characters")
