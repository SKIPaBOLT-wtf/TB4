from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

import pytest

from tb4.fetcher.artifact_runner import (
    ArtifactDescriptor,
    ArtifactExecutionError,
    ArtifactRunner,
)
from tb4.fetcher.execution_models import ExecutionDisposition, ExecutionReport
from tb4.security import redact_sensitive_text, scan_repository, scan_text
from tb4.watchdog.ssh_bootstrap import (
    BootstrapPlatform,
    BootstrapTarget,
    DoorScratchOutcome,
    DoorScratcher,
    SshCommandResult,
    SshFailureKind,
)


ROOT = Path(__file__).resolve().parents[2]


def _descriptor(content: bytes, *, hint: str = "python", suffix: str = ".py") -> ArtifactDescriptor:
    return ArtifactDescriptor(
        descriptor_object_id="desc-security-001",
        artifact_id="desc-security-001",
        kind="REQUEST_SCRIPT",
        content_object_id="content-security-001",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        interpreter_hint=hint,
        safe_suffix=suffix,
        created_at=1000,
        expires_at=2000,
        complete=True,
    )


def test_secret_scanner_catches_high_confidence_fixtures() -> None:
    github_token = "ghp_" + ("A" * 32)
    google_key = "AIza" + ("B" * 35)
    assigned = "client_" + "secret=" + ("C" * 24)
    private_ip = "192" + ".168.44.8"

    findings = scan_text(
        "synthetic.txt",
        "\n".join((github_token, google_key, assigned, private_ip)),
    )
    codes = {finding.code for finding in findings}

    assert "GITHUB_CLASSIC_TOKEN" in codes
    assert "GOOGLE_API_KEY" in codes
    assert "ASSIGNED_SECRET" in codes
    assert "PRIVATE_IPV4" in codes


def test_current_public_repository_passes_security_scan() -> None:
    findings = scan_repository(ROOT)
    assert findings == (), "\n".join(
        f"{item.path}:{item.line} {item.code}" for item in findings
    )


def test_redactor_removes_secret_values_from_human_error_text() -> None:
    password = "super-" + "secret-" + "value"
    bearer = "ya29." + ("X" * 30)
    raw = f"password={password}; Authorization: Bearer {bearer}"

    redacted = redact_sensitive_text(raw)

    assert password not in redacted
    assert bearer not in redacted
    assert redacted.count("[REDACTED]") >= 2


@dataclass
class _OneResultTransport:
    result: SshCommandResult

    def run_fixed(self, **_kwargs):
        return self.result


def test_ssh_bootstrap_error_does_not_echo_credential_material() -> None:
    secret = "ssh-" + "password-" + "material"
    transport = _OneResultTransport(
        SshCommandResult(
            None,
            stderr=f"password={secret}",
            failure_kind=SshFailureKind.AUTH,
        )
    )
    target = BootstrapTarget(
        ssh_bootstrap=True,
        host="target-a.example",
        credential_ref="local-profile-a",
        platform=BootstrapPlatform.LINUX_SYSTEMD,
    )

    report = DoorScratcher(transport).scratch(target)

    assert report.outcome is DoorScratchOutcome.AUTH_ERROR
    assert secret not in (report.message or "")
    assert "[REDACTED]" in (report.message or "")


@dataclass
class _PermissionSpyRunner:
    directory_mode: int | None = None
    file_mode: int | None = None

    def run_script(self, request, *, cancel_requested=None):
        del cancel_requested
        assert request.script_path is not None
        assert request.working_directory is not None
        if os.name != "nt":
            self.directory_mode = stat.S_IMODE(request.working_directory.stat().st_mode)
            self.file_mode = stat.S_IMODE(request.script_path.stat().st_mode)
        return ExecutionReport(
            ExecutionDisposition.EXITED,
            0,
            "",
            "",
            1.0,
            1.1,
        )


def test_artifact_temp_material_is_private_on_posix(tmp_path: Path) -> None:
    payload = b"print('safe')\n"
    spy = _PermissionSpyRunner()
    runner = ArtifactRunner(tmp_path, spy)  # type: ignore[arg-type]

    result = runner.run_script(
        _descriptor(payload),
        payload,
        run_limit_s=5,
        now_epoch_s=1500,
    )

    assert result.exit_code == 0
    if os.name != "nt":
        assert spy.directory_mode == 0o700
        assert spy.file_mode == 0o600
    assert list(tmp_path.iterdir()) == []


def test_artifact_interpreter_allowlist_rejects_unknown_runtime(tmp_path: Path) -> None:
    payload = b"puts 'nope'\n"
    with pytest.raises(ArtifactExecutionError, match="interpreter is not allowed"):
        ArtifactRunner(tmp_path, _PermissionSpyRunner()).run_script(  # type: ignore[arg-type]
            _descriptor(payload, hint="ruby", suffix=".rb"),
            payload,
            run_limit_s=5,
            now_epoch_s=1500,
        )


def test_service_packaging_defaults_to_low_privilege_accounts() -> None:
    fetcher = (ROOT / "packaging/systemd/tb4-fetcher.service").read_text(encoding="utf-8")
    watchdog = (ROOT / "packaging/systemd/tb4-watchdog.service").read_text(encoding="utf-8")
    windows = (ROOT / "packaging/windows/install-fetcher.ps1").read_text(encoding="utf-8")

    for unit in (fetcher, watchdog):
        assert "User=tb4" in unit
        assert "Group=tb4" in unit
        assert "UMask=0077" in unit
        assert "User=root" not in unit

    assert 'NT AUTHORITY\\LocalService' in windows
    assert 'NT AUTHORITY\\LocalSystem' not in windows
