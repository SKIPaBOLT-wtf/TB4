from __future__ import annotations

import json
import math
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable

from tb4.privacy import (ERROR_CODES, OUTCOMES, STAGES, allowed, canonical_protocol_names,
                         public_diagnostic)

OPERATIONS = frozenset({"get_metadata", "read_text", "replace_text", "rename", "move", "create_folder", "create_text", "delete", "list_children"})
PROCESS_STATES = frozenset({"STOPPED", "STARTING", "RUNNING", "STOPPING", "EXITED", "FAILED"})
MAX_EVENT_BYTES = 8192


def safe_time(value, fallback=None):
    return value if type(value) in {int, float} and math.isfinite(value) and 0 <= value < 10**12 else fallback


class Telemetry:
    """Only allowlisted observations; no payload, token, ID or raw exception body."""

    def __init__(self, role: str, clock: Callable[[], float] = time.time, *, protocol_names: frozenset[str] = frozenset()) -> None:
        if role not in {"watchdog", "fetcher"}:
            raise ValueError("ROLE_INVALID")
        self.role = role
        self.protocol_names = protocol_names
        self.clock = clock
        self.lock = threading.RLock()
        self.state = "STARTING"
        self.stage = "STARTUP"
        self.last_drive_at = None
        self.last_operation = None
        self.last_outcome = None
        self.protocol_state = None
        self.error_code = None
        self.events = deque(maxlen=100)

    def set_state(self, state: str, stage: str | None = None) -> None:
        if allowed(state, PROCESS_STATES) is None or (stage is not None and allowed(stage, STAGES) is None):
            raise ValueError("STATE_INVALID")
        with self.lock:
            self.state = state
            if stage is not None:
                self.stage = stage

    def fail(self, code: str) -> None:
        with self.lock:
            self.error_code = allowed(code, ERROR_CODES, "UNCLASSIFIED_ERROR")
            self.state = "FAILED"

    def record(self, operation: str, outcome: str, name: str | None = None) -> None:
        if operation not in OPERATIONS:
            return
        safe_outcome = allowed(outcome, OUTCOMES, "UNKNOWN")
        with self.lock:
            self.last_drive_at = self.clock()
            self.last_operation = operation
            self.last_outcome = safe_outcome
            if allowed(name, self.protocol_names) is not None and name in canonical_protocol_names():
                self.protocol_state = name
            self.events.append({"at": self.last_drive_at, "operation": operation, "outcome": safe_outcome})

    def snapshot(self) -> dict:
        with self.lock:
            return {"schema_version": 1, "role": self.role, "observed_at": safe_time(self.clock(), 0),
                    "process_state": allowed(self.state, PROCESS_STATES, "FAILED"), "stage": allowed(self.stage, STAGES, "UNKNOWN"),
                    "last_drive_at": safe_time(self.last_drive_at), "last_operation": allowed(self.last_operation, OPERATIONS),
                    "last_outcome": allowed(self.last_outcome, OUTCOMES), "protocol_state": allowed(self.protocol_state, canonical_protocol_names()),
                    "error_code": allowed(self.error_code, ERROR_CODES)}


