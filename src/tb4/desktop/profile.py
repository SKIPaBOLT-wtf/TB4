from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import tempfile
import tomllib
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

ROLES = ("watchdog", "fetcher")
MAX_CONFIG_BYTES = 256 * 1024


class ProfileError(ValueError):
    """A safe, actionable error code, never a copy of private configuration."""


class ProfileBusy(ProfileError):
    pass


def require_role(role: str) -> str:
    if role not in ROLES:
        raise ProfileError("ROLE_INVALID")
    return role


def drive_root_id(value: str) -> str:
    value = value.strip()
    if value.startswith("https://"):
        parsed = urlparse(value)
        if parsed.netloc != "drive.google.com" or parsed.username or parsed.password:
            raise ProfileError("DRIVE_FOLDER_URL_INVALID")
        match = re.fullmatch(r"/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]+)", parsed.path.rstrip("/"))
        if match is None:
            raise ProfileError("DRIVE_FOLDER_URL_INVALID")
        value = match[1]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value) or value == "replace-at-deploy-time":
        raise ProfileError("DRIVE_ROOT_ID_REQUIRED")
    return value


def content_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Profile:
    role: str
    directory: Path

    def __post_init__(self) -> None:
        require_role(self.role)
        if not self.directory.is_absolute():
            raise ProfileError("PROFILE_PATH_NOT_ABSOLUTE")

    @property
    def config(self) -> Path:
        return self.directory / "config.toml"

    @property
    def backup(self) -> Path:
        return self.directory / "config.previous.toml"

    @property
    def log(self) -> Path:
        return self.directory / "events.jsonl"

    def ensure(self) -> None:
        if self.directory.is_symlink():
            raise ProfileError("PROFILE_SYMLINK_REFUSED")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            self.directory.chmod(0o700)


def profile_for(role: str, base: Path | None = None) -> Profile:
    require_role(role)
    if base is None:
        if os.name == "nt":
            local = os.environ.get("LOCALAPPDATA")
            if not local:
                raise ProfileError("LOCALAPPDATA_UNAVAILABLE")
            base = Path(local) / "TB4"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "tb4"
    return Profile(role, base.expanduser().absolute() / role)


class ProfileLock(AbstractContextManager):
    """An OS-held lock; crashes release it. Never unlink a live lock inode."""

    def __init__(self, profile: Profile, name: str = "worker") -> None:
        if name not in {"worker", "gui", "config"}:
            raise ProfileError("LOCK_NAME_INVALID")
        self.profile = profile
        self.path = profile.directory / f"{name}.lock"
        self.file = None

    def __enter__(self):
        self.profile.ensure()
        if self.path.is_symlink():
            raise ProfileError("LOCK_SYMLINK_REFUSED")
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        self.file = os.fdopen(fd, "r+b", buffering=0)
        try:
            if os.fstat(fd).st_size == 0:
                self.file.write(b"\0")
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            self.file = None
            raise ProfileBusy("PROFILE_BUSY") from exc
        return self

    def __exit__(self, *args) -> None:
        if self.file is not None:
            try:
                self.file.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            finally:
                self.file.close()
                self.file = None


def read_config(path: Path) -> str:
    if path.is_symlink():
        raise ProfileError("CONFIG_SYMLINK_REFUSED")
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_CONFIG_BYTES + 1)
        if len(data) > MAX_CONFIG_BYTES:
            raise ProfileError("CONFIG_TOO_LARGE")
        return data.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ProfileError("CONFIG_UNREADABLE") from exc


