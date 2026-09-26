from __future__ import annotations

from dataclasses import dataclass, field

from tb4.watchdog.ssh_bootstrap import (
    BootstrapPlatform,
    BootstrapTarget,
    DoorScratchOutcome,
    DoorScratcher,
    SshCommandResult,
    SshFailureKind,
    fixed_bootstrap_commands,
)


@dataclass
class FakeTransport:
    results: list[SshCommandResult]
    calls: list[tuple[str, str, str, float]] = field(default_factory=list)

    def run_fixed(self, *, host, credential_ref, command, timeout_s):
        self.calls.append((host, credential_ref, command, timeout_s))
        if not self.results:
            raise AssertionError("unexpected SSH call")
        return self.results.pop(0)


def target(**overrides):
    values = {
        "ssh_bootstrap": True,
        "host": "target-a.local",
        "credential_ref": "local-ssh-profile-a",
        "platform": BootstrapPlatform.LINUX_SYSTEMD,
    }
    values.update(overrides)
    return BootstrapTarget(**values)


def test_already_running_uses_one_fixed_status_command() -> None:
    transport = FakeTransport([SshCommandResult(0, stdout="active")])

    result = DoorScratcher(transport).scratch(target())

    assert result.outcome is DoorScratchOutcome.ALREADY_RUNNING
    assert result.service_running is True
    assert result.protocol_ready is False
    assert len(transport.calls) == 1
    assert transport.calls[0][2] == fixed_bootstrap_commands(
        BootstrapPlatform.LINUX_SYSTEMD
    )[0]


def test_successful_start_checks_starts_and_rechecks() -> None:
    transport = FakeTransport(
        [
            SshCommandResult(3),
            SshCommandResult(0),
            SshCommandResult(0),
        ]
    )

    result = DoorScratcher(transport).scratch(target())

    assert result.outcome is DoorScratchOutcome.STARTED
    assert result.service_running is True
    assert result.protocol_ready is False
    check, start = fixed_bootstrap_commands(BootstrapPlatform.LINUX_SYSTEMD)
    assert [call[2] for call in transport.calls] == [check, start, check]


def test_auth_failure_is_normalized_and_does_not_retry() -> None:
    transport = FakeTransport(
        [SshCommandResult(None, stderr="permission denied", failure_kind=SshFailureKind.AUTH)]
    )

    result = DoorScratcher(transport).scratch(target())

    assert result.outcome is DoorScratchOutcome.AUTH_ERROR
    assert len(transport.calls) == 1


def test_unreachable_host_is_normalized() -> None:
    transport = FakeTransport(
        [SshCommandResult(None, stderr="timeout", failure_kind=SshFailureKind.UNREACHABLE)]
    )

    result = DoorScratcher(transport).scratch(target())

    assert result.outcome is DoorScratchOutcome.UNREACHABLE
    assert result.service_running is False


def test_start_command_failure_is_reported() -> None:
    transport = FakeTransport(
        [
            SshCommandResult(3),
            SshCommandResult(5, stderr="service failed"),
        ]
    )

    result = DoorScratcher(transport).scratch(target())

    assert result.outcome is DoorScratchOutcome.START_ERROR
    assert "service failed" in (result.message or "")


def test_start_success_but_status_not_running_is_error() -> None:
    transport = FakeTransport(
        [
            SshCommandResult(3),
            SshCommandResult(0),
            SshCommandResult(3),
        ]
    )

    result = DoorScratcher(transport).scratch(target())

    assert result.outcome is DoorScratchOutcome.START_ERROR
    assert result.service_running is False


def test_capability_absent_performs_no_ssh() -> None:
    transport = FakeTransport([])

    result = DoorScratcher(transport).scratch(target(ssh_bootstrap=False))

    assert result.outcome is DoorScratchOutcome.NOT_CAPABLE
    assert transport.calls == []


def test_missing_local_credential_reference_is_invalid() -> None:
    transport = FakeTransport([])

    result = DoorScratcher(transport).scratch(target(credential_ref=None))

    assert result.outcome is DoorScratchOutcome.INVALID_TARGET
    assert transport.calls == []


def test_windows_templates_are_fixed_and_bounded() -> None:
    check, start = fixed_bootstrap_commands(BootstrapPlatform.WINDOWS_SERVICE)

    assert "TB4Fetcher" in check
    assert "TB4Fetcher" in start
    assert len(check) < 300
    assert len(start) < 300


def test_public_helper_has_no_arbitrary_command_parameter() -> None:
    # API contract regression guard: callers can supply target metadata only.
    import inspect

    parameters = inspect.signature(DoorScratcher.scratch).parameters
    assert "command" not in parameters
    assert "script" not in parameters
    assert "payload" not in parameters
