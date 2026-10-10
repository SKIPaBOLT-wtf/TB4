"""Trusted first-run probes; selected adapters only, no discovery or auto-repair."""
from dataclasses import dataclass
import os
import platform
import sys

from .ballpark import catalogue, llm_projection, validate as validate_ballpark
from .commissioning_state import Validation, storage_spec
from .credential_contract import CredentialResolver, Outcome, Purpose
from .drive.commissioning import verify_allocated_bindings
from .exchange_layout import validate_document
from .instructions import select, check_boundary
from .private_settings import SettingsError, require
from .timing_contract import TimingProfile


@dataclass(frozen=True)
class Environment:
    os: str
    architecture: str
    privilege: str
    launch_mode: str
    session: str


def detect_environment(*, launch_mode):
    """Launch mode is supplied by the actual trusted entrypoint, not inferred
    from environment variables or a saved promise that a service is installed.
    """
    require(launch_mode in {"DESKTOP_SESSION", "OS_SERVICE", "EXTERNAL"}, "ENVIRONMENT_UNAVAILABLE")
    architecture = {"amd64": "X64", "x86_64": "X64", "arm64": "ARM64",
                    "aarch64": "ARM64"}.get(platform.machine().lower(), "OTHER")
    try:
        if sys.platform == "win32":
            from .windows_key_native import WindowsKeyNative
            import ctypes as C
            from ctypes import wintypes as W
            native = WindowsKeyNative()
            identity = native.identity()
            token = C.c_void_p()
            require(native.a.OpenProcessToken(native.k.GetCurrentProcess(), 8, C.byref(token)),
                    "ENVIRONMENT_UNAVAILABLE")
            try:
                elevated = bool(W.DWORD.from_buffer(native._token_info(token, 20)).value)
            finally:
                native.k.CloseHandle(token)
            try:
                active = native.interactive(identity.session)
            except Exception:
                active = False
            return Environment("WINDOWS", architecture, "ELEVATED" if elevated else "USER",
                               launch_mode, "INTERACTIVE" if active else "NONINTERACTIVE_OR_LOCKED")
        if sys.platform == "linux":
            from .linux_key_native import LinuxKeyNative
            native = LinuxKeyNative()
            user = native.identity()
            # A terminal/display variable is not unlocked desktop-session proof.
            return Environment("LINUX", architecture, "ROOT" if user.uid == 0 else "USER",
                               launch_mode, "UNQUALIFIED")
    except Exception:
        raise SettingsError("ENVIRONMENT_UNAVAILABLE") from None
    raise SettingsError("ENVIRONMENT_UNAVAILABLE")


class CommissionedStorage:
    def __init__(self, port):
        self.port = port

    def verify(self, record):
        """Read exact existing RP019 bindings. No create, seed, scan or reset."""
        try:
            spec, handle = storage_spec(record)
            port = self.port
            from .drive.folder_first_run import RemoteFolderCommissioning
            from .drive.folder_runtime import NativeFolderCommissioning
            if type(port) in {RemoteFolderCommissioning, NativeFolderCommissioning}:
                return port.verify(record)
            require(port.spec == spec and port.root_id == spec.root_id and port.mode == spec.mode,
                    "STORAGE_UNAVAILABLE")
            require(getattr(port,"root_transition",None) == record.get("root_transition"),
                    "STORAGE_UNAVAILABLE")
            port.check_root()
            require(port.inspect_authority(spec, handle) == handle, "STORAGE_UNAVAILABLE")
            snapshot = port.authority(handle).read()
            document = snapshot.document()
            require(document["domain_id"] == spec.domain_id, "STORAGE_UNAVAILABLE")
            require(validate_document(document) == spec.capacity, "STORAGE_UNAVAILABLE")
            from .commissioning_records import current_record
            current_record(document,spec,root_transition=record.get("root_transition"))
            verify_allocated_bindings(spec, port, document["records"], handle.object_id)
            return document
        except Exception:
            raise SettingsError("STORAGE_UNAVAILABLE") from None


