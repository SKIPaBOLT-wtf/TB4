from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


class BootstrapPlatform(StrEnum):
    LINUX_SYSTEMD = "LINUX_SYSTEMD"
    WINDOWS_SERVICE = "WINDOWS_SERVICE"


class SshFailureKind(StrEnum):
    UNREACHABLE = "UNREACHABLE"
    AUTH = "AUTH"
    REMOTE = "REMOTE"
    LOCAL = "LOCAL"


@dataclass(frozen=True, slots=True)
class SshCommandResult:
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    failure_kind: SshFailureKind | None = None

    @property
    def transport_ok(self) -> bool:
        return self.failure_kind is None and self.exit_code is not None


@runtime_checkable
class SshBootstrapTransport(Protocol):
    """Private/local SSH boundary.

    credential_ref is an opaque local lookup key. Implementations resolve it
    outside Google Drive and outside the public repository.
    """

    def run_fixed(
        self,
        *,
        host: str,
        credential_ref: str,
        command: str,
        timeout_s: float,
    ) -> SshCommandResult:
        ...


@dataclass(frozen=True, slots=True)
class BootstrapTarget:
    ssh_bootstrap: bool
    host: str | None
    credential_ref: str | None
    platform: BootstrapPlatform


class DoorScratchOutcome(StrEnum):
    ALREADY_RUNNING = "ALREADY_RUNNING"
    STARTED = "STARTED"
    NOT_CAPABLE = "NOT_CAPABLE"
    INVALID_TARGET = "INVALID_TARGET"
    UNREACHABLE = "UNREACHABLE"
    AUTH_ERROR = "AUTH_ERROR"
    START_ERROR = "START_ERROR"
    LOCAL_ERROR = "LOCAL_ERROR"


@dataclass(frozen=True, slots=True)
class DoorScratchReport:
    outcome: DoorScratchOutcome
    service_running: bool
    protocol_ready: bool = False
    message: str | None = None


_LINUX_CHECK = "systemctl is-active --quiet tb4-fetcher"
_LINUX_START = "systemctl start tb4-fetcher"
_WINDOWS_CHECK = (
    'powershell.exe -NoProfile -NonInteractive -Command '
    '"if ((Get-Service -Name \'TB4Fetcher\' -ErrorAction SilentlyContinue).Status '
    '-eq \'Running\') { exit 0 } else { exit 3 }"'
)
_WINDOWS_START = (
    'powershell.exe -NoProfile -NonInteractive -Command '
    '"Start-Service -Name \'TB4Fetcher\' -ErrorAction Stop"'
)

_COMMANDS: dict[BootstrapPlatform, tuple[str, str]] = {
    BootstrapPlatform.LINUX_SYSTEMD: (_LINUX_CHECK, _LINUX_START),
    BootstrapPlatform.WINDOWS_SERVICE: (_WINDOWS_CHECK, _WINDOWS_START),
}


@dataclass(slots=True)
class DoorScratcher:
    """Minimal SSH bootstrap helper.

    This helper can only check/start the installed TB4 FETCHER service. It has
    no arbitrary-command API and never transports script payloads. SSH success
    proves only that the service command succeeded; DOG_PULSE remains the sole
    proof of TB4 protocol readiness and is checked by WakeManager.
    """

    transport: SshBootstrapTransport
    command_timeout_s: float = 15.0

    def __post_init__(self) -> None:
        if self.command_timeout_s <= 0:
            raise ValueError("command_timeout_s must be positive")

    def scratch(self, target: BootstrapTarget) -> DoorScratchReport:
        if not target.ssh_bootstrap:
            return DoorScratchReport(
                DoorScratchOutcome.NOT_CAPABLE,
                service_running=False,
                message="target does not advertise ssh_bootstrap capability",
            )

        if not target.host or not target.credential_ref:
            return DoorScratchReport(
                DoorScratchOutcome.INVALID_TARGET,
                service_running=False,
                message="host and local credential_ref are required",
            )

        check_command, start_command = _COMMANDS[target.platform]

        checked = self.transport.run_fixed(
            host=target.host,
            credential_ref=target.credential_ref,
            command=check_command,
            timeout_s=self.command_timeout_s,
        )
        normalized = self._transport_failure(checked)
        if normalized is not None:
            return normalized

        if checked.exit_code == 0:
            return DoorScratchReport(
                DoorScratchOutcome.ALREADY_RUNNING,
                service_running=True,
                protocol_ready=False,
                message="service reports running; DOG_PULSE is still required for TB4 readiness",
            )

        started = self.transport.run_fixed(
            host=target.host,
            credential_ref=target.credential_ref,
            command=start_command,
            timeout_s=self.command_timeout_s,
        )
        normalized = self._transport_failure(started)
        if normalized is not None:
            return normalized

        if started.exit_code != 0:
            return DoorScratchReport(
                DoorScratchOutcome.START_ERROR,
                service_running=False,
                message=self._bounded_message(started),
            )

        # Re-check the fixed service status so "start command accepted" is not
        # confused with "service is running". Protocol readiness still requires
        # a fresh DOG_PULSE in WakeManager.
        verified = self.transport.run_fixed(
            host=target.host,
            credential_ref=target.credential_ref,
            command=check_command,
            timeout_s=self.command_timeout_s,
        )
        normalized = self._transport_failure(verified)
        if normalized is not None:
            return normalized
        if verified.exit_code != 0:
            return DoorScratchReport(
                DoorScratchOutcome.START_ERROR,
                service_running=False,
                message="start returned success but service status is not running",
            )

        return DoorScratchReport(
            DoorScratchOutcome.STARTED,
            service_running=True,
            protocol_ready=False,
            message="service running; DOG_PULSE is still required for TB4 readiness",
        )

    @staticmethod
    def _transport_failure(result: SshCommandResult) -> DoorScratchReport | None:
        if result.failure_kind is None:
            return None

        outcome = {
            SshFailureKind.UNREACHABLE: DoorScratchOutcome.UNREACHABLE,
            SshFailureKind.AUTH: DoorScratchOutcome.AUTH_ERROR,
            SshFailureKind.REMOTE: DoorScratchOutcome.START_ERROR,
            SshFailureKind.LOCAL: DoorScratchOutcome.LOCAL_ERROR,
        }[result.failure_kind]
        return DoorScratchReport(
            outcome,
            service_running=False,
            message=DoorScratcher._bounded_message(result),
        )

    @staticmethod
    def _bounded_message(result: SshCommandResult, limit: int = 512) -> str:
        text = (result.stderr or result.stdout or result.failure_kind or "SSH failure")
        return str(text)[:limit]


def fixed_bootstrap_commands(platform: BootstrapPlatform) -> tuple[str, str]:
    """Expose immutable templates for validation/tests, not arbitrary execution."""

    return _COMMANDS[platform]
