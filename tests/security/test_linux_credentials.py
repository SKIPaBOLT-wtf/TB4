"""Portable Linux policy failures; actual kernel coverage is in test_linux_key_native."""
from contextlib import contextmanager
from dataclasses import replace
import json
import sys

import pytest

from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.key_policy import KeyAccessError
from tb4.linux_credentials import LinuxKeyStore, UserSession
from tb4.linux_key_native import LinuxKeyNative, local_path

INSTALLATION = "00000000-0000-4000-8000-000000000121"
TARGET = "00000000-0000-4000-8000-000000000122"
TRUST = "b" * 64
CANARY = "synthetic-linux-key-never-public"
USER = UserSession(1001, 1001, (1001,), 71, ("synthetic-user-ns", "synthetic-mount-ns"))
PURPOSES = frozenset(Purpose)


class Native:
    user = USER
    version = 1
    state = Outcome.READY
    held = 0
    on_open = None

    def identity(self):
        return self.user

    @contextmanager
    def open_key(self, path, uid):
        assert uid == self.user.uid
        if self.state is not Outcome.READY:
            raise KeyAccessError(self.state)
        self.held += 1
        try:
            if self.on_open:
                self.on_open()
            yield Key(self)
        finally:
            self.held -= 1


class Key:
    def __init__(self, native):
        self.native = native
        self.version = native.version

    def recheck(self):
        if self.native.state is not Outcome.READY:
            raise KeyAccessError(self.native.state)


class Runner:
    trusted = True
    calls = 0
    result = Outcome.SUCCEEDED
    lost = False

    def __init__(self, native):
        self.native = native

    def verify_target(self, target, trust):
        return self.trusted

    def fetcher_status(self, key, target, trust):
        assert self.native.held == 1 and target == TARGET and trust == TRUST
        self.calls += 1
        if self.lost:
            raise RuntimeError(CANARY)
        return self.result

    fetcher_start = fetcher_status


def select_args(mode="headless"):
    return dict(path="/synthetic/private/key", target_id=TARGET, target_trust=TRUST,
                purposes=PURPOSES, expires_at=200, access_mode="existing_key",
                launch_mode=mode, owner_authorized=True)


def setup(mode="headless"):
    native = Native()
    runner = Runner(native)
    clock = [100]
    store = LinuxKeyStore(INSTALLATION, native=native, runner=runner, clock=lambda: clock[0])
    ref = store.select(**select_args(mode))
    resolver = CredentialResolver(INSTALLATION, store, clock=lambda: clock[0])
    handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator=ref,
                              purposes=PURPOSES, expires_at=200, owner_authorized=True)
    return resolver, store, native, runner, clock, ref, handle


def request(purpose=Purpose.FETCHER_STATUS):
    return dict(purpose=purpose, target_id=TARGET, target_trust=TRUST)


@pytest.mark.parametrize("mode", ["headless", "desktop"])
@pytest.mark.parametrize("purpose", list(Purpose))
def test_fixed_use_in_declared_modes_without_agent_or_display(mode, purpose, monkeypatch, capsys):
    monkeypatch.setenv("SSH_AUTH_SOCK", CANARY)
    monkeypatch.setenv("DISPLAY", CANARY)
    resolver, store, native, runner, clock, ref, handle = setup(mode)
    assert resolver.invoke(handle, **request(purpose)).outcome is Outcome.SUCCEEDED
    assert runner.calls == 1 and native.held == 0
    public = json.dumps(resolver.capability(handle, **request()).report())
    public += repr(store._selections[ref]) + repr(native.user)
    assert all(v not in public for v in [CANARY, "/synthetic", TRUST, ref, handle, TARGET])
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


