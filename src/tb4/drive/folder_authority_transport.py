"""Trusted existing-Folder fixed READ/CAS; credential outcomes never carry payload.

No enrollment, key copy, endpoint discovery, provisioning, replay or activation.
A private one-call slot carries only a closed correlated normal protocol reply.
Authority/effect authorization and durable endpoint commissioning are separate.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
import re
import threading

from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.exchange_layout import MAX_GENERATION
from tb4.linux_credentials import LinuxKeyStore
from tb4.linux_key_native import HeldKey as LinuxHeldKey, LinuxKeyNative
from tb4.windows_credentials import WindowsKeyStore
from tb4.windows_key_native import HeldKey as WindowsHeldKey, WindowsKeyNative
from .docs_authority import AuthorityError, WriteResult, require
from .folder_authority import FolderBinding
from .folder_probe_transport import ProbeEndpoint, _argv, _Pending
from .folder_protocol import body_bytes, check_header, flat_json, header
from .folder_transport import FixedProcess


def _authority_argv(endpoint, key_path, known_path):
    # The qualified closed SSH policy changes only its fixed normal command.
    argv = _argv(endpoint, key_path, known_path)
    return (*argv[:-1], "tb4-folder-v1")


def _request(binding, raw):
    require(type(binding) is FolderBinding, "AUTHORITY_TRANSPORT_BINDING")
    value = flat_json(raw)
    check_header(value, binding)
    operation = value.get("operation")
    require(operation in {"READ", "CAS"} and set(value) == set(header(binding, "")) |
            {"operation"} | ({"expected", "body"} if operation == "CAS" else set()),
            "AUTHORITY_TRANSPORT_REQUEST")
    if operation == "CAS":
        require(type(value["expected"]) is int and 1 <= value["expected"] < MAX_GENERATION,
                "REVISION_INVALID")
        body_bytes(value["body"], binding)
    return value


def _response(binding, raw, request):
    value = flat_json(raw)
    check_header(value, binding, request["nonce"])
    fields = set(header(binding, "")) | {"result"}
    if request["operation"] == "READ":
        require(set(value) == fields | {"revision", "body"} and value["result"] == "SNAPSHOT",
                "AUTHORITY_TRANSPORT_REPLY")
        require(type(value["revision"]) is int and 1 <= value["revision"] <= MAX_GENERATION,
                "REVISION_INVALID")
        body_bytes(value["body"], binding)
    else:
        require(set(value) == fields and value["result"] in {
            WriteResult.ACCEPTED.value, WriteResult.REJECTED.value, WriteResult.UNAVAILABLE.value},
            "AUTHORITY_TRANSPORT_REPLY")
    # ACCEPTED is the existing protocol result, still requiring caller readback.


class FolderAuthorityRunner:
    def __init__(self, native, endpoint, binding):
        require(type(endpoint) is ProbeEndpoint and type(binding) is FolderBinding
                and (os.name == "nt" and type(native) is WindowsKeyNative
                     or os.name == "posix" and type(native) is LinuxKeyNative),
                "AUTHORITY_TRANSPORT_ENDPOINT")
        self._native, self.endpoint, self.binding = native, endpoint, binding
        self._native_pin, self._endpoint_pin, self._binding_pin = native, endpoint, binding
        self._lock, self._pending = threading.RLock(), None

    def _current(self):
        require(self._native is self._native_pin and self.endpoint == self._endpoint_pin
                and self.binding == self._binding_pin, "AUTHORITY_TRANSPORT_ENDPOINT")

    @contextmanager
    def _known(self):
        self._current()
        user = self._native.identity()
        principal = user.sid if os.name == "nt" else user.uid
        with self._native.open_key(self._endpoint_pin.known_hosts, principal) as known:
            require(known.version == self._endpoint_pin.known_version, "AUTHORITY_TRANSPORT_ENDPOINT")
            known.recheck()
            self._current()
            yield known

    def verify_target(self, target, trust):
        if target != self._endpoint_pin.target_id or trust != self._endpoint_pin.trust:
            return False
        try:
            with self._known():
                return True
        except Exception:
            return False

    def folder_authority(self, key, target, trust):
        # Claim under the slot lock; never hold it over resolver/native/process IO.
        with self._lock:
            pending = self._pending
            kind = WindowsHeldKey if os.name == "nt" else LinuxHeldKey
            if (pending is None or pending.thread != threading.get_ident() or pending.used
                    or type(key) is not kind or target != self._endpoint_pin.target_id
                    or trust != self._endpoint_pin.trust):
                return Outcome.DENIED
            pending.used = True
        sent = False
        try:
            self._current()
            request = _request(self._binding_pin, pending.raw)
            with self._known() as known:
                key.recheck()
                argv = _authority_argv(self._endpoint_pin, key.process_path(), known.process_path())
                key.recheck(); known.recheck(); self._current()
                sent = True
                raw = FixedProcess(self._binding_pin, argv, self._endpoint_pin.timeout).call(pending.raw)
                key.recheck(); known.recheck(); self._current()
                _response(self._binding_pin, raw, request)
                with self._lock:
                    require(self._pending is pending, "AUTHORITY_TRANSPORT_REPLY")
                    pending.reply = raw
                return Outcome.SUCCEEDED
        except Exception:
            with self._lock:
                pending.reply = None
            return Outcome.UNKNOWN if sent else Outcome.DENIED


class CredentialAuthorityProcess:
    """Exact trusted normal process; private raw reply is never a UseResult."""
    def __init__(self, resolver, handle):
        require(type(resolver) is CredentialResolver and type(handle) is str
                and re.fullmatch(r"cr_[a-f0-9]{32}", handle), "AUTHORITY_TRANSPORT_CREDENTIAL")
        store = resolver._store
        require(type(store) in {WindowsKeyStore, LinuxKeyStore}
                and type(store._runner) is FolderAuthorityRunner
                and store._native is store._runner._native, "AUTHORITY_TRANSPORT_CREDENTIAL")
        self._resolver, self._handle, self._store, self._runner = resolver, handle, store, store._runner
        self._native, self._installation = store._native, store.installation_id
        self.binding, self._endpoint = self._runner.binding, self._runner.endpoint

    def _current(self):
        runner = self._runner
        require(self._resolver._store is self._store and self._store._runner is runner
                and self._store.installation_id == self._installation == self._resolver._installation_id
                and self._store._native is self._native is runner._native
                and runner.endpoint == self._endpoint and runner.binding == self.binding,
                "AUTHORITY_TRANSPORT_CREDENTIAL")
        runner._current()

    def call(self, raw):
        runner, token = self._runner, object()
        try:
            self._current()
            _request(self.binding, raw)  # Closed normal protocol, before credential IO.
            with runner._lock:
                require(runner._pending is None, "AUTHORITY_TRANSPORT_BUSY")
                runner._pending = _Pending(token, threading.get_ident(), raw)
            result = self._resolver.invoke(self._handle, purpose=Purpose.FOLDER_AUTHORITY,
                target_id=self._endpoint.target_id, target_trust=self._endpoint.trust)
            self._current()
            with runner._lock:
                pending = runner._pending
                require(result.outcome is Outcome.SUCCEEDED and pending is not None
                        and pending.token is token and pending.used and type(pending.reply) is bytes,
                        "AUTHORITY_TRANSPORT_REPLY")
                return pending.reply
        except Exception:
            raise AuthorityError("HELPER_UNAVAILABLE") from None
        finally:
            with runner._lock:
                if runner._pending is not None and runner._pending.token is token:
                    runner._pending.reply = None
                    runner._pending = None


def credential_authority_pair(installation_id, endpoint, binding, *, clock):
    """Trusted factory; creates no selection, enrollment, profile or authority."""
    if os.name == "nt":
        native, kind = WindowsKeyNative(), WindowsKeyStore
    else:
        native, kind = LinuxKeyNative(), LinuxKeyStore
    runner = FolderAuthorityRunner(native, endpoint, binding)
    store = kind(installation_id, native=native, runner=runner, clock=clock)
    return store, CredentialResolver(installation_id, store, clock=clock)

