from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from tb4.drive.backend import DriveBackend
from tb4.drive.errors import BackendOutcome

from .execution_models import ExecutionReport


class ArtifactSpoolError(RuntimeError):
    pass


@dataclass(slots=True)
class OutputCapture:
    """Disk-backed full-output capture with bounded storage.

    SubprocessRunner may call observe() from one stdout reader thread and one
    stderr reader thread. Each stream owns its own file handle, so no shared
    write cursor exists. RAM remains bounded by SubprocessRunner's tail buffers.
    """

    root: Path
    max_total_bytes: int

    def __post_init__(self) -> None:
        if self.max_total_bytes <= 0:
            raise ValueError("max_total_bytes must be positive")
        self.root = self.root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.work_dir = Path(tempfile.mkdtemp(prefix="tb4-output-", dir=self.root))
        self.stdout_path = self.work_dir / "stdout.bin"
        self.stderr_path = self.work_dir / "stderr.bin"
        self._stdout = self.stdout_path.open("xb")
        self._stderr = self.stderr_path.open("xb")
        self.stdout_bytes = 0
        self.stderr_bytes = 0
        self.error: str | None = None
        self._closed = False

    @property
    def total_bytes(self) -> int:
        return self.stdout_bytes + self.stderr_bytes

    def observe(self, stream_name: str, chunk: bytes) -> None:
        if self.error is not None or not chunk:
            return

        if self.total_bytes + len(chunk) > self.max_total_bytes:
            self.error = (
                f"captured output exceeds max_total_bytes={self.max_total_bytes}"
            )
            return

        try:
            if stream_name == "stdout":
                self._stdout.write(chunk)
                self.stdout_bytes += len(chunk)
            elif stream_name == "stderr":
                self._stderr.write(chunk)
                self.stderr_bytes += len(chunk)
            else:
                self.error = f"unknown output stream {stream_name!r}"
        except OSError as exc:
            self.error = f"output spool write failed: {exc}"

    def close(self) -> None:
        if self._closed:
            return
        for handle in (self._stdout, self._stderr):
            try:
                handle.flush()
                handle.close()
            except OSError as exc:
                if self.error is None:
                    self.error = f"output spool close failed: {exc}"
        self._closed = True

    def read_text(self) -> tuple[str, str]:
        self.close()
        if self.error is not None:
            raise ArtifactSpoolError(self.error)
        return (
            self.stdout_path.read_bytes().decode("utf-8", errors="replace"),
            self.stderr_path.read_bytes().decode("utf-8", errors="replace"),
        )

    def cleanup(self) -> None:
        self.close()
        shutil.rmtree(self.work_dir, ignore_errors=True)


@dataclass(frozen=True, slots=True)
class BoundedResult:
    stdout_tail: str
    stderr_tail: str
    result_artifact_id: str | None
    result_artifact_sha256: str | None
    result_artifact_size_bytes: int | None
    full_output_preserved: bool


@dataclass(slots=True)
class ArtifactSpool:
    backend: DriveBackend
    toy_box_folder_id: str
    temp_root: Path
    inline_result_max_bytes: int = 32_768
    result_tail_max_chars: int = 4_096
    max_result_artifact_bytes: int = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        if self.inline_result_max_bytes <= 0:
            raise ValueError("inline_result_max_bytes must be positive")
        if self.result_tail_max_chars <= 0:
            raise ValueError("result_tail_max_chars must be positive")
        if self.max_result_artifact_bytes < self.inline_result_max_bytes:
            raise ValueError(
                "max_result_artifact_bytes must be >= inline_result_max_bytes"
            )
        self.temp_root = self.temp_root.resolve()
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def new_capture(self) -> OutputCapture:
        return OutputCapture(self.temp_root, self.max_result_artifact_bytes)

    def finalize(
        self,
        report: ExecutionReport,
        capture: OutputCapture,
        *,
        job_id: str,
        now_epoch_s: int,
        retention_s: int,
    ) -> BoundedResult:
        try:
            stdout, stderr = capture.read_text()
            payload = {
                "stdout": stdout,
                "stderr": stderr,
            }
            serialized = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            serialized_bytes = serialized.encode("utf-8")

            stdout_tail = stdout[-self.result_tail_max_chars :]
            stderr_tail = stderr[-self.result_tail_max_chars :]

            if len(serialized_bytes) <= self.inline_result_max_bytes:
                return BoundedResult(
                    stdout_tail=stdout,
                    stderr_tail=stderr,
                    result_artifact_id=None,
                    result_artifact_sha256=None,
                    result_artifact_size_bytes=None,
                    full_output_preserved=True,
                )

            if len(serialized_bytes) > self.max_result_artifact_bytes:
                raise ArtifactSpoolError(
                    "serialized result exceeds max_result_artifact_bytes"
                )

            digest = hashlib.sha256(serialized_bytes).hexdigest()
            token = hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:20]

            content_created = self.backend.create_text(
                self.toy_box_folder_id,
                f"result-content-{token}",
                serialized,
            )
            content_obj = self._require_success(content_created, "create result content")
            content_id = content_obj.metadata.object_id

            content_read = self.backend.read_text(content_id)
            content_remote = self._require_success(content_read, "read back result content")
            remote_bytes = content_remote.text.encode("utf-8")
            if len(remote_bytes) != len(serialized_bytes):
                raise ArtifactSpoolError("result content size readback mismatch")
            if hashlib.sha256(remote_bytes).hexdigest() != digest:
                raise ArtifactSpoolError("result content hash readback mismatch")

            descriptor_created = self.backend.create_text(
                self.toy_box_folder_id,
                f"result-descriptor-{token}",
                "{}",
            )
            descriptor_obj = self._require_success(
                descriptor_created,
                "create result descriptor",
            )
            descriptor_id = descriptor_obj.metadata.object_id
            descriptor = {
                "schema_version": 1,
                "protocol_major": 1,
                "artifact_id": descriptor_id,
                "kind": "RESULT_TEXT",
                "content_object_id": content_id,
                "size_bytes": len(serialized_bytes),
                "sha256": digest,
                "interpreter_hint": None,
                "safe_suffix": ".json",
                "created_at": now_epoch_s,
                "expires_at": now_epoch_s + retention_s,
                "complete": True,
            }
            descriptor_text = json.dumps(
                descriptor,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )

            descriptor_write = self.backend.replace_text(
                descriptor_id,
                descriptor_text,
                expected_version_token=descriptor_obj.metadata.version_token,
            )
            self._require_success(descriptor_write, "write result descriptor")

            descriptor_read = self.backend.read_text(descriptor_id)
            descriptor_remote = self._require_success(
                descriptor_read,
                "read back result descriptor",
            )
            try:
                parsed = json.loads(descriptor_remote.text)
            except json.JSONDecodeError as exc:
                raise ArtifactSpoolError(
                    f"result descriptor readback is invalid JSON: {exc}"
                ) from exc
            if parsed != descriptor:
                raise ArtifactSpoolError("result descriptor readback mismatch")

            return BoundedResult(
                stdout_tail=stdout_tail,
                stderr_tail=stderr_tail,
                result_artifact_id=descriptor_id,
                result_artifact_sha256=digest,
                result_artifact_size_bytes=len(serialized_bytes),
                full_output_preserved=True,
            )
        finally:
            capture.cleanup()

    @staticmethod
    def _require_success(result, operation: str):
        if result.outcome is not BackendOutcome.SUCCESS or result.value is None:
            raise ArtifactSpoolError(
                f"{operation} failed with {result.outcome.value}: {result.message or ''}".rstrip()
            )
        return result.value