def parse_config(role: str, text: str) -> dict:
    require_role(role)
    if len(text.encode("utf-8")) > MAX_CONFIG_BYTES:
        raise ProfileError("CONFIG_TOO_LARGE")
    try:
        config = tomllib.loads(text)
        drive = config["drive"]
        drive_root_id(drive["root_id"])
        # URLs can be pasted into the UI field, but runtime TOML contains an ID.
        if drive["root_id"] != drive_root_id(drive["root_id"]):
            raise ProfileError("CONFIG_ROOT_MUST_BE_ID")
        identity = config["watchdog" if role == "watchdog" else "identity"]["device_id"]
        if not isinstance(identity, str) or not identity.strip() or identity == "replace-at-deploy-time":
            raise ProfileError("DEVICE_ID_REQUIRED")
        for key in ("client_secrets_path", "token_path"):
            if not isinstance(drive[key], str) or not Path(drive[key]).expanduser().is_absolute():
                raise ProfileError("CREDENTIAL_PATH_NOT_ABSOLUTE")
        desktop = config.get("desktop", {})
        if not isinstance(desktop, dict) or not isinstance(desktop.get("start_role", False), bool):
            raise ProfileError("DESKTOP_SETTINGS_INVALID")
        mount = desktop.get("local_drive_folder", "")
        if not isinstance(mount, str) or (mount and not Path(mount).is_absolute()):
            raise ProfileError("LOCAL_DRIVE_FOLDER_NOT_ABSOLUTE")
    except (tomllib.TOMLDecodeError, KeyError, TypeError, AttributeError) as exc:
        raise ProfileError("CONFIG_STRUCTURE_INVALID") from exc
    return config


def canonical_validate(role: str, path: Path) -> None:
    module = importlib.import_module(f"tb4.{require_role(role)}.runtime")
    try:
        module.validate_config(path)
    except (ValueError, TypeError, KeyError) as exc:
        # Canonical validators can include input in errors. Export only the class.
        raise ProfileError(f"ROLE_CONFIG_INVALID:{type(exc).__name__.upper()}") from exc


def _atomic_write(path: Path, text: str) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=".config-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def save_config(
    profile: Profile,
    text: str,
    *,
    expected_digest: str | None,
    validator: Callable[[str, Path], None] = canonical_validate,
) -> str:
    """Validate first, reject concurrent edits, back up, then atomically replace."""
    parse_config(profile.role, text)
    profile.ensure()
    with ProfileLock(profile, "worker"), ProfileLock(profile, "config"):
        if profile.config.is_symlink():
            raise ProfileError("CONFIG_SYMLINK_REFUSED")
        current = read_config(profile.config) if profile.config.exists() else None
        actual = content_digest(current) if current is not None else None
        if actual != expected_digest:
            raise ProfileError("CONFIG_CHANGED_RELOAD_REQUIRED")
        fd, temp_name = tempfile.mkstemp(prefix=".validate-", suffix=".toml", dir=profile.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            validator(profile.role, Path(temp_name))
            if current is not None:
                if profile.backup.is_symlink():
                    raise ProfileError("BACKUP_SYMLINK_REFUSED")
                _atomic_write(profile.backup, current)
            os.replace(temp_name, profile.config)
        finally:
            Path(temp_name).unlink(missing_ok=True)
    return content_digest(text)


def default_config(profile: Profile) -> str:
    """An intentionally unconfigured template; never selects a private deployment."""
    quoted = lambda value: json.dumps(str(value), ensure_ascii=True)
    shared = ('[drive]\nroot_id = "replace-at-deploy-time"\n'
              'client_secrets_path = "replace-at-deploy-time"\n'
              f'token_path = {quoted(profile.directory / "token.json")}\n\n')
    if profile.role == "watchdog":
        text = ('[watchdog]\ndevice_id = "watchdog-host"\n\n' + shared +
                '[service]\npoll_interval_s = 1.0\n\n'
                '[[targets]]\ndevice_id = "target-a"\ndevice_key = "target-a"\n'
                f'os_family = "{"WINDOWS" if os.name == "nt" else "LINUX"}"\n'
                'address_hints = ["127.0.0.1"]\n\n'
                '# Local target template; enable remote capabilities deliberately.\n'
                '[targets.wol]\nenabled = false\n\n'
                '[targets.ssh_bootstrap]\nenabled = false\n\n')
    else:
        text = ('[identity]\ndevice_id = "target-a"\n\n' + shared +
                '[service]\nephemeral = false\nidle_exit_s = 600\npoll_interval_s = 1.0\n\n'
                '[execution]\n' + f'artifact_work_dir = {quoted(profile.directory / "artifacts")}\n\n')
    return text + ('[desktop]\nstart_role = false\n'
                   '# Optional local convenience; API remains authoritative.\nlocal_drive_folder = ""\n')
