"""Trusted read-only OpenSSH proof composition; no public credential payload API.

Endpoint objects are protected commissioning inputs, never shared/LLM fields.
Only the existing resolver selects/uses a key. The fixed runner owns a transient
thread-bound VERIFY slot; its public return is still Outcome only. No selection,
provisioning, authority READ/CAS, activation, retry or alternate identity exists.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import ipaddress
import os
import re
import threading

from tb4.credential_contract import CredentialResolver, Outcome, Purpose, identity
from tb4.exchange_layout import MAX_GENERATION
from tb4.linux_credentials import LinuxKeyStore
from tb4.linux_key_native import HeldKey as LinuxHeldKey, LinuxKeyNative
from tb4.windows_credentials import WindowsKeyStore
from tb4.windows_key_native import HeldKey as WindowsHeldKey, WindowsKeyNative
from .commissioning import SetupSpec
from .commissioning_bootstrap import AuthorityHandle
from .docs_authority import AuthorityError, require
from .folder_authority import FolderBinding
from .folder_probe import check_probe_header, checked_document, probe_header
from .folder_protocol import MODE, body_bytes, flat_json
from .folder_transport import FixedProcess


def _text(value, limit):
    return (type(value) is str and 0 < len(value) <= limit
            and not any(ord(c) < 32 or ord(c) == 127 for c in value))


def _host(value):
    if not _text(value, 253):
        return False
    try:
        ipaddress.ip_address(value)
        return "%" not in value or re.fullmatch(r"[A-Za-z0-9_.:-]+%[A-Za-z0-9_.-]+", value) is not None
    except ValueError:
        return all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                   for label in value.split("."))


def _file_option(value):
    # Escape OpenSSH file tokens and configuration grammar, never a shell.
    # Environment interpolation/control characters cannot name a selected file.
    require(_text(value, 4096) and "$" + "{" not in value and os.path.isabs(value), "PROBE_ENDPOINT")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


@dataclass(frozen=True, repr=False)
class ProbeEndpoint:
    target_id: str
    trust: str
    executable: str
    host: str
    port: int
    user: str
    known_hosts: str
    known_version: int
    timeout: float = 10.0

    def __post_init__(self):
        require(identity(self.target_id) and type(self.trust) is str
                and re.fullmatch(r"[a-f0-9]{64}", self.trust)
                and _text(self.executable, 4096) and os.path.isabs(self.executable)
                and _host(self.host) and _text(self.user, 128)
                and type(self.port) is int and 1 <= self.port <= 65535
                and type(self.known_version) is int and 1 <= self.known_version <= 2**256
                and type(self.timeout) in {int, float} and 0 < self.timeout <= 15, "PROBE_ENDPOINT")
        _file_option(self.known_hosts)


def _argv(endpoint, key_path, known_path):
    require(type(endpoint) is ProbeEndpoint, "PROBE_ENDPOINT")
    policy = (
        "BatchMode=yes", "IdentitiesOnly=yes", "IdentityAgent=none",
        "PKCS11Provider=none", "SecurityKeyProvider=none",
        "PreferredAuthentications=publickey", "PasswordAuthentication=no",
        "KbdInteractiveAuthentication=no", "GSSAPIAuthentication=no", "HostbasedAuthentication=no",
        "StrictHostKeyChecking=yes", "VerifyHostKeyDNS=no", "UpdateHostKeys=no",
        "KnownHostsCommand=none", "ControlMaster=no", "ControlPath=none", "ControlPersist=no",
        "ProxyCommand=none", "ProxyJump=none", "PermitLocalCommand=no",
        "ForwardAgent=no", "ForwardX11=no", "ClearAllForwardings=yes",
        "CanonicalizeHostname=no", "ConnectionAttempts=1", "ConnectTimeout=2")
    return (endpoint.executable, "-F", "none", "-T", *("-o" + p for p in policy),
        "-oIdentityFile=" + _file_option(key_path),
        "-oCertificateFile=" + ('"NUL"' if os.name == "nt" else '"/dev/null"'),
        "-oUserKnownHostsFile=" + _file_option(known_path),
        "-oGlobalKnownHostsFile=" + ('"NUL"' if os.name == "nt" else '"/dev/null"'),
        "-p", str(endpoint.port), "-l", endpoint.user, endpoint.host, "tb4-folder-probe-v1")


@dataclass(repr=False)
class _Pending:
    token: object
    thread: int
    raw: bytes
    used: bool = False
    reply: bytes | None = None


def probe_request(binding, spec, authority, raw):
    """Pure closed VERIFY validation, before any native or credential IO."""
    value = flat_json(raw)
    from .folder_mapping_after_probe import MODE as AFTER_MODE, after_request
    if value.get("mode") == AFTER_MODE:
        return after_request(binding, spec, authority, raw)
    check_probe_header(value, binding)
    require(set(value) == set(probe_header(binding, "")) |
            {"operation", "blueprint", "authority"} and value["operation"] == "VERIFY"
            and value["blueprint"] == spec.fingerprint
            and value["authority"] == authority.seal, "PROBE_REQUEST")
    return value


class FolderProbeRunner:
    def __init__(self, native, endpoint, spec, handle):
        require(type(endpoint) is ProbeEndpoint and type(spec) is SetupSpec and spec.mode == MODE
                and type(handle) is AuthorityHandle and handle.object_id == spec.root_id
                and handle.tab_id is None
                and (os.name == "nt" and type(native) is WindowsKeyNative
                     or os.name == "posix" and type(native) is LinuxKeyNative), "PROBE_ENDPOINT")
        self._native, self.endpoint, self.spec, self.authority = native, endpoint, spec, handle
        self.binding = FolderBinding(spec.root_id, spec.domain_id)
        self._lock, self._pending = threading.RLock(), None

    @contextmanager
    def _known(self):
        user = self._native.identity()
        principal = user.sid if os.name == "nt" else user.uid
        with self._native.open_key(self.endpoint.known_hosts, principal) as known:
            require(known.version == self.endpoint.known_version, "PROBE_ENDPOINT")
            known.recheck()
            yield known

    def verify_target(self, target, trust):
        if target != self.endpoint.target_id or trust != self.endpoint.trust:
            return False
        try:
            with self._known():
                return True
        except Exception:
            return False

    def _request(self, raw):
        return probe_request(self.binding, self.spec, self.authority, raw)

    def _response(self, raw, request):
        from .folder_mapping_after_probe import MODE as AFTER_MODE, after_response
        if request.get("mode") == AFTER_MODE:
            after_response(self.binding, self.spec, self.authority, raw, request)
            return
        value = flat_json(raw)
        check_probe_header(value, self.binding, request["nonce"])
        require(set(value) == set(probe_header(self.binding, "")) |
                {"result", "revision", "body", "blueprint", "authority"}
                and value["result"] == "VERIFIED" and value["blueprint"] == self.spec.fingerprint
                and value["authority"] == self.authority.seal
                and type(value["revision"]) is int and 1 <= value["revision"] <= MAX_GENERATION,
                "PROBE_RESPONSE")
        _, spec = checked_document(body_bytes(value["body"], self.binding), self.binding,
                                   self.spec.fingerprint)
        require(spec == self.spec, "PROBE_RESPONSE")

    def folder_probe(self, key, target, trust):
        # Neither process nor runner holds this lock while invoking resolver or
        # waiting for IO: other callers can refuse the occupied slot promptly.
        with self._lock:
            pending = self._pending
            kind = WindowsHeldKey if os.name == "nt" else LinuxHeldKey
            if (pending is None or pending.thread != threading.get_ident() or pending.used
                    or type(key) is not kind or target != self.endpoint.target_id
                    or trust != self.endpoint.trust):
                return Outcome.DENIED
            pending.used = True
        sent = False
        try:
            request = self._request(pending.raw)
            with self._known() as known:
                key.recheck()
                argv = _argv(self.endpoint, key.process_path(), known.process_path())
                key.recheck(); known.recheck()
                sent = True
                raw = FixedProcess(self.binding, argv, self.endpoint.timeout).call(pending.raw)
                key.recheck(); known.recheck()
                self._response(raw, request)
                with self._lock:
                    require(self._pending is pending, "PROBE_UNAVAILABLE")
                    pending.reply = raw
                return Outcome.SUCCEEDED
        except Exception:
            with self._lock:
                pending.reply = None
            return Outcome.UNKNOWN if sent else Outcome.DENIED


class CredentialProbeProcess:
    """Exact typed proof-only transport. No caller command or public reply slot."""
    def __init__(self, resolver, handle):
        require(type(resolver) is CredentialResolver and type(handle) is str
                and re.fullmatch(r"cr_[a-f0-9]{32}", handle), "PROBE_CREDENTIAL")
        store = resolver._store
        require(type(store) in {WindowsKeyStore, LinuxKeyStore}
                and type(store._runner) is FolderProbeRunner
                and store._native is store._runner._native, "PROBE_CREDENTIAL")
        self._resolver, self._handle, self._runner = resolver, handle, store._runner
        runner = self._runner
        self.binding, self.spec, self.authority = runner.binding, runner.spec, runner.authority
        self._endpoint = runner.endpoint

    def _current(self):
        runner = self._runner
        require(self._resolver._store._runner is runner
                and self._resolver._store._native is runner._native
                and runner.endpoint == self._endpoint and runner.binding == self.binding
                and runner.spec == self.spec and runner.authority == self.authority, "PROBE_CREDENTIAL")

    def call(self, raw):
        token = object()
        runner = self._runner
        try:
            self._current()
            runner._request(raw)  # Closed VERIFY only, before any credential/native IO.
            with runner._lock:
                require(runner._pending is None, "PROBE_BUSY")
                runner._pending = _Pending(token, threading.get_ident(), raw)
            # Resolver returns only an enum. Raw proof stays in trusted local code.
            result = self._resolver.invoke(self._handle, purpose=Purpose.FOLDER_PROBE,
                target_id=self._endpoint.target_id, target_trust=self._endpoint.trust)
            self._current()
            with runner._lock:
                pending = runner._pending
                require(result.outcome is Outcome.SUCCEEDED and pending is not None
                        and pending.token is token and pending.used and type(pending.reply) is bytes,
                        "PROBE_UNAVAILABLE")
                return pending.reply
        except Exception:
            raise AuthorityError("HELPER_UNAVAILABLE") from None
        finally:
            with runner._lock:
                if runner._pending is not None and runner._pending.token is token:
                    runner._pending.reply = None
                    runner._pending = None


def credential_probe_pair(installation_id, endpoint, spec, handle, *, clock):
    """Trusted factory; creates no selected key, enrollment or protected image."""
    if os.name == "nt":
        native, kind = WindowsKeyNative(), WindowsKeyStore
    elif os.name == "posix":
        native, kind = LinuxKeyNative(), LinuxKeyStore
    else:
        raise AuthorityError("PROBE_CREDENTIAL")
    runner = FolderProbeRunner(native, endpoint, spec, handle)
    store = kind(installation_id, native=native, runner=runner, clock=clock)
    return store, CredentialResolver(installation_id, store, clock=clock)
