from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class PilotConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class GeneratedConfigs:
    watchdog: str
    fetcher: str


def _table(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise PilotConfigError(f"missing [{key}] table")
    return value


def _string(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PilotConfigError(f"missing string field {key!r}")
    return value.strip()


def _bool(data: Mapping[str, Any], key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise PilotConfigError(f"field {key!r} must be boolean")
    return value


def _q(value: str) -> str:
    # JSON string syntax is valid TOML basic-string syntax for our supported values.
    return json.dumps(value)


def _string_array(values: Any, key: str) -> list[str]:
    if not isinstance(values, list) or not all(
        isinstance(item, str) and item.strip() for item in values
    ):
        raise PilotConfigError(f"field {key!r} must be a string array")
    return [item.strip() for item in values]


def build_configs(data: Mapping[str, Any]) -> GeneratedConfigs:
    drive = _table(data, "drive")
    watchdog = _table(data, "watchdog")
    target = _table(data, "target")
    wol = _table(target, "wol")
    ssh = _table(target, "ssh_bootstrap")
    fetcher = _table(target, "fetcher")
    network = data.get("network", {})
    if not isinstance(network, Mapping):
        raise PilotConfigError("[network] must be a table")

    root_id = _string(drive, "root_id")
    client = _string(drive, "client_secrets_path")
    token = _string(drive, "token_path")

    device_id = _string(target, "device_id")
    device_key = _string(target, "device_key")
    hostname = _string(target, "hostname")
    os_family = _string(target, "os_family")
    addresses = _string_array(target.get("address_hints"), "address_hints")
    if os_family not in {"LINUX", "WINDOWS", "MACOS", "OTHER"}:
        raise PilotConfigError("target os_family is invalid")

    wol_enabled = _bool(wol, "enabled")
    ssh_enabled = _bool(ssh, "enabled")
    ephemeral = _bool(fetcher, "ephemeral")

    discovery_cidrs = _string_array(
        network.get("discovery_cidrs", []),
        "discovery_cidrs",
    )

    watchdog_text = f"""[watchdog]
device_id = {_q(_string(watchdog, "device_id"))}

[drive]
root_id = {_q(root_id)}
client_secrets_path = {_q(client)}
token_path = {_q(token)}

[service]
poll_interval_s = 1.0

[network]
discovery_cidrs = [{", ".join(_q(item) for item in discovery_cidrs)}]
discovery_max_hosts = {int(network.get("discovery_max_hosts", 1024))}
discovery_workers = {int(network.get("discovery_workers", 16))}

[[targets]]
device_id = {_q(device_id)}
device_key = {_q(device_key)}
hostname = {_q(hostname)}
os_family = {_q(os_family)}
address_hints = [{", ".join(_q(item) for item in addresses)}]

[targets.wol]
enabled = {str(wol_enabled).lower()}
mac = {_q(str(wol.get("mac", "")))}
broadcast_address = {_q(str(wol.get("broadcast_address", "")))}
port = {int(wol.get("port", 9))}

[targets.ssh_bootstrap]
enabled = {str(ssh_enabled).lower()}
host_alias = {_q(str(ssh.get("host_alias", "")))}
platform = {_q(str(ssh.get("platform", "LINUX_SYSTEMD")))}
"""

    fetcher_text = f"""[identity]
device_id = {_q(device_id)}

[drive]
root_id = {_q(root_id)}
client_secrets_path = {_q(client)}
token_path = {_q(token)}

[service]
ephemeral = {str(ephemeral).lower()}
idle_exit_s = {int(fetcher.get("idle_exit_s", 600))}
poll_interval_s = 1.0

[execution]
artifact_work_dir = {_q(_string(fetcher, "artifact_work_dir"))}
allow_inline_commands = true
"""

    # Parse our own output before returning it. Generation must never emit
    # syntactically invalid deployment configuration.
    tomllib.loads(watchdog_text)
    tomllib.loads(fetcher_text)
    return GeneratedConfigs(watchdog_text, fetcher_text)


def load_and_build(path: Path) -> GeneratedConfigs:
    try:
        data = tomllib.loads(path.expanduser().read_text(encoding="utf-8"))
    except OSError as exc:
        raise PilotConfigError("pilot configuration file is unavailable") from exc
    except tomllib.TOMLDecodeError as exc:
        raise PilotConfigError("pilot configuration is invalid TOML") from exc
    return build_configs(data)


def write_private_configs(
    generated: GeneratedConfigs,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    watchdog_path = output_dir / "watchdog.toml"
    fetcher_path = output_dir / "fetcher.toml"

    for path, text in (
        (watchdog_path, generated.watchdog),
        (fetcher_path, generated.fetcher),
    ):
        path.write_text(text, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return watchdog_path, fetcher_path
