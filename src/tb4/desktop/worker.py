from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from .profile import (Profile, ProfileError, ProfileLock, canonical_validate,
                      parse_config, read_config, save_config)
from .telemetry import ObservedBackend, Telemetry
from tb4.privacy import canonical_protocol_names, exception_code


class SnapshotEmitter:
    def __init__(self, telemetry: Telemetry, stream=None) -> None:
        self.telemetry = telemetry
        self.stream = stream if stream is not None else sys.stdout
        self.lock = threading.Lock()
        self.closed = threading.Event()

    def emit(self) -> None:
        with self.lock:
            try:
                self.stream.write(json.dumps(self.telemetry.snapshot(), allow_nan=False) + "\n")
                self.stream.flush()
            except (BrokenPipeError, OSError):
                self.closed.set()


def _listen(stream, stop: threading.Event) -> None:
    try:
        while not stop.is_set():
            line = stream.readline(1025)
            if not line:
                stop.set()  # GUI pipe disappeared: stop accepting new work.
                return
            if len(line) > 1024:
                stop.set()
                return
            try:
                message = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(message, dict) and message.get("op") == "stop":
                stop.set()
    except (OSError, ValueError):
        stop.set()


def refuse_legacy_service(role: str) -> None:
    """Never silently operate an old service alongside a desktop role."""
    if os.name == "nt":
        name = "TB4Fetcher" if role == "fetcher" else "TB4Watchdog"
        result = subprocess.run(["sc.exe", "query", name], capture_output=True,
                                timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode == 0:
            # Refuse even a stopped installed service: its future autostart is
            # outside this desktop process's ownership.
            raise ProfileError("LEGACY_SERVICE_INSTALLED")
        if result.returncode != 1060:
            raise ProfileError("SERVICE_PRESENCE_UNCONFIRMED")
    elif sys.platform.startswith("linux"):
        # Exact unit lookups only. No system-wide service enumeration.
        for scope in ([], ["--user"]):
            result = subprocess.run(["systemctl", *scope, "show", f"tb4-{role}.service",
                                     "--property=LoadState", "--value"],
                                    capture_output=True, timeout=10)
            state = result.stdout.decode(errors="replace").strip()
            if state and state != "not-found":
                raise ProfileError("LEGACY_SERVICE_INSTALLED")
            if state != "not-found":
                raise ProfileError("SERVICE_PRESENCE_UNCONFIRMED")


def run_production(profile: Profile, telemetry: Telemetry, stop: threading.Event) -> int:
    from tb4.runtime_support import build_context
    from tb4.service_host import ServiceHost
    from .provider import google_backend
    telemetry.set_state("STARTING", "CONFIGURATION")
    config = parse_config(profile.role, read_config(profile.config))
    canonical_validate(profile.role, profile.config)
    if stop.is_set():
        return 0
    refuse_legacy_service(profile.role)
    telemetry.set_state("STARTING", "AUTHORIZATION")
    backend = ObservedBackend(google_backend(config), telemetry)
    if stop.is_set():
        return 0
    telemetry.set_state("STARTING", "ROOT_AND_MAP")
    context = build_context(profile.config, backend=backend)
    if stop.is_set():
        return 0
    telemetry.set_state("STARTING", "ROLE_STARTUP")
    factory = importlib.import_module(f"tb4.{profile.role}.runtime").create_runtime_from_context
    runtime = factory(context)
    if stop.is_set():
        return 0
    telemetry.set_state("RUNNING", "ROLE_LOOP")
    return ServiceHost(runtime, stop_event=stop).run()


def run_action(profile: Profile, action: str, telemetry: Telemetry, stop: threading.Event) -> int:
    if action == "save":
        message = json.loads(sys.stdin.readline(2 * 1024 * 1024 + 1))
        if not isinstance(message, dict) or not isinstance(message.get("text"), str):
            raise ProfileError("CONFIG_SAVE_MESSAGE_INVALID")
        save_config(profile, message["text"], expected_digest=message.get("expected_digest"))
        return 0
    recovery_ticket = None
    if action == "recover-return":
        if profile.role != "fetcher":
            raise ProfileError("RETURN_RECOVERY_REQUIRES_FETCHER")
        from tb4.fetcher.return_recovery import ReturnRecoveryError, validate_ticket
        try:
            message = sys.stdin.readline(4097)
            if len(message) > 4096:
                raise ValueError("bounded recovery ticket required")
            recovery_ticket = validate_ticket(json.loads(message))
        except (ValueError, ReturnRecoveryError) as exc:
            raise ProfileError("RETURN_RECOVERY_TICKET_INVALID") from exc
        # The action payload must be consumed before the stop listener starts.
        threading.Thread(target=_listen, args=(sys.stdin, stop), daemon=True).start()
    with ProfileLock(profile):
        if action == "run":
            return run_production(profile, telemetry, stop)
        config = parse_config(profile.role, read_config(profile.config))
        canonical_validate(profile.role, profile.config)
        if action == "validate":
            return 0
        if action == "recover-return":
            refuse_legacy_service(profile.role)
        from .provider import google_backend
        telemetry.set_state("STARTING", "AUTHORIZATION")
        backend = ObservedBackend(google_backend(config, interactive=action == "authorize"), telemetry)
        if action == "authorize":
            return 0
        if stop.is_set():
            return 0
        root_id = config["drive"]["root_id"]
        telemetry.set_state("STARTING", "ROOT_AND_MAP")
        if action == "bootstrap":
            if profile.role != "watchdog":
                raise ProfileError("BOOTSTRAP_REQUIRES_WATCHDOG")
            from tb4.drive.bootstrap import bootstrap_tree
            bootstrap_tree(backend, root_id=root_id)
            return 0
        if action == "check":
            from tb4.runtime_support import discover_park_map
            discover_park_map(backend, root_id)
            mount = config.get("desktop", {}).get("local_drive_folder", "")
            if mount and not Path(mount).is_dir():
                raise ProfileError("OPTIONAL_LOCAL_MOUNT_UNAVAILABLE")
            return 0
        if action == "recover-return":
            from tb4.runtime_support import build_context
            from tb4.fetcher.return_recovery import ReturnRecoveryError, recover_returning
            context = build_context(profile.config, backend=backend)
            telemetry.set_state("STARTING", "ROLE_STARTUP")
            try:
                recover_returning(context, recovery_ticket, now_epoch_s=int(time.time()),
                                  stop_requested=stop.is_set)
            except ReturnRecoveryError as exc:
                raise ProfileError(str(exc)) from exc
            return 0
        raise ProfileError("ACTION_INVALID")


def main(profile: Profile, action: str) -> int:
    stop = threading.Event()
    finished = threading.Event()
    telemetry = Telemetry(profile.role)
    emitter = SnapshotEmitter(telemetry)
    if action not in {"save", "recover-return"}:
        threading.Thread(target=_listen, args=(sys.stdin, stop), daemon=True).start()

    def pulse():
        while not finished.is_set():
            if stop.is_set() and telemetry.state == "RUNNING":
                telemetry.set_state("STOPPING", "COOPERATIVE_STOP")
            emitter.emit()
            if emitter.closed.is_set():
                stop.set()
            finished.wait(2.0)
    thread = threading.Thread(target=pulse, daemon=True)
    thread.start()
    try:
        telemetry.protocol_names = canonical_protocol_names()
        code = int(run_action(profile, action, telemetry, stop))
        telemetry.set_state("EXITED" if code == 0 else "FAILED", "ACTION_FINISHED")
        return code
    except Exception as exc:
        if isinstance(exc, ProfileError):
            telemetry.fail(str(exc))
        else:
            telemetry.fail(exception_code(exc))
        return 1
    finally:
        finished.set()
        emitter.emit()
        thread.join(timeout=3)
