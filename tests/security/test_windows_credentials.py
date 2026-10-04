from contextlib import contextmanager
from dataclasses import replace
import json

import pytest

from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.windows_credentials import KeyAccessError, UserSession, WindowsKeyStore
from tb4.windows_key_native import local_path

INSTALLATION = "00000000-0000-4000-8000-000000000020"
TARGET = "00000000-0000-4000-8000-000000000021"
TRUST = "a" * 64
CANARY = "synthetic-windows-key-never-public"
USER = UserSession("synthetic-user", 1, (2, 3))
PURPOSES = frozenset({Purpose.FETCHER_STATUS, Purpose.FETCHER_START})


class Key:
    version = 1
    def __init__(self, native):
        self.native = native
        self.version = native.version
    def recheck(self):
        if not self.native.permissions:
            raise KeyAccessError(Outcome.DENIED)


class Native:
    user = USER
    active = True
    permissions = True
    version = 1
    state = Outcome.READY
    held = 0
    on_open = None

    def identity(self):
        return self.user
    def interactive(self, session):
        return self.active
    @contextmanager
    def open_key(self, path, sid):
        if self.state is not Outcome.READY:
            raise KeyAccessError(self.state)
        if not self.permissions:
            raise KeyAccessError(Outcome.DENIED)
        self.held += 1
        try:
            if self.on_open:
                self.on_open()
            yield Key(self)
        finally:
            self.held -= 1


class Runner:
    trusted = True
    calls = 0
    result = Outcome.SUCCEEDED
    mode = ""
    def __init__(self, native):
        self.native = native
    def verify_target(self, target, trust):
        if self.mode == "trust_error":
            raise RuntimeError(CANARY)
        return self.trusted
    def fetcher_status(self, key, target, trust):
        assert self.native.held == 1
        assert target == TARGET and trust == TRUST
        self.calls += 1
        if self.mode == "lost":
            raise RuntimeError(CANARY)
        return self.result
    fetcher_start = fetcher_status


def setup(interactive=True):
    native = Native()
    runner = Runner(native)
    clock = [100]
    store = WindowsKeyStore(INSTALLATION, native=native, runner=runner, clock=lambda: clock[0])
    ref = store.select(path="synthetic-selected-key", target_id=TARGET, target_trust=TRUST,
                       purposes=PURPOSES, expires_at=200, interactive_required=interactive,
                       owner_authorized=True)
    resolver = CredentialResolver(INSTALLATION, store, clock=lambda: clock[0])
    handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator=ref,
                             purposes=PURPOSES, expires_at=200, owner_authorized=True)
    return resolver, store, native, runner, clock, ref, handle


def request(purpose=Purpose.FETCHER_STATUS):
    return dict(purpose=purpose, target_id=TARGET, target_trust=TRUST)


@pytest.mark.parametrize("purpose", [Purpose.FETCHER_STATUS, Purpose.FETCHER_START])
def test_one_fixed_call_holds_key_and_safe_report(purpose, capsys):
    resolver, store, native, runner, clock, ref, handle = setup()
    assert resolver.capability(handle, **request(purpose)).outcome is Outcome.READY
    assert resolver.invoke(handle, **request(purpose)).outcome is Outcome.SUCCEEDED
    assert runner.calls == 1 and native.held == 0
    report = json.dumps(resolver.capability(handle, **request()).report())
    report += repr(store._selections[ref]) + repr(native.user)
    assert all(x not in report for x in [CANARY, TRUST, TARGET, ref, handle, "synthetic-user"])
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


@pytest.mark.parametrize("change,expected", [
    ("missing", Outcome.ABSENT), ("locked", Outcome.LOCKED),
    ("provider", Outcome.STORE_UNAVAILABLE), ("permissions", Outcome.DENIED),
    ("user", Outcome.DENIED), ("session", Outcome.DENIED), ("logon", Outcome.DENIED),
    ("interactive", Outcome.LOCKED), ("version", Outcome.REVOKED),
    ("revoked", Outcome.REVOKED), ("expired", Outcome.EXPIRED),
    ("trust", Outcome.DENIED), ("trust_error", Outcome.STORE_UNAVAILABLE),
])
def test_fail_closed_matrix_without_fixed_call(change, expected):
    resolver, store, native, runner, clock, ref, handle = setup()
    if change in {"missing", "locked", "provider"}:
        native.state = {"missing": Outcome.ABSENT, "locked": Outcome.LOCKED,
                        "provider": Outcome.STORE_UNAVAILABLE}[change]
    elif change == "permissions":
        native.permissions = False
    elif change in {"user", "session", "logon"}:
        native.user = replace(USER, **{"user": {"sid": "other"}, "session": {"session": 2},
                                      "logon": {"logon": (9, 9)}}[change])
    elif change == "interactive":
        native.active = False
    elif change == "version":
        native.version = 2
    elif change == "revoked":
        store.revoke_selection(ref, owner_authorized=True)
    elif change == "expired":
        clock[0] = 200
    elif change == "trust":
        runner.trusted = False
    else:
        runner.mode = "trust_error"
    assert resolver.capability(handle, **request()).outcome is expected
    assert resolver.invoke(handle, **request()).outcome is expected
    assert runner.calls == native.held == 0


