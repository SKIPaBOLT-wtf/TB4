from __future__ import annotations

import subprocess
from pathlib import Path

from tb4.fetcher.execution_models import ExecutionRequest, ExecutionSource, Interpreter
from tb4.fetcher.subprocess_runner import SubprocessRunner
from tb4.platform.windows_process import _taskkill_argv, terminate_windows_process_tree
from tb4.platform.windows_service import (
    DEFAULT_WINDOWS_CONFIG,
    SERVICE_DISPLAY_NAME,
    SERVICE_NAME,
)


ROOT = Path(__file__).resolve().parents[2]


class FakeProcess:
    pid = 4242

    def __init__(self, *, time_out_once: bool = False) -> None:
        self.running = True
        self.time_out_once = time_out_once
        self.wait_calls = 0

    def poll(self):
        return None if self.running else 0

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.time_out_once and self.wait_calls == 1:
            raise subprocess.TimeoutExpired("fake", timeout)
        self.running = False
        return 0


def test_windows_service_identity_and_config_are_deterministic() -> None:
    assert SERVICE_NAME == "TB4Fetcher"
    assert SERVICE_DISPLAY_NAME == "TB4 FETCHER"
    assert DEFAULT_WINDOWS_CONFIG == Path(r"C:\ProgramData\TB4\fetcher.toml")


def test_taskkill_uses_argv_not_shell_text() -> None:
    assert _taskkill_argv(42, force=False) == ["taskkill", "/PID", "42", "/T"]
    assert _taskkill_argv(42, force=True) == ["taskkill", "/PID", "42", "/T", "/F"]


def test_windows_tree_termination_escalates_to_force() -> None:
    process = FakeProcess(time_out_once=True)
    commands: list[list[str]] = []

    def fake_run(argv, **kwargs):
        commands.append(list(argv))
        assert "shell" not in kwargs
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    outcome = terminate_windows_process_tree(
        process, grace_s=1.0, run_command=fake_run
    )

    assert outcome.stopped
    assert outcome.forced
    assert commands == [
        ["taskkill", "/PID", "4242", "/T"],
        ["taskkill", "/PID", "4242", "/T", "/F"],
    ]


def test_powershell_script_uses_file_and_no_profile(monkeypatch) -> None:
    runner = SubprocessRunner()
    monkeypatch.setattr(runner, "_require", lambda executable: executable)
    request = ExecutionRequest(
        source=ExecutionSource.SCRIPT_FILE,
        interpreter=Interpreter.POWERSHELL,
        run_limit_s=30,
        script_path=Path(r"C:\ProgramData\TB4\work\job.ps1"),
    )

    argv = runner._script_argv(request)

    assert "-NoProfile" in argv
    assert "-NonInteractive" in argv
    assert "-File" in argv
    assert "-Command" not in argv


def test_packaging_scripts_contain_no_embedded_secret() -> None:
    for name in ("install-fetcher.ps1", "remove-fetcher.ps1"):
        text = (ROOT / "packaging" / "windows" / name).read_text(encoding="utf-8")
        lowered = text.lower()
        assert "private_key" not in lowered
        assert "password =" not in lowered
