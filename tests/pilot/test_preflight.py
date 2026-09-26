from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tb4.pilot.preflight import evaluate


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config" / "examples" / "pilot.example.toml"


def test_public_pilot_template_is_structurally_valid() -> None:
    checks = evaluate(EXAMPLE, template=True)
    assert checks
    assert not [c for c in checks if c.status in {"MISSING", "INVALID", "BLOCKED"}]


def test_template_cli_runs_protocol_check_without_private_values() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "preflight.py"),
            "--config",
            str(EXAMPLE),
            "--template",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout)
    assert report["template_valid"] is True
    assert report["ready"] is False


def test_missing_enabled_capability_is_precise(tmp_path: Path) -> None:
    cfg = tmp_path / "pilot.toml"
    cfg.write_text(
        """
[drive]
root_id = "root-placeholder-private"
client_secrets_path = "/does/not/exist/client.json"
token_path = "/does/not/exist/token.json"

[watchdog]
device_id = "watchdog-host"

[target]
device_id = "target-a"
device_key = "target-a"
hostname = "example-host"
os_family = "LINUX"
address_hints = ["192.0.2.10"]

[target.wol]
enabled = true
mac = ""

[target.ssh_bootstrap]
enabled = false

[policy]
use_public_timing_defaults = true
""",
        encoding="utf-8",
    )
    checks = {c.name: c for c in evaluate(cfg)}
    assert checks["target.wol"].status == "MISSING"
    assert checks["target.ssh_bootstrap"].status == "OPTIONAL"
    assert checks["drive.client_secrets_file"].status == "MISSING"


def test_report_does_not_echo_private_values(tmp_path: Path) -> None:
    secret_marker = "sensitive-host-alias-do-not-print"
    cfg = tmp_path / "pilot.toml"
    client = tmp_path / "client.json"
    token = tmp_path / "token.json"
    client.write_text("{}", encoding="utf-8")
    token.write_text("{}", encoding="utf-8")
    cfg.write_text(
        f"""
[drive]
root_id = "private-root-id-do-not-print"
client_secrets_path = "{client}"
token_path = "{token}"

[watchdog]
device_id = "watchdog-host"

[target]
device_id = "target-a"

[target.wol]
enabled = false
mac = ""

[target.ssh_bootstrap]
enabled = true
host_alias = "{secret_marker}"
platform = "LINUX_SYSTEMD"

[policy]
use_public_timing_defaults = true
""",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "preflight.py"), "--config", str(cfg)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert secret_marker not in completed.stdout
    assert "private-root-id-do-not-print" not in completed.stdout
    assert str(tmp_path) not in completed.stdout