@pytest.mark.parametrize("field,value", [
    ("access_mode", "ssh_agent"), ("access_mode", "secret_service"),
    ("access_mode", "plaintext_config"), ("access_mode", None),
    ("launch_mode", "interactive_unlock"), ("launch_mode", "auto"), ("launch_mode", None),
])
def test_unsupported_modes_fail_without_store_access(field, value):
    native = Native()
    native.on_open = lambda: pytest.fail("Unsupported mode touched key")
    store = LinuxKeyStore(INSTALLATION, native=native, runner=Runner(native), clock=lambda: 100)
    with pytest.raises(KeyAccessError) as error:
        store.select(**(select_args() | {field: value}))
    assert str(error.value) == "STORE_UNAVAILABLE" and native.held == 0


@pytest.mark.parametrize("change,expected", [
    ("missing", Outcome.ABSENT), ("locked", Outcome.LOCKED), ("provider", Outcome.STORE_UNAVAILABLE),
    ("permissions", Outcome.DENIED), ("uid", Outcome.DENIED), ("gid", Outcome.DENIED),
    ("groups", Outcome.DENIED), ("session", Outcome.DENIED), ("namespaces", Outcome.DENIED),
    ("version", Outcome.REVOKED), ("revoked", Outcome.REVOKED), ("expiry", Outcome.EXPIRED),
    ("trust", Outcome.DENIED),
])
def test_failure_matrix_never_admits_helper(change, expected):
    resolver, store, native, runner, clock, ref, handle = setup()
    if change in {"missing", "locked", "provider", "permissions"}:
        native.state = {"missing": Outcome.ABSENT, "locked": Outcome.LOCKED,
                        "provider": Outcome.STORE_UNAVAILABLE, "permissions": Outcome.DENIED}[change]
    elif change in {"uid", "gid", "groups", "session", "namespaces"}:
        native.user = replace(USER, **{change: {"uid": 1002, "gid": 1002, "groups": (),
                             "session": 72, "namespaces": ("changed", "changed")}[change]})
    elif change == "version":
        native.version += 1
    elif change == "revoked":
        store.revoke_selection(ref, owner_authorized=True)
    elif change == "expiry":
        clock[0] = 200
    else:
        runner.trusted = False
    assert resolver.capability(handle, **request()).outcome is expected
    assert resolver.invoke(handle, **request()).outcome is expected
    assert runner.calls == native.held == 0


@pytest.mark.parametrize("change", ["identity", "permission", "expiry", "trust", "revoked"])
def test_changes_during_held_acquisition_deny_before_use(change):
    resolver, store, native, runner, clock, ref, handle = setup()
    binding = resolver._bindings[handle]
    version = store.inspect(binding).version
    def race():
        if change == "identity":
            native.user = replace(USER, session=99)
        elif change == "permission":
            native.state = Outcome.DENIED
        elif change == "expiry":
            clock[0] = 200
        elif change == "trust":
            runner.trusted = False
        else:
            store.revoke_selection(ref, owner_authorized=True)
    native.on_open = race
    assert store.use_fixed(binding, Purpose.FETCHER_START, expected_version=version) in {
        Outcome.DENIED, Outcome.EXPIRED, Outcome.REVOKED}
    assert runner.calls == native.held == 0


@pytest.mark.parametrize("result", [CANARY, {"stderr": CANARY}, True, None, Outcome.READY])
def test_raw_or_malformed_callback_is_unknown_without_replay(result):
    resolver, store, native, runner, clock, ref, handle = setup()
    runner.result = result
    report = resolver.invoke(handle, **request()).report()
    assert report == dict(outcome="UNKNOWN", retry_automatically=False, inspection_required=True)
    assert CANARY not in json.dumps(report) and runner.calls == 1


def test_lost_reply_and_rotation_preserve_uncertainty():
    resolver, store, native, runner, clock, ref, handle = setup()
    runner.lost = True
    assert resolver.invoke(handle, **request()).outcome is Outcome.UNKNOWN
    assert runner.calls == 1
    runner.lost = False
    new_ref = store.select(**(select_args() | {"path": "/synthetic/private/second"}))
    new = resolver.rotate(handle, new_store_locator=new_ref, expires_at=200, owner_authorized=True)
    assert resolver.invoke(handle, **request()).outcome is Outcome.REVOKED
    assert resolver.invoke(new, **request()).outcome is Outcome.SUCCEEDED
    store.revoke_selection(new_ref, owner_authorized=True)
    assert resolver.invoke(new, **request()).outcome is Outcome.REVOKED


