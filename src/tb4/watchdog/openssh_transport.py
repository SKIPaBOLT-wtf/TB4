from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass

from tb4.security import redact_sensitive_text
from tb4.watchdog.ssh_bootstrap import (
    BootstrapPlatform,
    SshCommandResult,
    SshFailureKind,
    fixed_bootstrap_commands,
)


_ALLOWED_COMMANDS = frozenset(
    command
    for platform_kind in BootstrapPlatform
    for command in fixed_bootstrap_commands(platform_kind)
)


@dataclass(slots=True)
class OpenSshBootstrapTransport:
    """OpenSSH adapter restricted to TB4's fixed FETCHER service commands.

    `credential_ref` must be the literal `OPENSSH_CONFIG`. Host identity,
    keys, ProxyJump, usernames, and other private details remain in the local
    OpenSSH configuration and are referenced only through the supplied host
    alias.
    """

    executable: str | None = None

    def run_fixed(
        self,
        *,
        host: str,
        credential_ref: str,
        command: str,
        timeout_s: float,
    ) -> SshCommandResult:
        if command not in _ALLOWED_COMMANDS:
            return SshCommandResult(
                None,
                failure_kind=SshFailureKind.LOCAL,
                stderr="command is not in the TB4 fixed bootstrap allowlist",
            )
        if credential_ref != "OPENSSH_CONFIG":
            return SshCommandResult(
                None,
                failure_kind=SshFailureKind.LOCAL,
                stderr="unsupported SSH credential reference",
            )
        if not host or timeout_s <= 0:
            return SshCommandResult(
                None,
                failure_kind=SshFailureKind.LOCAL,
                stderr="valid SSH host alias and positive timeout are required",
            )

        executable = self.executable or shutil.which("ssh")
        if not executable:
            return SshCommandResult(
                None,
                failure_kind=SshFailureKind.LOCAL,
                stderr="OpenSSH client is unavailable",
            )

        connect_timeout = max(1, int(math.ceil(timeout_s)))
        argv = [
            executable,
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={connect_timeout}",
            "--",
            host,
            command,
        ]
        try:
            completed = subprocess.run(
                argv,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout_s + 2.0,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return SshCommandResult(
                None,
                failure_kind=SshFailureKind.UNREACHABLE,
                stderr="SSH bootstrap timed out",
            )
        except OSError as exc:
            return SshCommandResult(
                None,
                failure_kind=SshFailureKind.LOCAL,
                stderr=redact_sensitive_text(str(exc))[:512],
            )

        stdout = redact_sensitive_text(completed.stdout)[-512:]
        stderr = redact_sensitive_text(completed.stderr)[-512:]
        lower = stderr.lower()
        if completed.returncode == 255:
            if "permission denied" in lower or "authentication" in lower:
                failure = SshFailureKind.AUTH
            else:
                failure = SshFailureKind.UNREACHABLE
            return SshCommandResult(
                completed.returncode,
                stdout,
                stderr,
                failure,
            )
        return SshCommandResult(
            completed.returncode,
            stdout,
            stderr,
            None,
        )
