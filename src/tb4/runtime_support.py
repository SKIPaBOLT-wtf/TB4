from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from tb4.core.retry import RetryPolicy
from tb4.drive.backend import DriveBackend
from tb4.drive.google_backend import GoogleDriveBackend
from tb4.drive.google_client import GoogleAuthConfig, build_google_drive_client
from tb4.drive.park_map import ParkMap


class RuntimeConfigurationError(ValueError):
    pass


class RuntimeStartupError(RuntimeError):
    pass


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_toml(path: Path) -> dict[str, Any]:
    try:
        data = tomllib.loads(path.expanduser().read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeConfigurationError("runtime configuration file is unavailable") from exc
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeConfigurationError("runtime configuration is invalid TOML") from exc
    if not isinstance(data, dict):
        raise RuntimeConfigurationError("runtime configuration must be a TOML table")
    return data


def load_public_defaults() -> dict[str, Any]:
    return load_toml(repository_root() / "config" / "defaults.toml")


def require_table(config: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = config.get(key)
    if not isinstance(value, Mapping):
        raise RuntimeConfigurationError(f"missing [{key}] configuration table")
    return value


def require_string(table: Mapping[str, Any], key: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeConfigurationError(f"missing required configuration field {key!r}")
    return value.strip()


def optional_bool(table: Mapping[str, Any], key: str, default: bool) -> bool:
    value = table.get(key, default)
    if not isinstance(value, bool):
        raise RuntimeConfigurationError(f"configuration field {key!r} must be boolean")
    return value


def build_google_backend(config: Mapping[str, Any]) -> GoogleDriveBackend:
    drive = require_table(config, "drive")
    client_path = Path(require_string(drive, "client_secrets_path")).expanduser()
    token_path = Path(require_string(drive, "token_path")).expanduser()
    auth = GoogleAuthConfig(
        client_path,
        token_path,
        allow_interactive=False,
        open_browser=False,
    )
    report = build_google_drive_client(auth)
    if not report.ready:
        raise RuntimeStartupError(
            f"Google Drive authorization is not ready: {report.outcome.value}: "
            f"{report.message or ''}".rstrip()
        )
    return GoogleDriveBackend(report.service)


def discover_park_map(backend: DriveBackend, root_id: str) -> ParkMap:
    """Bootstrap-only PARK_MAP discovery.

    This is intentionally the only runtime-support directory scan. The returned
    PARK_MAP becomes the exact-ID routing table for normal role operation.
    """

    root = backend.get_metadata(root_id)
    if not root.ok or root.value is None:
        raise RuntimeStartupError("configured TB4 root is not reachable")
    if not root.value.is_folder:
        raise RuntimeStartupError("configured TB4 root is not a folder")

    listing = backend.list_children(root_id)
    if not listing.ok or listing.value is None:
        raise RuntimeStartupError("configured TB4 root cannot be enumerated during startup")
    matches = [item for item in listing.value if item.name == "PARK_MAP" and not item.is_folder]
    if len(matches) != 1:
        raise RuntimeStartupError(
            f"startup requires exactly one PARK_MAP under the configured root; observed {len(matches)}"
        )

    body = backend.read_text(matches[0].object_id)
    if not body.ok or body.value is None:
        raise RuntimeStartupError("PARK_MAP cannot be read")
    try:
        parsed = json.loads(body.value.text)
        park_map = ParkMap.from_dict(parsed)
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeStartupError("PARK_MAP is invalid") from exc

    if park_map.root_id != root_id:
        raise RuntimeStartupError("PARK_MAP root_id does not match configured root")
    if park_map.lookup("PARK_MAP") != matches[0].object_id:
        raise RuntimeStartupError("PARK_MAP does not point to its own canonical object ID")
    return park_map


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    config: Mapping[str, Any]
    defaults: Mapping[str, Any]
    backend: DriveBackend
    park_map: ParkMap
    retry_policy: RetryPolicy


def build_context(
    config_path: Path,
    *,
    backend: DriveBackend | None = None,
) -> RuntimeContext:
    config = load_toml(config_path)
    drive = require_table(config, "drive")
    root_id = require_string(drive, "root_id")
    selected = backend if backend is not None else build_google_backend(config)
    defaults = load_public_defaults()
    park_map = discover_park_map(selected, root_id)
    return RuntimeContext(
        config=config,
        defaults=defaults,
        backend=selected,
        park_map=park_map,
        retry_policy=RetryPolicy.from_config(defaults),
    )
