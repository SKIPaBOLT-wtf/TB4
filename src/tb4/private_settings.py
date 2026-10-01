"""Protected, revision-checked R2 settings. Payloads are private, never reports."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import hashlib
import json
import sys

MAX_BYTES = 1024 * 1024


class SettingsError(ValueError):
    """Closed diagnostic only; no source paths, identities or payload repr."""


def require(condition, code="SETTINGS_INVALID"):
    if not condition:
        raise SettingsError(code)


def encoded(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
        require(len(raw) <= MAX_BYTES, "SETTINGS_TOO_LARGE")
        return raw
    except SettingsError:
        raise
    except Exception:
        raise SettingsError("SETTINGS_INVALID") from None


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "SETTINGS_DUPLICATE_KEY")
        value[key] = item
    return value


@dataclass(frozen=True, repr=False)
class Snapshot:
    revision: int
    payload: dict = field(repr=False)
    previous: dict | None = field(repr=False)


class PrivateSettings:
    """Own one native lock for each transaction; never accept a public lock flag.

    Native ports are trusted program objects, not deserialized configuration.
    The first-run model validates its closed payload schema before calling save.
    A missing current file with pending data cannot mint another identity.
    """
    def __init__(self, native):
        self.native = native

    def _decode(self, raw, binding):
        try:
            require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES)
            frame = json.loads(raw, object_pairs_hook=unique,
                               parse_constant=lambda _: require(False))
            require(type(frame) is dict and set(frame) == {
                "schema_version", "binding", "revision", "payload", "previous", "digest"})
            require(type(frame["schema_version"]) is int and frame["schema_version"] == 1)
            require(frame["binding"] == binding, "SETTINGS_IDENTITY_MISMATCH")
            require(type(frame["revision"]) is int and 1 <= frame["revision"] <= 2**63 - 1)
            require(type(frame["payload"]) is dict and
                    (frame["previous"] is None or type(frame["previous"]) is dict))
            digest = frame.pop("digest")
            require(type(digest) is str and hashlib.sha256(encoded(frame)).hexdigest() == digest,
                    "SETTINGS_DIGEST_MISMATCH")
            return Snapshot(frame["revision"], frame["payload"], frame["previous"])
        except SettingsError:
            raise
        except Exception:
            raise SettingsError("SETTINGS_UNREADABLE") from None

    def read(self):
        try:
            with self.native.locked() as port:
                raw = port.read("settings.json")
                if raw is None:
                    require(port.read("settings.pending") is None, "SETTINGS_RECOVERY_REQUIRED")
                    return None
                return self._decode(raw, port.binding)
        except SettingsError:
            raise
        except Exception:
            raise SettingsError("SETTINGS_UNAVAILABLE") from None

    def save(self, payload, *, expected_revision):
        require(type(payload) is dict and type(expected_revision) is int and expected_revision >= 0)
        try:
            payload = copy.deepcopy(payload)
            with self.native.locked() as port:
                before = port.read("settings.json")
                current = None if before is None else self._decode(before, port.binding)
                require((current.revision if current else 0) == expected_revision,
                        "SETTINGS_CHANGED_RELOAD_REQUIRED")
                require(port.read("settings.pending") is None, "SETTINGS_RECOVERY_REQUIRED")
                frame = dict(schema_version=1, binding=port.binding,
                             revision=expected_revision + 1, payload=payload,
                             previous=None if current is None else current.payload)
                frame["digest"] = hashlib.sha256(encoded(frame)).hexdigest()
                raw = encoded(frame)
                # Native exclusive-create prevents an unknown staging write being
                # overwritten. Flush before atomic promotion, then exact readback.
                port.stage(raw)
                port.promote()
                require(port.read("settings.json") == raw, "SETTINGS_READBACK_UNCONFIRMED")
                return self._decode(raw, port.binding)
        except SettingsError:
            raise
        except Exception:
            raise SettingsError("SETTINGS_COMMIT_UNCONFIRMED") from None

    def recover_pending(self):
        """Inspect the same complete candidate; never reconstruct a lost payload."""
        try:
            with self.native.locked() as port:
                pending = port.read("settings.pending")
                current_raw = port.read("settings.json")
                current = None if current_raw is None else self._decode(current_raw, port.binding)
                if pending is None:
                    return current
                candidate = self._decode(pending, port.binding)
                require(candidate.revision == (current.revision if current else 0) + 1
                        and candidate.previous == (current.payload if current else None),
                        "SETTINGS_RECOVERY_CONFLICT")
                port.promote()
                require(port.read("settings.json") == pending, "SETTINGS_READBACK_UNCONFIRMED")
                return candidate
        except SettingsError:
            raise
        except Exception:
            raise SettingsError("SETTINGS_RECOVERY_REQUIRED") from None


def native_settings(root, *, create=False, owner_authorized=False):
    """Explicit selected root; existing directories are verified, never repaired."""
    require(type(create) is bool and type(owner_authorized) is bool)
    require(not create or owner_authorized, "SETTINGS_CREATION_NOT_AUTHORIZED")
    try:
        if sys.platform == "win32":
            from .private_settings_windows import WindowsSettingsNative
            native = WindowsSettingsNative(root, create=create)
        elif sys.platform.startswith("linux"):
            from .private_settings_linux import LinuxSettingsNative
            native = LinuxSettingsNative(root, create=create)
        else:
            raise SettingsError("SETTINGS_PLATFORM_UNSUPPORTED")
        return PrivateSettings(native)
    except SettingsError:
        raise
    except Exception:
        raise SettingsError("SETTINGS_STORE_UNAVAILABLE") from None
