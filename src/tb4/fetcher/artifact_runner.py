from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .execution_models import ExecutionRequest, ExecutionSource, Interpreter, ExecutionReport
from .runner import CancelCheck
from .subprocess_runner import SubprocessRunner


class ArtifactExecutionError(ValueError):
    pass


_HINT_TO_INTERPRETER = {
    "pwsh": Interpreter.PWSH,
    "powershell": Interpreter.POWERSHELL,
    "bash": Interpreter.BASH,
    "sh": Interpreter.SH,
    "python3": Interpreter.PYTHON3,
    "python": Interpreter.PYTHON,
}

_SUFFIX_BY_HINT = {
    "pwsh": ".ps1",
    "powershell": ".ps1",
    "bash": ".sh",
    "sh": ".sh",
    "python3": ".py",
    "python": ".py",
}


@dataclass(frozen=True, slots=True)
class ArtifactDescriptor:
    descriptor_object_id: str
    artifact_id: str
    kind: str
    content_object_id: str
    size_bytes: int
    sha256: str
    interpreter_hint: str | None
    safe_suffix: str
    created_at: int
    expires_at: int
    complete: bool

    def __post_init__(self) -> None:
        if self.descriptor_object_id != self.artifact_id:
            raise ArtifactExecutionError(
                "descriptor body artifact_id does not match exact descriptor object ID"
            )
        if not self.complete:
            raise ArtifactExecutionError("artifact descriptor is not complete")
        if self.size_bytes < 0:
            raise ArtifactExecutionError("artifact size must be non-negative")
        if len(self.sha256) != 64 or any(ch not in "0123456789abcdef" for ch in self.sha256):
            raise ArtifactExecutionError("artifact sha256 is invalid")

    def validate_script_policy(self) -> Interpreter:
        if self.kind != "REQUEST_SCRIPT":
            raise ArtifactExecutionError("artifact is not a request script")
        if self.interpreter_hint not in _HINT_TO_INTERPRETER:
            raise ArtifactExecutionError("request script interpreter is not allowed")
        expected_suffix = _SUFFIX_BY_HINT[self.interpreter_hint]
        if self.safe_suffix != expected_suffix:
            raise ArtifactExecutionError(
                f"suffix {self.safe_suffix!r} does not match interpreter {self.interpreter_hint!r}"
            )
        return _HINT_TO_INTERPRETER[self.interpreter_hint]


@dataclass(slots=True)
class ArtifactRunner:
    temp_root: Path
    process_runner: SubprocessRunner
    max_script_bytes: int = 16 * 1024 * 1024
    preserve_failed_temp: bool = False

    def __post_init__(self) -> None:
        self.temp_root = self.temp_root.resolve()
        if self.max_script_bytes <= 0:
            raise ValueError("max_script_bytes must be positive")
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def run_script(
        self,
        descriptor: ArtifactDescriptor,
        content: bytes,
        *,
        run_limit_s: float,
        now_epoch_s: int,
        cancel_requested: CancelCheck | None = None,
    ) -> ExecutionReport:
        interpreter = descriptor.validate_script_policy()

        if descriptor.expires_at <= now_epoch_s:
            raise ArtifactExecutionError("artifact is expired")
        if len(content) != descriptor.size_bytes:
            raise ArtifactExecutionError("artifact byte size does not match descriptor")
        if len(content) > self.max_script_bytes:
            raise ArtifactExecutionError("artifact exceeds local script size policy")
        digest = hashlib.sha256(content).hexdigest()
        if digest != descriptor.sha256:
            raise ArtifactExecutionError("artifact hash does not match descriptor")

        token = hashlib.sha256(descriptor.artifact_id.encode("utf-8")).hexdigest()[:20]
        work_dir = Path(
            tempfile.mkdtemp(
                prefix=f"tb4-{token}-",
                dir=self.temp_root,
            )
        )
        script_path = work_dir / f"fetch-{token}{descriptor.safe_suffix}"

        try:
            self._write_verified(script_path, content, descriptor.sha256)
            request = ExecutionRequest(
                source=ExecutionSource.SCRIPT_FILE,
                interpreter=interpreter,
                run_limit_s=run_limit_s,
                script_path=script_path,
                working_directory=work_dir,
            )
            report = self.process_runner.run_script(
                request,
                cancel_requested=cancel_requested,
            )
            if self.preserve_failed_temp and report.exit_code not in {0, None}:
                return report
            return report
        finally:
            if not self.preserve_failed_temp or not script_path.exists():
                shutil.rmtree(work_dir, ignore_errors=True)
            elif script_path.exists():
                # Debug preservation is explicit and local-only. Caller owns later cleanup.
                pass

    @staticmethod
    def _write_verified(path: Path, content: bytes, expected_sha256: str) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(path, flags, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=True) as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                path.unlink()
            except OSError:
                pass
            raise

        materialized = path.read_bytes()
        if len(materialized) != len(content):
            path.unlink(missing_ok=True)
            raise ArtifactExecutionError("materialized script size verification failed")
        if hashlib.sha256(materialized).hexdigest() != expected_sha256:
            path.unlink(missing_ok=True)
            raise ArtifactExecutionError("materialized script hash verification failed")
