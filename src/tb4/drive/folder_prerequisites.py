"""Trusted fresh native Folder composition of the existing first-run checks."""
from __future__ import annotations

from tb4.commissioning_checks import CommissionedStorage, Prerequisites
from tb4.commissioning_state import validated
from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.credential_persistence import restore_private
from tb4.private_settings import SettingsError, require
from .folder_connection import NativeFolderConnection
from .folder_first_run import RemoteFolderCommissioning
from .folder_probe_transport import credential_probe_pair


class NativeFolderFirstRun:
    def __init__(self, profile, *, access, environment, source, runtime, clock,
                 credential_factory=None):
        require(credential_factory is None or callable(credential_factory),
                "CREDENTIAL_UNAVAILABLE")
        connection = NativeFolderConnection(profile, clock=clock)
        self.connection = connection
        self._factory = credential_factory
        self.storage = CommissionedStorage(RemoteFolderCommissioning(connection.probe(access)))
        self.checker = Prerequisites(environment=environment, storage=self.storage,
            credentials=None, source=source, runtime=runtime, clock=clock, native_folder=self)
        self._pins = (connection, self.storage, self.storage.port, self.checker,
                      environment, source, runtime, clock, credential_factory)

    def _current(self):
        c = self.checker
        require(type(self) is NativeFolderFirstRun and type(c) is Prerequisites
            and c._native_folder is self and c._native_folder_required is True
            and c.storage is self.storage
            and (self.connection, self.storage, self.storage.port, c,
                 c.environment, c.source, c.runtime, c.clock, self._factory) == self._pins,
                "STORAGE_UNAVAILABLE")
        self.connection._current()

    def _capture(self, payload, expected=None):
        try:
            self._current()
            connection = self.connection
            with connection._link._pair(connection._pointer["reference"]) as (
                    port, current, pending, value, pointer):
                require(pending is None and current.payload == validated(payload),
                        "STORAGE_UNAVAILABLE")
                connection._selected(current.payload, value, pointer, Purpose.FOLDER_PROBE)
                raw = port.read("settings.json")
                require(connection.profile._decode(raw, port.binding) == current
                    and (expected is None or raw == expected), "STORAGE_UNAVAILABLE")
            self._current()
            return raw, current.payload
        except Exception:
            raise SettingsError("STORAGE_UNAVAILABLE") from None

    def _credentials(self, payload):
        try:
            connection = self.connection
            if self._factory is None:
                store, resolver = credential_probe_pair(payload["installation_id"],
                    connection.endpoint, connection.spec, connection.authority,
                    clock=self.checker.clock)
            else:
                # An installer-owned code factory, never selected by profile data.
                store, resolver = self._factory(payload["installation_id"])
            from tb4.linux_key_native import LinuxKeyNative
            from tb4.windows_key_native import WindowsKeyNative
            require(type(store._native) in {LinuxKeyNative, WindowsKeyNative}
                    and type(resolver) is CredentialResolver, "CREDENTIAL_UNAVAILABLE")
            restore_private(payload["credential_image"], store, resolver)
            return resolver
        except Exception:
            raise SettingsError("CREDENTIAL_UNAVAILABLE") from None

    @staticmethod
    def _capabilities(payload, resolver):
        try:
            for record in payload["choices"]["credentials"]:
                for purpose in record["purposes"]:
                    result = resolver.capability(record["handle"], purpose=Purpose(purpose),
                        target_id=record["target_id"], target_trust=record["target_trust"])
                    require(result.configured and result.available
                            and result.outcome is Outcome.READY, "CREDENTIAL_UNAVAILABLE")
        except Exception:
            raise SettingsError("CREDENTIAL_UNAVAILABLE") from None

    def validate(self, payload):
        self._current()
        # Old resolver availability must never survive a failed fresh attempt.
        self.checker.credentials = None
        raw, current = self._capture(payload)
        resolver = self._credentials(current)
        self.checker.credentials = resolver
        validation = self.checker._validate(current)
        self._current()
        require(self.checker.credentials is resolver, "CREDENTIAL_UNAVAILABLE")
        self._capture(current, raw)
        fresh = self._credentials(current)
        self._capabilities(current, fresh)
        self._capture(current, raw)
        self.checker.credentials = fresh
        return validation


def native_folder_prerequisites(profile, *, access, environment, source, runtime,
                                clock, credential_factory=None):
    """Return the exact existing checker; saved metadata grants no readiness."""
    return NativeFolderFirstRun(profile, access=access, environment=environment,
        source=source, runtime=runtime, clock=clock,
        credential_factory=credential_factory).checker
