"""Native metadata-only endpoint pointer link; no credential, RPC or role grant."""
from __future__ import annotations

import copy
from contextlib import contextmanager
from pathlib import Path

from tb4.commissioning_state import Setup, validated
from tb4.reconfiguration_candidate import native_binding
from tb4.reconfiguration_maintenance import sha
from .docs_authority import require
from .folder_endpoint import NativeFolderEndpoint, _native, _text
from .folder_endpoint_selection import selection


class NativeFolderEndpointAttachment:
    def __init__(self, endpoint, profile):
        require(type(endpoint) is NativeFolderEndpoint and _native(profile),
                "FOLDER_ENDPOINT_ATTACHMENT_STORE")
        require(profile is not endpoint.store, "FOLDER_ENDPOINT_ATTACHMENT_ALIAS")
        self.endpoint, self.profile = endpoint, profile
        self._pins = (endpoint, endpoint.store, endpoint.store.native, profile, profile.native)
        self._binding = native_binding(profile)
        require(self._binding != endpoint._binding, "FOLDER_ENDPOINT_ATTACHMENT_ALIAS")
        self._current()

    def _current(self):
        require((self.endpoint, self.endpoint.store, self.endpoint.store.native,
                 self.profile, self.profile.native) == self._pins and _native(self.profile),
                "FOLDER_ENDPOINT_ATTACHMENT_CHANGED")
        self.endpoint._current()
        require(native_binding(self.profile) == self._binding, "FOLDER_ENDPOINT_ATTACHMENT_CHANGED")

    def _pointer(self, reference):
        require(_text(reference, r"fe_[0-9a-f]{32}"), "FOLDER_ENDPOINT_REFERENCE")
        return selection(dict(schema_version=1, reference=reference,
            root=str(Path(self.endpoint.store.native.root)), binding_digest=self.endpoint._binding))

    def _facts(self, payload, value, pointer):
        payload = validated(payload)
        require(value["reference"] == pointer["reference"], "FOLDER_ENDPOINT_REFERENCE")
        facts = self.endpoint._profile_payload(payload, value["credential_handle"])
        require(all(value[k] == facts[k] for k in ("authority", "blueprint_sha256",
            "authority_handle_sha256", "credential_handle"))
            and value["endpoint"]["target_id"] == facts["target_id"]
            and value["endpoint"]["trust"] == facts["target_trust"], "FOLDER_ENDPOINT_PROFILE")
        return payload

    def _desired(self, payload, pointer):
        require(payload.get("folder_endpoint") is None, "FOLDER_ENDPOINT_ATTACHMENT_CONFLICT")
        require(payload["state"] == "INCOMPLETE", "FOLDER_ENDPOINT_ATTACHMENT_STATE")
        require("UNKNOWN" not in payload["operations"].values(), "FOLDER_ENDPOINT_ATTACHMENT_UNKNOWN")
        value = copy.deepcopy(payload)
        value["folder_endpoint"] = copy.deepcopy(pointer)
        return validated(value)

    def _candidate(self, current, pending, port, value, pointer):
        candidate = self.profile._decode(pending, port.binding)
        require(candidate.revision == current.revision + 1 and candidate.previous == current.payload,
                "FOLDER_ENDPOINT_ATTACHMENT_RECOVERY_CONFLICT")
        require(candidate.payload == self._desired(current.payload, pointer),
                "FOLDER_ENDPOINT_ATTACHMENT_RECOVERY_CONFLICT")
        self._facts(candidate.payload, value, pointer)
        return candidate

    @contextmanager
    def _pair(self, reference):
        self._current()
        pointer = self._pointer(reference)
        # This matches the existing endpoint recovery order. Never nest an
        # endpoint lookup that would acquire these same native locks again.
        with self.endpoint.store.native.locked() as endpoint_port:
            require(sha(endpoint_port.binding) == self.endpoint._binding,
                    "FOLDER_ENDPOINT_ATTACHMENT_CHANGED")
            raw = endpoint_port.read("settings.json")
            require(raw is not None and endpoint_port.read("settings.pending") is None,
                    "FOLDER_ENDPOINT_UNAVAILABLE")
            value = self.endpoint._frame(self.endpoint.store._decode(raw, endpoint_port.binding))
            with self.profile.native.locked() as port:
                require(sha(port.binding) == self._binding, "FOLDER_ENDPOINT_ATTACHMENT_CHANGED")
                profile_raw, pending = port.read("settings.json"), port.read("settings.pending")
                require(profile_raw is not None, "FOLDER_ENDPOINT_ATTACHMENT_PROFILE")
                current = self.profile._decode(profile_raw, port.binding)
                self._facts(current.payload, value, pointer)
                yield port, current, pending, value, pointer
                require(endpoint_port.read("settings.json") == raw
                    and endpoint_port.read("settings.pending") is None,
                    "FOLDER_ENDPOINT_ATTACHMENT_CHANGED")
        self._current()

    @staticmethod
    def _report(state, reference):
        return dict(status=state, reference=reference, metadata_only=True,
                    credential_ready=False, runtime_active=False, automatic_replay=False)

    def attach(self, setup, reference, *, owner_authorized=False):
        require(owner_authorized is True, "FOLDER_ENDPOINT_OWNER_REQUIRED")
        require(type(setup) is Setup and setup.store is self.profile, "FOLDER_ENDPOINT_ATTACHMENT_PROFILE")
        setup._fresh()
        with self._pair(reference) as (port, current, pending, value, pointer):
            require(pending is None, "FOLDER_ENDPOINT_ATTACHMENT_PENDING")
            require(current.revision == setup.snapshot.revision and current.payload == setup._payload,
                    "FOLDER_ENDPOINT_ATTACHMENT_CHANGED")
            if current.payload.get("folder_endpoint") == pointer:
                snapshot = current  # Same link needs no reset, even during UNKNOWN.
            else:
                desired = self._desired(current.payload, pointer)
                snapshot = self.profile._save_locked(port, desired, expected_revision=current.revision)
                require(snapshot.payload == desired and snapshot.previous == current.payload,
                        "FOLDER_ENDPOINT_ATTACHMENT_UNCONFIRMED")
                self._facts(snapshot.payload, value, pointer)
        if snapshot.revision != setup.snapshot.revision:
            setup._validation = setup._ready_revision = None
            setup.snapshot, setup._payload = snapshot, validated(snapshot.payload)
        setup._fresh()
        return self._report("ATTACHED", reference)

    def inspect(self, reference):
        with self._pair(reference) as (port, current, pending, value, pointer):
            if pending is not None:
                self._candidate(current, pending, port, value, pointer)
                state = "PENDING"
            else:
                require(current.payload.get("folder_endpoint") in (None, pointer),
                        "FOLDER_ENDPOINT_ATTACHMENT_CONFLICT")
                state = "ATTACHED" if current.payload.get("folder_endpoint") == pointer else "UNSELECTED"
        return self._report(state, reference)

    def recover(self, reference, *, owner_authorized=False):
        require(owner_authorized is True, "FOLDER_ENDPOINT_OWNER_REQUIRED")
        with self._pair(reference) as (port, current, pending, value, pointer):
            if pending is not None:
                self._candidate(current, pending, port, value, pointer)
                port.promote()
                require(port.read("settings.json") == pending,
                        "FOLDER_ENDPOINT_ATTACHMENT_UNCONFIRMED")
            else:
                require(current.payload.get("folder_endpoint") == pointer,
                        "FOLDER_ENDPOINT_ATTACHMENT_NOT_STARTED")
        require(self.inspect(reference)["status"] == "ATTACHED", "FOLDER_ENDPOINT_ATTACHMENT_UNCONFIRMED")
        return self._report("ATTACHED", reference)

