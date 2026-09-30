from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

from .profile import ProfileLock, profile_for


def packaged_self_test(role: str) -> dict:
    """Import/resource/native-child checks; no credentials or Drive access."""
    from .environment import prepare_external_programs
    prepare_external_programs()
    from tb4.core.schemas import load_schema_store
    from tb4.core.state_machine import load_state_machines
    from tb4.runtime_support import load_public_defaults
    from tb4.core.protocol_names import LogicalObject
    from tb4.fetcher.return_recovery import recover_returning
    assert callable(recover_returning)
    load_schema_store().validator("fetch-ball.schema.json")
    assert load_state_machines().machine(LogicalObject.FETCH_BALL) is not None
    assert load_public_defaults()["job"]
    for name in ("watchdog", "fetcher"):
        assert callable(importlib.import_module(f"tb4.{name}.runtime").create_runtime_from_context)
    from googleapiclient.discovery_cache import get_static_doc
    assert get_static_doc("drive", "v3")
    from PySide6 import QtCore, QtWidgets
    assert QtCore.qVersion() and QtWidgets.QSystemTrayIcon
    import os
    import subprocess
    import tempfile
    from .provider import google_backend
    from .profile import ProfileError
    with tempfile.TemporaryDirectory(prefix="tb4-self-test-") as directory:
        try:
            google_backend({"drive": {"client_secrets_path": str(Path(directory) / "absent-client.json"),
                                      "token_path": str(Path(directory) / "absent-token.json")}})
        except ProfileError as exc:
            assert str(exc) == "AUTH_MISSING_LOCAL_CREDENTIALS"
        else:
            raise AssertionError("missing credentials were not refused")
    command = [os.environ["COMSPEC"], "/d", "/c", "exit", "0"] if os.name == "nt" else ["/bin/sh", "-c", "exit 0"]
    subprocess.run(command, check=True, capture_output=True, timeout=10)
    return {"role": role, "self_test": "PASS", "scope": "imports-resources-native-child-no-Drive"}


def main(fixed_role: str | None = None, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TB4 role desktop application")
    parser.add_argument("--role", choices=("watchdog", "fetcher"), default=fixed_role, required=fixed_role is None)
    parser.add_argument("--action", choices=("gui", "run", "validate", "check", "authorize", "bootstrap", "save", "recover-return", "probe-lock", "self-test", "gui-smoke"), default="gui")
    parser.add_argument("--profile-root", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if fixed_role is not None and args.role != fixed_role:
        parser.error("this executable belongs to the other role")
    profile = profile_for(args.role, args.profile_root)
    if args.action == "probe-lock":
        try:
            with ProfileLock(profile, "gui"), ProfileLock(profile, "worker"):
                return 0
        except Exception:
            return 1
    if args.action == "self-test":
        try:
            report = packaged_self_test(args.role)
        except Exception as exc:
            report = {"role": args.role, "self_test": "FAIL", "error_class": type(exc).__name__}
        if args.report:
            args.report.write_text(json.dumps(report), encoding="utf-8")
        elif sys.stdout is not None:
            print(json.dumps(report))
        return 0 if report["self_test"] == "PASS" else 1
    if args.action in {"gui", "gui-smoke"}:
        from .app import run_gui
        return run_gui(profile, smoke_report=args.report if args.action == "gui-smoke" else None,
                       smoke=args.action == "gui-smoke")
    from .environment import prepare_external_programs
    prepare_external_programs()
    from .worker import main as worker_main
    return worker_main(profile, args.action)


def watchdog_main() -> int:
    return main("watchdog")


def fetcher_main() -> int:
    return main("fetcher")


if __name__ == "__main__":
    raise SystemExit(main())