@pytest.mark.parametrize("change", ["version", "permissions", "session", "expiry", "trust", "revoked"])
def test_direct_use_rechecks_after_previous_ready(change):
    resolver, store, native, runner, clock, ref, handle = setup()
    binding = resolver._bindings[handle]
    ready = store.inspect(binding)
    assert ready.outcome is Outcome.READY
    if change == "version":
        native.version += 1
    elif change == "permissions":
        native.permissions = False
    elif change == "session":
        native.user = replace(USER, session=2)
    elif change == "expiry":
        clock[0] = 200
    elif change == "trust":
        runner.trusted = False
    else:
        store.revoke_selection(ref, owner_authorized=True)
    assert store.use_fixed(binding, Purpose.FETCHER_START, expected_version=ready.version) in {
        Outcome.REVOKED, Outcome.DENIED, Outcome.EXPIRED}
    assert runner.calls == 0


def test_permission_expiry_and_identity_rechecked_while_handle_held():
    for change in ["permission", "expiry", "identity"]:
        resolver, store, native, runner, clock, ref, handle = setup()
        def race():
            if change == "permission":
                native.permissions = False
            elif change == "expiry":
                clock[0] = 200
            else:
                native.user = replace(USER, session=9)
        native.on_open = race
        assert resolver.invoke(handle, **request()).outcome in {Outcome.DENIED, Outcome.EXPIRED}
        assert runner.calls == native.held == 0


@pytest.mark.parametrize("result", [CANARY, {"output": CANARY}, True, Outcome.READY, None])
def test_malformed_result_after_effect_is_unknown_and_never_retried(result):
    resolver, store, native, runner, clock, ref, handle = setup()
    runner.result = result
    report = resolver.invoke(handle, **request()).report()
    assert report == {"outcome": "UNKNOWN", "retry_automatically": False, "inspection_required": True}
    assert CANARY not in json.dumps(report) and runner.calls == 1


def test_lost_reply_and_no_implicit_retry():
    resolver, store, native, runner, clock, ref, handle = setup()
    runner.mode = "lost"
    assert resolver.invoke(handle, **request()).outcome is Outcome.UNKNOWN
    assert runner.calls == 1


@pytest.mark.parametrize("field,value", [
    ("installation_id", TARGET), ("target_id", INSTALLATION), ("target_trust", "b" * 64),
    ("store_locator", "absent"), ("expires_at", 201),
    ("purposes", frozenset({"arbitrary-command"})),
])
def test_direct_binding_bypass_denied(field, value):
    resolver, store, native, runner, clock, ref, handle = setup()
    binding = replace(resolver._bindings[handle], **{field: value})
    assert store.use_fixed(binding, Purpose.FETCHER_START, expected_version=1) is Outcome.DENIED
    assert runner.calls == 0


def test_direct_wrong_purpose_or_generation_denied():
    resolver, store, native, runner, clock, ref, handle = setup()
    binding = resolver._bindings[handle]
    assert store.use_fixed(binding, "shell", expected_version=1) is Outcome.DENIED
    for version in [0, -1, True, "1", 2]:
        assert store.use_fixed(binding, Purpose.FETCHER_START, expected_version=version) in {
            Outcome.DENIED, Outcome.REVOKED}
    assert runner.calls == 0


def test_explicit_noninteractive_policy_still_binds_logon_session():
    resolver, store, native, runner, clock, ref, handle = setup(interactive=False)
    native.active = False
    assert resolver.invoke(handle, **request()).outcome is Outcome.SUCCEEDED
    native.user = replace(USER, logon=(99, 99))
    assert resolver.invoke(handle, **request()).outcome is Outcome.DENIED


def test_rotation_and_revocation_only_change_binding_metadata():
    resolver, store, native, runner, clock, ref, handle = setup()
    new_ref = store.select(path="second-synthetic-key", target_id=TARGET, target_trust=TRUST,
                           purposes=PURPOSES, expires_at=200, interactive_required=True,
                           owner_authorized=True)
    new = resolver.rotate(handle, new_store_locator=new_ref, expires_at=200, owner_authorized=True)
    assert resolver.invoke(handle, **request()).outcome is Outcome.REVOKED
    assert resolver.invoke(new, **request()).outcome is Outcome.SUCCEEDED
    store.revoke_selection(new_ref, owner_authorized=True)
    assert resolver.invoke(new, **request()).outcome is Outcome.REVOKED
    assert native.version == 1 and ref in store._selections


@pytest.mark.parametrize("path", ["relative", "C:relative", r"\\server\share\key",
    r"\\?\C:\key", r"\\.\pipe\key", r"C:\key:stream", r"C:\a\..\key",
    r"C:\key.", r"C:\key ", r"C:\NUL", r"C:\CON.txt", "C:\\key\x00"])
def test_unsafe_path_syntax_denied_before_os_access(path):
    with pytest.raises(KeyAccessError):
        local_path(path)


def test_unavailable_native_platform_is_explicit():
    import os
    if os.name != "nt":
        from tb4.windows_key_native import WindowsKeyNative
        with pytest.raises(KeyAccessError) as error:
            WindowsKeyNative()
        assert str(error.value) == "STORE_UNAVAILABLE"
