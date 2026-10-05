"""Immutable protected connection facts; no key/transport use or runtime grant."""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import re
import secrets
import sys

from tb4.commissioning_state import Setup, storage_spec
from tb4.credential_contract import Purpose, identity
from tb4.credential_persistence import validate_image
from tb4.private_settings import PrivateSettings, encoded
from tb4.private_settings_linux import LinuxSettingsNative
from tb4.private_settings_windows import WindowsSettingsNative
from tb4.reconfiguration_candidate import native_binding
from tb4.reconfiguration_maintenance import sha
from .commissioning import digest
from .docs_authority import require
from .folder_authority import FolderBinding
from .folder_probe_transport import ProbeEndpoint

FIELDS = frozenset({"schema_version", "kind", "reference", "installation_id",
    "authority", "blueprint_sha256", "authority_handle_sha256", "credential_handle",
    "endpoint", "store_binding"})
ENDPOINT_FIELDS = frozenset({"target_id", "trust", "executable", "host", "port",
    "user", "known_hosts", "known_version", "timeout"})


def _text(value, pattern):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def _native(store):
    expected = WindowsSettingsNative if sys.platform == "win32" else (
        LinuxSettingsNative if sys.platform.startswith("linux") else None)
    return type(store) is PrivateSettings and expected is not None and type(store.native) is expected


def _shape(value):
    require(type(value) is dict and set(value) == FIELDS
        and type(value["schema_version"]) is int and value["schema_version"] == 1
        and value["kind"] == "NATIVE_FOLDER_ENDPOINT"
        and _text(value["reference"], r"fe_[0-9a-f]{32}")
        and identity(value["installation_id"]), "FOLDER_ENDPOINT_FRAME")
    require(type(value["authority"]) is dict
        and set(value["authority"]) == {"root_id", "domain_id"}, "FOLDER_ENDPOINT_FRAME")
    FolderBinding(**value["authority"])
    require(all(_text(value[k], r"[0-9a-f]{64}") for k in (
        "blueprint_sha256", "authority_handle_sha256", "store_binding"))
        and _text(value["credential_handle"], r"cr_[0-9a-f]{32}"), "FOLDER_ENDPOINT_FRAME")
    require(type(value["endpoint"]) is dict and set(value["endpoint"]) == ENDPOINT_FIELDS,
        "FOLDER_ENDPOINT_FRAME")
    ProbeEndpoint(**value["endpoint"])
    require(len(encoded(value)) <= 32 * 1024, "FOLDER_ENDPOINT_SIZE")
    return copy.deepcopy(value)


@dataclass(frozen=True, repr=False)
class EndpointSelection:
    """Private facts for trusted composition, never a public credential report."""
    reference: str
    endpoint: ProbeEndpoint
    credential_handle: str
    binding: FolderBinding