class ObservedBackend:
    """Serialize provider access and observe existing calls without adding calls."""

    def __init__(self, backend, telemetry: Telemetry) -> None:
        self.backend = backend
        self.telemetry = telemetry
        self.io_lock = threading.RLock()

    @property
    def capabilities(self):
        return self.backend.capabilities

    def get_metadata(self, *args, **kwargs):
        return self._call("get_metadata", *args, **kwargs)

    def read_text(self, *args, **kwargs):
        return self._call("read_text", *args, **kwargs)

    def replace_text(self, *args, **kwargs):
        return self._call("replace_text", *args, **kwargs)

    def rename(self, *args, **kwargs):
        return self._call("rename", *args, **kwargs)

    def move(self, *args, **kwargs):
        return self._call("move", *args, **kwargs)

    def create_folder(self, *args, **kwargs):
        return self._call("create_folder", *args, **kwargs)

    def create_text(self, *args, **kwargs):
        return self._call("create_text", *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._call("delete", *args, **kwargs)

    def list_children(self, *args, **kwargs):
        return self._call("list_children", *args, **kwargs)

    def _call(self, name, *args, **kwargs):
        method = getattr(self.backend, name)
        with self.io_lock:
            try:
                result = method(*args, **kwargs)
            except Exception:
                self.telemetry.record(name, "EXCEPTION")
                raise
            outcome = str(getattr(getattr(result, "outcome", None), "value", "UNKNOWN"))
            # Mutation receipts are not remote readback. Only metadata READs
            # can update the displayed observed protocol name.
            value = getattr(result, "value", None)
            object_name = getattr(value, "name", None) if name == "get_metadata" and result.ok else None
            self.telemetry.record(name, outcome, object_name)
            return result


def decode_snapshot(line: bytes, role: str) -> dict:
    """Reject untrusted/malformed worker output instead of displaying raw text."""
    if len(line) > MAX_EVENT_BYTES:
        raise ValueError("TELEMETRY_TOO_LARGE")
    try:
        value = json.loads(line)
        if value.get("schema_version") != 1 or value.get("role") != role:
            raise ValueError("TELEMETRY_IDENTITY_INVALID")
        if value["process_state"] not in PROCESS_STATES:
            raise ValueError("TELEMETRY_STATE_INVALID")
        for key in ("observed_at", "last_drive_at"):
            number = value.get(key)
            if (number is None and key == "last_drive_at"):
                continue
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not 0 <= number < 10**12:
                raise ValueError("TELEMETRY_TIME_INVALID")
        if value.get("last_operation") is not None and value["last_operation"] not in OPERATIONS:
            raise ValueError("TELEMETRY_OPERATION_INVALID")
        for key, values in (("stage", STAGES), ("last_outcome", OUTCOMES), ("error_code", ERROR_CODES)):
            word = value.get(key)
            if word is not None and allowed(word, values) is None:
                raise ValueError("TELEMETRY_WORD_INVALID")
        name = value.get("protocol_state")
        if name is not None and allowed(name, canonical_protocol_names()) is None:
            raise ValueError("TELEMETRY_PROTOCOL_INVALID")
        keys = Telemetry(role).snapshot().keys()
        return {key: value.get(key) for key in keys}
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("TELEMETRY_INVALID") from None


def observation_state(snapshot: dict | None, now: float, *, stale_s: float = 120) -> str:
    if snapshot is None or snapshot.get("last_drive_at") is None:
        return "UNKNOWN"
    age = now - snapshot["last_drive_at"]
    if age < -5 or now - snapshot["observed_at"] < -5:
        return "CLOCK_UNCERTAIN"
    if age > stale_s or now - snapshot["observed_at"] > 10:
        return "STALE"
    return "RECENT_RESPONSE"  # Deliberately not a claim of global/target health.


def append_event(path: Path, snapshot: dict, *, max_bytes: int = 512 * 1024) -> None:
    """Bounded private log. Rotation retains one previous file, per role."""
    if path.is_symlink() or path.with_suffix(".previous.jsonl").is_symlink():
        raise ValueError("LOG_SYMLINK_REFUSED")
    try:
        clean = decode_snapshot(json.dumps(snapshot, allow_nan=False).encode(), snapshot.get("role"))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("LOG_SNAPSHOT_INVALID") from None
    line = json.dumps(clean, sort_keys=True, allow_nan=False) + "\n"
    if path.exists() and path.stat().st_size + len(line.encode()) > max_bytes:
        path.replace(path.with_suffix(".previous.jsonl"))
    with path.open("a", encoding="utf-8") as stream:
        stream.write(line)
    if __import__("os").name != "nt":
        path.chmod(0o600)


def diagnostic_report(role: str, snapshot: dict | None, now: float) -> dict:
    clean = decode_snapshot(json.dumps(snapshot).encode(), role) if snapshot is not None else None
    return public_diagnostic(role, clean, observation_state(clean, now))
