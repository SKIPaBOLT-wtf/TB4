from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PLACEHOLDER = "replace-at-deploy-time"
DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MAC_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    status: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def _nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _present_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value != PLACEHOLDER


def _check_device_id(name: str, value: Any) -> Check:
    if not _present_string(value):
        return Check(name, "MISSING", "stable device ID is required")
    if not DEVICE_ID_RE.fullmatch(value):
        return Check(name, "INVALID", "device ID must use only letters, digits, dot, underscore, or hyphen")
    return Check(name, "PASS", "stable device ID is configured")


def _check_private_file(name: str, value: Any, *, template: bool) -> Check:
    if not _present_string(value):
        if template and value == PLACEHOLDER:
            return Check(name, "PASS", "deployment placeholder is present")
        return Check(name, "MISSING", "private local file path is required")
    if template:
        return Check(name, "PASS", "template field is structurally valid")
    path = Path(value).expanduser()
    if not path.is_file():
        return Check(name, "MISSING", "configured private file is not present")
    return Check(name, "PASS", "configured private file is present")


def evaluate(config_path: Path, *, template: bool = False) -> list[Check]:
    checks: list[Check] = []
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return [Check("config.parse", "INVALID", "pilot configuration could not be parsed")]

    checks.append(Check("config.parse", "PASS", "pilot TOML parsed"))

    root_id = _nested(data, "drive", "root_id")
    if _present_string(root_id):
        checks.append(Check("drive.root_id", "PASS", "explicit existing root is configured"))
    elif template and root_id == PLACEHOLDER:
        checks.append(Check("drive.root_id", "PASS", "deployment placeholder is present"))
    else:
        checks.append(Check("drive.root_id", "MISSING", "explicit existing TB4 root ID is required"))

    checks.append(
        _check_private_file(
            "drive.client_secrets_file",
            _nested(data, "drive", "client_secrets_path"),
            template=template,
        )
    )
    checks.append(
        _check_private_file(
            "drive.token_file",
            _nested(data, "drive", "token_path"),
            template=template,
        )
    )

    checks.append(
        _check_device_id("watchdog.device_id", _nested(data, "watchdog", "device_id"))
    )
    checks.append(
        _check_device_id("target.device_id", _nested(data, "target", "device_id"))
    )

    wol_enabled = _nested(data, "target", "wol", "enabled")
    if wol_enabled is False:
        checks.append(Check("target.wol", "OPTIONAL", "Wake-on-LAN is intentionally disabled"))
    elif wol_enabled is True:
        mac = _nested(data, "target", "wol", "mac")
        if template and mac == PLACEHOLDER:
            checks.append(Check("target.wol", "PASS", "WOL deployment placeholder is present"))
        elif not _present_string(mac):
            checks.append(Check("target.wol", "MISSING", "WOL is enabled but MAC is missing"))
        elif not MAC_RE.fullmatch(mac):
            checks.append(Check("target.wol", "INVALID", "WOL MAC has invalid format"))
        else:
            checks.append(Check("target.wol", "PASS", "WOL capability is configured"))
    else:
        checks.append(Check("target.wol", "INVALID", "enabled must be true or false"))

    ssh_enabled = _nested(data, "target", "ssh_bootstrap", "enabled")
    if ssh_enabled is False:
        checks.append(Check("target.ssh_bootstrap", "OPTIONAL", "SSH bootstrap is intentionally disabled"))
    elif ssh_enabled is True:
        alias = _nested(data, "target", "ssh_bootstrap", "host_alias")
        if template and alias == PLACEHOLDER:
            checks.append(Check("target.ssh_bootstrap", "PASS", "SSH deployment placeholder is present"))
        elif not _present_string(alias):
            checks.append(Check("target.ssh_bootstrap", "MISSING", "SSH bootstrap is enabled but host alias is missing"))
        else:
            checks.append(Check("target.ssh_bootstrap", "PASS", "SSH bootstrap host alias is configured"))
    else:
        checks.append(Check("target.ssh_bootstrap", "INVALID", "enabled must be true or false"))

    timing = _nested(data, "policy", "use_public_timing_defaults")
    if timing is True:
        checks.append(Check("policy.timing_defaults", "PASS", "public timing defaults selected"))
    else:
        checks.append(Check("policy.timing_defaults", "INVALID", "first pilot must explicitly use public timing defaults"))

    return checks


def protocol_check() -> Check:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate_protocol.py")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode == 0:
        return Check("repository.protocol", "PASS", "canonical protocol/config validation passed")
    return Check("repository.protocol", "BLOCKED", "canonical protocol/config validation failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sanitized TB4 private-pilot readiness check")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--template",
        action="store_true",
        help="validate the public example structure without requiring private files",
    )
    args = parser.parse_args(argv)

    checks = [protocol_check(), *evaluate(args.config, template=args.template)]
    blocking = [check for check in checks if check.status in {"MISSING", "INVALID", "BLOCKED"}]
    report = {
        "ready": not blocking and not args.template,
        "template_valid": not blocking if args.template else None,
        "checks": [check.as_dict() for check in checks],
    }
    print(json.dumps(report, sort_keys=True))
    return 0 if not blocking else 2