class Prerequisites:
    def __init__(self, *, environment, storage, credentials, source, runtime, clock,
                 native_folder=None):
        self.environment, self.storage, self.credentials = environment, storage, credentials
        self.source, self.runtime, self.clock = source, runtime, clock
        self._pin = None
        self._native_folder = native_folder
        self._native_folder_required = native_folder is not None

    def validate(self, payload):
        if self._native_folder is not None or self._native_folder_required:
            from .drive.folder_prerequisites import NativeFolderFirstRun
            try:
                require(type(self._native_folder) is NativeFolderFirstRun
                        and self._native_folder.checker is self, "STORAGE_UNAVAILABLE")
                return NativeFolderFirstRun.validate(self._native_folder, payload)
            except Exception:
                self.credentials = None
                raise
        return self._validate(payload)

    def _validate(self, payload):
        choices = payload["choices"]
        try:
            environment = self.environment()
            require(type(environment) is Environment and
                    (environment.os == "WINDOWS" and environment.architecture == "X64" or
                     environment.os == "LINUX" and environment.architecture in {"X64", "ARM64"}),
                    "ENVIRONMENT_UNAVAILABLE")
        except Exception:
            raise SettingsError("ENVIRONMENT_UNAVAILABLE") from None
        require(choices["storage"] is not None, "STORAGE_UNAVAILABLE")
        self.storage.verify(choices["storage"])
        try:
            for record in choices["credentials"]:
                require(type(self.credentials) is CredentialResolver
                        and self.credentials._installation_id == payload["installation_id"],
                        "CREDENTIAL_UNAVAILABLE")
                for purpose in record["purposes"]:
                    result = self.credentials.capability(record["handle"], purpose=Purpose(purpose),
                        target_id=record["target_id"], target_trust=record["target_trust"])
                    require(result.configured and result.available and result.outcome is Outcome.READY,
                            "CREDENTIAL_UNAVAILABLE")
        except Exception:
            raise SettingsError("CREDENTIAL_UNAVAILABLE") from None
        require(choices["descriptor"] is not None, "DESCRIPTOR_REQUIRED")
        try:
            local = validate_ballpark(choices["descriptor"])
            spec, _ = storage_spec(choices["storage"])
            require(local["installation_id"] == payload["installation_id"]
                    and local["domain_id"] == spec.domain_id, "DESCRIPTOR_INVALID")
            shared = catalogue(local)
            now = self.clock()
            require(type(now) is int and 0 <= now <= 10**12, "DESCRIPTOR_INVALID")
            llm_projection(shared, now=now)
            TimingProfile.parse(choices["timing"])
        except Exception:
            raise SettingsError("DESCRIPTOR_INVALID") from None
        try:
            if self._pin is None:
                self._pin = select(self.source, self.runtime)
            else:
                check_boundary(self.source, self._pin, self.runtime)
        except Exception:
            raise SettingsError("INSTRUCTIONS_UNAVAILABLE") from None
        return Validation(self._pin, environment)


def native_credential_pair(installation, *, runner, clock):
    """Trusted local construction; runner owns commissioned fixed target pins."""
    from .credential_contract import CredentialResolver
    if sys.platform == "win32":
        from .windows_credentials import WindowsKeyStore
        from .windows_key_native import WindowsKeyNative
        store = WindowsKeyStore(installation, native=WindowsKeyNative(), runner=runner, clock=clock)
    elif sys.platform == "linux":
        from .linux_credentials import LinuxKeyStore
        from .linux_key_native import LinuxKeyNative
        store = LinuxKeyStore(installation, native=LinuxKeyNative(), runner=runner, clock=clock)
    else:
        raise SettingsError("CREDENTIAL_UNAVAILABLE")
    return store, CredentialResolver(installation, store, clock=clock)


def restore_setup_credentials(setup, factory):
    """Factory is trusted code. Only freshly read protected metadata can restore."""
    try:
        setup._fresh()
        if setup._payload.get("credential_image") is None:
            require(not setup.private_choices()["credentials"], "CREDENTIAL_UNAVAILABLE")
            return None
        store, resolver = factory(setup.installation_id)
        setup.restore_credentials(store, resolver)
        return resolver
    except Exception:
        raise SettingsError("CREDENTIAL_UNAVAILABLE") from None