class NativeFolderEndpoint:
    """One immutable actual native frame at an explicitly selected private root."""
    def __init__(self, store, installation_id):
        require(_native(store) and identity(installation_id), "FOLDER_ENDPOINT_STORE")
        self.store, self.installation_id = store, installation_id
        self._pins = (store, store.native, installation_id)
        self._binding = native_binding(store)

    def _current(self):
        require(self.store is self._pins[0] and self.store.native is self._pins[1]
            and self.installation_id == self._pins[2] and _native(self.store),
            "FOLDER_ENDPOINT_CHANGED")
        require(native_binding(self.store) == self._binding, "FOLDER_ENDPOINT_CHANGED")

    def _frame(self, snapshot):
        require(snapshot.revision == 1 and snapshot.previous is None, "FOLDER_ENDPOINT_IMMUTABLE")
        value = _shape(snapshot.payload)
        require(value["installation_id"] == self.installation_id
            and value["store_binding"] == self._binding, "FOLDER_ENDPOINT_BINDING")
        return value

    def _read(self):
        self._current()
        snapshot = self.store.read()
        value = None if snapshot is None else self._frame(snapshot)
        self._current()
        return value

    def _profile(self, setup, credential_handle):
        require(type(setup) is Setup and _native(setup.store)
            and setup.installation_id == self.installation_id
            and setup.store is not self.store, "FOLDER_ENDPOINT_PROFILE")
        require(native_binding(setup.store) != self._binding, "FOLDER_ENDPOINT_STORE_ALIAS")
        setup._fresh()
        spec, handle = storage_spec(setup.private_choices()["storage"])
        require(spec.mode == "FOLDER_SQLITE_V1", "FOLDER_ENDPOINT_MODE")
        binding = FolderBinding(spec.root_id, spec.domain_id)
        matches = [c for c in setup.private_choices()["credentials"]
            if c["handle"] == credential_handle]
        require(len(matches) == 1 and ({Purpose.FOLDER_PROBE.value, Purpose.FOLDER_AUTHORITY.value}
            & set(matches[0]["purposes"])), "FOLDER_ENDPOINT_CREDENTIAL")
        image = setup._payload.get("credential_image")
        require(image is not None, "FOLDER_ENDPOINT_CREDENTIAL")
        image = validate_image(image, self.installation_id)
        saved = image["bindings"][credential_handle]
        require(not saved["revoked"]
            and not image["selections"][saved["store_locator"]]["revoked"],
            "FOLDER_ENDPOINT_CREDENTIAL")
        return dict(authority=asdict(binding), blueprint_sha256=spec.fingerprint,
            authority_handle_sha256=digest(handle.record()), credential_handle=credential_handle,
            target_id=matches[0]["target_id"], target_trust=matches[0]["target_trust"])

    def _verify(self, value, setup, reference):
        require(_text(reference, r"fe_[0-9a-f]{32}") and value["reference"] == reference,
            "FOLDER_ENDPOINT_REFERENCE")
        facts = self._profile(setup, value["credential_handle"])
        require(all(value[k] == facts[k] for k in ("authority", "blueprint_sha256",
            "authority_handle_sha256", "credential_handle"))
            and value["endpoint"]["target_id"] == facts["target_id"]
            and value["endpoint"]["trust"] == facts["target_trust"], "FOLDER_ENDPOINT_PROFILE")
        return facts

    def prepare(self, setup, endpoint, credential_handle, *, owner_authorized=False):
        require(owner_authorized is True, "FOLDER_ENDPOINT_OWNER_REQUIRED")
        require(type(endpoint) is ProbeEndpoint, "FOLDER_ENDPOINT_INPUT")
        require(self._read() is None, "FOLDER_ENDPOINT_EXISTS")
        facts = self._profile(setup, credential_handle)
        require(endpoint.target_id == facts["target_id"] and endpoint.trust == facts["target_trust"],
            "FOLDER_ENDPOINT_TARGET")
        value = _shape(dict(schema_version=1, kind="NATIVE_FOLDER_ENDPOINT",
            reference="fe_" + secrets.token_hex(16), installation_id=self.installation_id,
            **{k: facts[k] for k in ("authority", "blueprint_sha256",
                "authority_handle_sha256", "credential_handle")},
            endpoint=asdict(endpoint), store_binding=self._binding))
        require(self._profile(setup, credential_handle) == facts, "FOLDER_ENDPOINT_CHANGED")
        self._current()
        self.store.save(value, expected_revision=0)
        require(self._read() == value and self._verify(value, setup, value["reference"]) == facts,
            "FOLDER_ENDPOINT_UNCONFIRMED")
        return value["reference"]

    def lookup(self, setup, reference):
        value = self._read()
        require(value is not None, "FOLDER_ENDPOINT_UNAVAILABLE")
        facts = self._verify(value, setup, reference)
        require(self._read() == value and self._verify(value, setup, reference) == facts,
            "FOLDER_ENDPOINT_CHANGED")
        return EndpointSelection(reference, ProbeEndpoint(**value["endpoint"]),
            value["credential_handle"], FolderBinding(**value["authority"]))

    def inspect(self):
        """Only closed status/opaque reference; no endpoint or credential readiness."""
        self._current()
        with self.store.native.locked() as port:
            require(sha(port.binding) == self._binding, "FOLDER_ENDPOINT_CHANGED")
            raw, pending = port.read("settings.json"), port.read("settings.pending")
            require(raw is None or pending is None, "FOLDER_ENDPOINT_RECOVERY_CONFLICT")
            if raw is None and pending is None:
                state, reference = "EMPTY", None
            else:
                value = self._frame(self.store._decode(pending if pending is not None else raw, port.binding))
                state, reference = ("PENDING" if pending is not None else "SELECTED"), value["reference"]
        self._current()
        return dict(status=state, reference=reference, metadata_only=True, credential_ready=False)

    def recover(self, setup, reference, *, owner_authorized=False):
        """Promote only the same native pending record; no reconstruction or reselection."""
        require(owner_authorized is True, "FOLDER_ENDPOINT_OWNER_REQUIRED")
        self._current()
        with self.store.native.locked() as port:
            require(sha(port.binding) == self._binding, "FOLDER_ENDPOINT_CHANGED")
            raw, pending = port.read("settings.json"), port.read("settings.pending")
            require(raw is None or pending is None, "FOLDER_ENDPOINT_RECOVERY_CONFLICT")
            require(raw is not None or pending is not None, "FOLDER_ENDPOINT_UNAVAILABLE")
            value = self._frame(self.store._decode(pending if pending is not None else raw, port.binding))
            self._verify(value, setup, reference)
            if pending is not None:
                port.promote()
                require(port.read("settings.json") == pending, "FOLDER_ENDPOINT_UNCONFIRMED")
        require(self._read() == value, "FOLDER_ENDPOINT_UNCONFIRMED")
        self.lookup(setup, reference)
        return "ENDPOINT_SELECTED"
