from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

from .profile import Profile
from .telemetry import MAX_EVENT_BYTES, decode_snapshot


def worker_command(profile: Profile, action: str) -> list[str]:
    if getattr(sys, "frozen", False):
        suffix = ".exe" if os.name == "nt" else ""
        executable = Path(sys.executable).parent / f"tb4-{profile.role}-worker{suffix}"
        prefix = [str(executable)]
    else:
        executable = Path(sys.executable)
        if os.name == "nt" and executable.name.lower() == "pythonw.exe":
            executable = executable.with_name("python.exe")
        prefix = [str(executable), "-m", "tb4.desktop.entry", "--role", profile.role]
    return prefix + ["--action", action, "--profile-root", str(profile.directory.parent)]


class WorkerProcess:
    """Bounded queue and background pipe readers; no blocking UI calls."""

    def __init__(self, role: str) -> None:
        self.role = role
        self.process: subprocess.Popen | None = None
        self.events: queue.Queue = queue.Queue(maxsize=200)
        self.action: str | None = None
        self.write_lock = threading.Lock()
        self.session = None

    @property
    def active(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _event(self, event: dict) -> None:
        try:
            self.events.put_nowait(event)
        except queue.Full:
            try:
                self.events.get_nowait()
            except queue.Empty:
                pass
            try:
                self.events.put_nowait(event)
            except queue.Full:
                pass

    def start(self, command: list[str], action: str, payload: dict | None = None) -> None:
        if self.active:
            raise RuntimeError("WORKER_ALREADY_RUNNING")
        # Never pass a command through a shell, even when a profile path has spaces.
        options = dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       bufsize=0, shell=False)
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            options["start_new_session"] = True
        self.process = subprocess.Popen(command, **options)
        self.action = action
        process = self.process
        self.session = id(process)
        readers = [threading.Thread(target=self._read_stdout, args=(process,), daemon=True),
                   threading.Thread(target=self._discard_stderr, args=(process,), daemon=True)]
        for reader in readers:
            reader.start()
        threading.Thread(target=self._wait, args=(process, action, readers), daemon=True).start()
        if payload is not None:
            threading.Thread(target=self.send, args=(payload,), daemon=True).start()

    def send(self, payload: dict) -> bool:
        with self.write_lock:
            process = self.process
            if process is None or process.poll() is not None or process.stdin is None:
                return False
            try:
                data = (json.dumps(payload, ensure_ascii=True) + "\n").encode("utf-8")
                if len(data) > 2 * 1024 * 1024:
                    raise ValueError("CONTROL_MESSAGE_TOO_LARGE")
                # Only the small stop command is sent on the UI thread. The
                # larger configuration payload is sent from an action thread.
                offset = 0
                while offset < len(data):
                    count = process.stdin.write(data[offset:])
                    if not count:
                        return False
                    offset += count
                process.stdin.flush()
                return True
            except (BrokenPipeError, OSError):
                return False

    def request_stop(self) -> bool:
        return self.send({"op": "stop"})

    def _read_stdout(self, process) -> None:
        stream = process.stdout
        assert stream is not None
        discarding = False
        try:
            while True:
                line = stream.readline(MAX_EVENT_BYTES + 1)
                if not line:
                    break
                if discarding or len(line) > MAX_EVENT_BYTES:
                    discarding = not line.endswith(b"\n")
                    self._event({"kind": "error", "code": "WORKER_OUTPUT_INVALID", "session": id(process)})
                    continue
                try:
                    snapshot = decode_snapshot(line, self.role)
                    self._event({"kind": "snapshot", "snapshot": snapshot, "session": id(process)})
                except ValueError:
                    self._event({"kind": "error", "code": "WORKER_OUTPUT_INVALID", "session": id(process)})
        finally:
            stream.close()

    def _discard_stderr(self, process) -> None:
        stream = process.stderr
        assert stream is not None
        announced = False
        try:
            while stream.read(4096):
                if not announced:
                    self._event({"kind": "error", "code": "WORKER_STDERR_REDACTED", "session": id(process)})
                    announced = True
        finally:
            stream.close()

    def _wait(self, process, action, readers) -> None:
        code = process.wait()
        for reader in readers:
            reader.join(timeout=2)
        with self.write_lock:
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except OSError:
                    pass
        self._event({"kind": "exit", "action": action, "code": code, "session": id(process)})