@pytest.mark.parametrize("field,value", [
    ("installation_id", TARGET), ("target_id", INSTALLATION), ("target_trust", "a" * 64),
    ("store_locator", "unknown"), ("expires_at", 201),
    ("purposes", frozenset({"shell"})),
])
def test_direct_binding_bypass_denied(field, value):
    resolver, store, native, runner, clock, ref, handle = setup()
    binding = replace(resolver._bindings[handle], **{field: value})
    assert store.use_fixed(binding, Purpose.FETCHER_START, expected_version=1) is Outcome.DENIED
    assert runner.calls == 0


@pytest.mark.parametrize("path", ["relative", "/", "//key", "/a/../key", "/a/./key", "/a//key",
                                  "/key/", "/key\x00", None, "/a" * 129])
def test_path_aliases_rejected_without_os_open(path):
    with pytest.raises(KeyAccessError):
        local_path(path)


def test_non_linux_native_mode_explicit():
    if not sys.platform.startswith("linux"):
        with pytest.raises(KeyAccessError) as error:
            LinuxKeyNative()
        assert str(error.value) == "STORE_UNAVAILABLE"

MOUNT = "29 1 8:1 / /synthetic rw - ext4 synthetic rw"


@pytest.mark.parametrize("fstype,magic", [("ext4", 0xEF53), ("xfs", 0x58465342)])
def test_exact_descriptor_mount_type_and_magic_agree(fstype, magic):
    from tb4.linux_key_native import qualified_mount
    assert qualified_mount("pos: 0\nmnt_id: 29\n", MOUNT.replace("ext4", fstype), magic) == fstype


@pytest.mark.parametrize("fdinfo,mountinfo,magic", [
    ("mnt_id: 29", MOUNT.replace("ext4", "ext2"), 0xEF53),
    ("mnt_id: 29", MOUNT.replace("ext4", "ext3"), 0xEF53),
    ("mnt_id: 29", MOUNT.replace("ext4", "nfs"), 0xEF53),
    ("mnt_id: 29", MOUNT.replace("ext4", "overlay"), 0xEF53),
    ("mnt_id: 29", MOUNT, 0x58465342),
    ("mnt_id: 29", MOUNT, True),
    ("mnt_id: 29\nmnt_id: 29", MOUNT, 0xEF53),
    ("mnt_id: -29", MOUNT, 0xEF53),
    ("pos: 0", MOUNT, 0xEF53),
    ("mnt_id: 30", MOUNT, 0xEF53),
    ("mnt_id: 29", MOUNT + "\n" + MOUNT, 0xEF53),
    ("mnt_id: 29", "29 malformed", 0xEF53),
    ("mnt_id: 29", MOUNT.replace("8:1", "invalid"), 0xEF53),
    ("mnt_id: 29", MOUNT + " - duplicated", 0xEF53),
])
def test_unknown_ambiguous_or_different_filesystem_is_denied(fdinfo, mountinfo, magic):
    from tb4.linux_key_native import qualified_mount
    with pytest.raises(KeyAccessError):
        qualified_mount(fdinfo, mountinfo, magic)


@pytest.mark.parametrize("which", ["fdinfo", "mountinfo"])
def test_kernel_table_reads_are_bounded(which):
    from tb4.linux_key_native import qualified_mount
    args = dict(fdinfo="mnt_id: 29", mountinfo=MOUNT, magic=0xEF53)
    args[which] = "x" * (8193 if which == "fdinfo" else 2 * 1024 * 1024 + 1)
    with pytest.raises(KeyAccessError):
        qualified_mount(**args)
