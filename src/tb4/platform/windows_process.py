from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass


RunCommand = Callable[..., subprocess.CompletedProcess[bytes]]


@dataclass(frozen=True, slots=True)
class WindowsTreeTermination:
    stopped: bool
    forced: bool
    message: str | None = None


def _taskkill_argv(pid: int, *, force: bool) -> list[str]:
    if pid <= 0:
        raise ValueError("pid must be positive")
    argv = ["taskkill", "/PID", str(pid), "/T"]
    if force:
        argv.append("/F")
    return argv


def terminate_windows_process_tree(
    process: subprocess.Popen[bytes],
    *,
    grace_s: float,
    run_command: RunCommand = subprocess.run,
) -> WindowsTreeTermination:
    """Terminate a Windows process tree without shell command construction.

    taskkill /T is used because terminating only the direct Popen process can
    orphan descendants. Arguments are always passed as an argv list.
    """

    if grace_s <= 0:
        raise ValueError("grace_s must be positive")
    if process.poll() is not None:
        return WindowsTreeTermination(stopped=True, forced=False)

    graceful = run_command(
        _taskkill_argv(process.pid, force=False),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    try:
        process.wait(timeout=grace_s)
        return WindowsTreeTermination(
            stopped=True,
            forced=False,
            message=_command_message(graceful),
        )
    except subprocess.TimeoutExpired:
        forced = run_command(
            _taskkill_argv(process.pid, force=True),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        try:
            process.wait(timeout=grace_s)
            return WindowsTreeTermination(
                stopped=True,
                forced=True,
                message=_command_message(forced),
            )
        except subprocess.TimeoutExpired:
            return WindowsTreeTermination(
                stopped=False,
                forced=True,
                message=_command_message(forced) or "process tree did not exit after forced taskkill",
            )


def _command_message(result: subprocess.CompletedProcess[bytes]) -> str | None:
    if result.returncode == 0:
        return None
    raw = result.stderr or result.stdout or b""
    text = raw.decode("utf-8", errors="replace").strip()
    return text or f"taskkill exited with code {result.returncode}"
