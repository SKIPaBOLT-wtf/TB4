from __future__ import annotations

import subprocess

import pytest

from tb4.watchdog.openssh_transport import OpenSshBootstrapTransport
from tb4.watchdog.ssh_bootstrap import (
    BootstrapPlatform,
    SshFailureKind,
    fixed_bootstrap_commands,
)
from tb4.watchdog.sniffer import KnownDeviceTarget, Reachability
from tb4.watchdog.system_probe import SystemPingProbe


def test_system_ping_probe_reports_unknown_without_ping(monkeypatch) -> None:
    monkeypatch.setattr("tb4.watchdog.system_probe.shutil.which", lambda _: None)
    report = SystemPingProbe().probe(
        KnownDeviceTarget("target-a", "sniff-id", ("example.invalid",), None)
    )
    assert report.reachability is Reachability.UNKNOWN


@pytest.mark.parametrize("system,flag", [("Windows", "-n"), ("Linux", "-c")])
def test_system_ping_probe_uses_no_shell(monkeypatch, system, flag) -> None:
    observed = {}
    monkeypatch.setattr("tb4.watchdog.system_probe.platform.system", lambda: system)

    class Result:
        returncode = 0

    monkeypatch.setattr("tb4.watchdog.system_probe.shutil.which", lambda _: "/bin/ping")

    def fake_run(argv, **kwargs):
        observed["argv"] = argv
        observed["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr("tb4.watchdog.system_probe.subprocess.run", fake_run)
    report = SystemPingProbe(timeout_s=1.0).probe(
        KnownDeviceTarget("target-a", "sniff-id", ("example.invalid",), None)
    )
    assert report.reachability is Reachability.ONLINE
    assert observed["kwargs"]["shell"] is False
    assert observed["argv"][1:3] == [flag, "1"]
    assert observed["argv"][-1] == "example.invalid"


def test_openssh_transport_rejects_arbitrary_command_without_starting_ssh(monkeypatch) -> None:
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("must not execute")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = OpenSshBootstrapTransport(executable="ssh").run_fixed(
        host="target-alias",
        credential_ref="OPENSSH_CONFIG",
        command="rm -rf /",
        timeout_s=5,
    )
    assert result.failure_kind is SshFailureKind.LOCAL
    assert called is False


def test_openssh_transport_executes_only_fixed_command_without_shell(monkeypatch) -> None:
    observed = {}

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(argv, **kwargs):
        observed["argv"] = argv
        observed["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    check, _ = fixed_bootstrap_commands(BootstrapPlatform.LINUX_SYSTEMD)
    result = OpenSshBootstrapTransport(executable="ssh").run_fixed(
        host="target-alias",
        credential_ref="OPENSSH_CONFIG",
        command=check,
        timeout_s=5,
    )

    assert result.transport_ok
    assert observed["kwargs"]["shell"] is False
    assert observed["argv"][-2:] == ["target-alias", check]


def test_openssh_transport_classifies_auth_failure(monkeypatch) -> None:
    class Result:
        returncode = 255
        stdout = ""
        stderr = "Permission denied (publickey)."

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Result())
    check, _ = fixed_bootstrap_commands(BootstrapPlatform.LINUX_SYSTEMD)
    result = OpenSshBootstrapTransport(executable="ssh").run_fixed(
        host="target-alias",
        credential_ref="OPENSSH_CONFIG",
        command=check,
        timeout_s=5,
    )
    assert result.failure_kind is SshFailureKind.AUTH
