"""Fresh protected Folder selection for one existing fixed credential operation.

No selection, enrollment, profile write, activation or automatic retry occurs here.
Native locks cover the current selected image through its one correlated reply.
"""
from __future__ import annotations

import copy
from dataclasses import asdict
from pathlib import Path

from tb4.commissioning_state import storage_spec, validated
from tb4.credential_contract import Purpose
from tb4.credential_persistence import restore_private
from tb4.private_settings import encoded, native_settings
from .docs_authority import AuthorityError, require
from .folder_authority import FolderBinding
from .folder_authority_transport import CredentialAuthorityProcess, credential_authority_pair, _request
from .folder_endpoint import NativeFolderEndpoint, _native
from .folder_endpoint_attachment import NativeFolderEndpointAttachment
from .folder_endpoint_selection import selection
from .folder_probe import FolderProbe
from .folder_probe_transport import (
    ProbeEndpoint, CredentialProbeProcess, credential_probe_pair, probe_request)
from .folder_protocol import FolderAuthority


class NativeFolderConnection:
    def __init__(self, profile, *, clock):
        require(_native(profile) and callable(clock), "FOLDER_CONNECTION_PROFILE")
        snapshot = profile.read()
        require(snapshot is not None, "FOLDER_CONNECTION_PROFILE")
        payload = validated(snapshot.payload)
        pointer = selection(payload.get("folder_endpoint"))
        require(pointer is not None, "FOLDER_CONNECTION_SELECTION")
        metadata = NativeFolderEndpoint(native_settings(Path(pointer["root"])), payload["installation_id"])
        link = NativeFolderEndpointAttachment(metadata, profile)
        with link._pair(pointer["reference"]) as (port, current, pending, value, actual):
            require(pending is None and current.payload.get("folder_endpoint") == pointer == actual,
                    "FOLDER_CONNECTION_SELECTION")
            self.spec, self.authority = storage_spec(current.payload["choices"]["storage"])
            self.binding = FolderBinding(**value["authority"])
            self.endpoint = ProbeEndpoint(**value["endpoint"])
            self.handle = value["credential_handle"]
            self._value = copy.deepcopy(value)
        self.profile, self.metadata, self._link, self._clock = profile, metadata, link, clock
        self._pointer = copy.deepcopy(pointer)
        self._pins = (profile, profile.native, metadata, metadata.store, metadata.store.native, link, clock)
        self._facts_pin = encoded(dict(pointer=pointer, spec=asdict(self.spec),
            authority=self.authority.record(), binding=asdict(self.binding),
            endpoint=asdict(self.endpoint), handle=self.handle, metadata=self._value))
        self._current()

    def _current(self):
        # Pure object/value pins only. No filesystem, profile, key or resolver IO
        # may precede a process caller's closed request validation.
        require(type(self) is NativeFolderConnection
            and (self.profile, self.profile.native, self.metadata, self.metadata.store,
                 self.metadata.store.native, self._link, self._clock) == self._pins
            and self._link.profile is self.profile and self._link.endpoint is self.metadata,
                "FOLDER_CONNECTION_CHANGED")
        require(encoded(dict(pointer=self._pointer, spec=asdict(self.spec),
            authority=self.authority.record(), binding=asdict(self.binding),
            endpoint=asdict(self.endpoint), handle=self.handle, metadata=self._value)) == self._facts_pin,
                "FOLDER_CONNECTION_CHANGED")

    def _selected(self, payload, value, pointer, purpose):
        require(payload.get("folder_endpoint") == pointer == self._pointer
            and value == self._value, "FOLDER_CONNECTION_SELECTION")
        spec, authority = storage_spec(payload["choices"]["storage"])
        require(spec == self.spec and authority == self.authority, "FOLDER_CONNECTION_SELECTION")
        selected = [record for record in payload["choices"]["credentials"]
                    if record["handle"] == self.handle]
        require(len(selected) == 1 and purpose.value in selected[0]["purposes"],
                "FOLDER_CONNECTION_PURPOSE")

    def _use(self, purpose, raw):
        try:
            self._current()
            if purpose is Purpose.FOLDER_PROBE:
                probe_request(self.binding, self.spec, self.authority, raw)
            else:
                require(purpose is Purpose.FOLDER_AUTHORITY, "FOLDER_CONNECTION_PURPOSE")
                _request(self.binding, raw)
            with self._link._pair(self._pointer["reference"]) as (port, current, pending, value, pointer):
                require(pending is None, "FOLDER_CONNECTION_PENDING")
                self._selected(current.payload, value, pointer, purpose)
                before = port.read("settings.json")
                require(self.profile._decode(before, port.binding) == current,
                        "FOLDER_CONNECTION_CHANGED")
                installation = current.payload["installation_id"]
                if purpose is Purpose.FOLDER_PROBE:
                    store, resolver = credential_probe_pair(installation, self.endpoint,
                        self.spec, self.authority, clock=self._clock)
                    process_type = CredentialProbeProcess
                else:
                    store, resolver = credential_authority_pair(installation, self.endpoint,
                        self.binding, clock=self._clock)
                    process_type = CredentialAuthorityProcess
                # Only this freshly read actual protected image is restored.
                # Existing native factories still recheck key/trust/scope/expiry.
                restore_private(current.payload["credential_image"], store, resolver)
                reply = process_type(resolver, self.handle).call(raw)
                require(port.read("settings.json") == before and port.read("settings.pending") is None,
                        "FOLDER_CONNECTION_CHANGED")
                self._current()
            return reply
        except Exception:
            # A reply or effect may have been lost. Never reconstruct or resend.
            raise AuthorityError("HELPER_UNAVAILABLE") from None

    def probe(self, access):
        return FolderProbe(NativeFolderProbeProcess(self), self.spec, self.authority, access)

    def authority_client(self, access):
        return FolderAuthority(NativeFolderAuthorityProcess(self), self.binding, access)


class NativeFolderProbeProcess:
    def __init__(self, connection):
        require(type(connection) is NativeFolderConnection, "FOLDER_CONNECTION_PROCESS")
        connection._current()
        self._connection = connection
        self.binding, self.spec, self.authority = connection.binding, connection.spec, connection.authority
        self._pin = (connection, self.binding, self.spec, self.authority)

    def _current(self):
        require(type(self) is NativeFolderProbeProcess
            and (self._connection, self.binding, self.spec, self.authority) == self._pin
            and self.binding == self._connection.binding and self.spec == self._connection.spec
            and self.authority == self._connection.authority, "FOLDER_CONNECTION_PROCESS")
        self._connection._current()

    def call(self, raw):
        self._current()
        return self._connection._use(Purpose.FOLDER_PROBE, raw)


class NativeFolderAuthorityProcess:
    def __init__(self, connection):
        require(type(connection) is NativeFolderConnection, "FOLDER_CONNECTION_PROCESS")
        connection._current()
        self._connection, self.binding = connection, connection.binding
        self._pin = (connection, self.binding)

    def _current(self):
        require(type(self) is NativeFolderAuthorityProcess
            and (self._connection, self.binding) == self._pin
            and self.binding == self._connection.binding, "FOLDER_CONNECTION_PROCESS")
        self._connection._current()

    def call(self, raw):
        self._current()
        return self._connection._use(Purpose.FOLDER_AUTHORITY, raw)

