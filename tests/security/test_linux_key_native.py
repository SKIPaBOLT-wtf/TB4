"""Real Linux kernel tests, never substitute mocks for fd/ACL/seal behavior."""
from contextlib import contextmanager
import errno
import json
import os
import stat
import struct
import sys

import pytest

from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.key_policy import KeyAccessError
from tb4.linux_credentials import LinuxKeyStore
from tb4.linux_key_native import LinuxKeyNative, MAX_KEY_BYTES
from test_linux_credentials import INSTALLATION, TARGET, TRUST, PURPOSES, request

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"),
                               reason="Actual Linux fd/ACL/seal APIs required")
CANARY = b"synthetic-linux-native-key-do-not-export"


@pytest.fixture
def selected(tmp_path):
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    key = parent / "key"
    key.write_bytes(CANARY)
    key.chmod(0o600)
    return key


def open_selected(path):
    native = LinuxKeyNative()
    return native, native.open_key(str(path), os.getuid())


class Fixed:
    def __init__(self):
        self.calls = 0
        self.borrowed = None
        self.callback = None
    def verify_target(self, target, trust):
        return target == TARGET and trust == TRUST
    def fetcher_status(self, key, target, trust):
        self.calls += 1
        self.borrowed = key
        assert os.read(key.handle, MAX_KEY_BYTES) == CANARY
        if self.callback:
            self.callback(key)
        return Outcome.SUCCEEDED
    fetcher_start = fetcher_status


def enroll(path, mode="headless"):
    native, runner = LinuxKeyNative(), Fixed()
    store = LinuxKeyStore(INSTALLATION, native=native, runner=runner, clock=lambda: 100)
    ref = store.select(path=str(path), target_id=TARGET, target_trust=TRUST,
                       purposes=PURPOSES, expires_at=200, access_mode="existing_key",
                       launch_mode=mode, owner_authorized=True)
    resolver = CredentialResolver(INSTALLATION, store, clock=lambda: 100)
    handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator=ref,
                             purposes=PURPOSES, expires_at=200, owner_authorized=True)
    return resolver, store, runner, ref, handle


@pytest.mark.parametrize("mode", ["desktop", "headless"])
def test_actual_fixed_use_borrowed_lifetime_and_safe_reports(selected, mode, capsys):
    resolver, store, runner, ref, handle = enroll(selected, mode)
    before = selected.read_bytes()
    assert resolver.invoke(handle, **request()).outcome is Outcome.SUCCEEDED
    assert runner.calls == 1
    with pytest.raises(KeyAccessError):
        runner.borrowed.handle
    store.revoke_selection(ref, owner_authorized=True)
    assert resolver.invoke(handle, **request()).outcome is Outcome.REVOKED
    assert selected.read_bytes() == before
    public = json.dumps(resolver.capability(handle, **request()).report()) + repr(runner.borrowed)
    assert str(selected) not in public and CANARY.decode() not in public
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_memfd_is_sealed_private_and_noninheritable(selected):
    native, context = open_selected(selected)
    with context as key:
        fd = key.handle
        assert os.read(fd, MAX_KEY_BYTES) == CANARY
        assert stat.S_IMODE(os.fstat(fd).st_mode) == 0o600
        assert not os.get_inheritable(fd)
        assert native.f.fcntl(fd, native.f.F_GET_SEALS) & native.seals == native.seals
        for operation in [lambda: os.write(fd, b"x"), lambda: os.ftruncate(fd, 0),
                          lambda: os.ftruncate(fd, len(CANARY) + 1)]:
            with pytest.raises(OSError) as error:
                operation()
            assert error.value.errno == errno.EPERM
        assert os.readlink("/proc/self/fd/" + str(fd)).startswith("/memfd:tb4-key")
    with pytest.raises(OSError) as error:
        os.fstat(fd)
    assert error.value.errno == errno.EBADF


@pytest.mark.parametrize("mode", [0o000, 0o200, 0o500, 0o640, 0o604, 0o660, 0o4600])
def test_actual_bad_permissions_denied(selected, mode):
    selected.chmod(mode)
    with pytest.raises(KeyAccessError) as error:
        with open_selected(selected)[1]:
            pytest.fail("Unprotected key admitted")
    assert error.value.outcome is Outcome.DENIED


def test_read_only_owner_key_accepted(selected):
    selected.chmod(0o400)
    with open_selected(selected)[1] as key:
        assert os.read(key.handle, MAX_KEY_BYTES) == CANARY


def test_actual_nonblocking_exclusive_lock(selected):
    native = LinuxKeyNative()
    fd = os.open(selected, os.O_RDONLY)
    try:
        native.f.flock(fd, native.f.LOCK_EX | native.f.LOCK_NB)
        with pytest.raises(KeyAccessError) as error:
            with native.open_key(str(selected), os.getuid()):
                pytest.fail("Locked key admitted")
        assert error.value.outcome is Outcome.LOCKED
    finally:
        os.close(fd)


@pytest.mark.parametrize("kind", ["symlink", "parent_symlink", "hardlink", "fifo", "directory"])
def test_nonregular_or_aliased_files_rejected(selected, kind):
    target = selected
    if kind == "symlink":
        target = selected.with_name("alias")
        target.symlink_to(selected)
    elif kind == "parent_symlink":
        parent = selected.parent.with_name("alias")
        parent.symlink_to(selected.parent, target_is_directory=True)
        target = parent / selected.name
    elif kind == "hardlink":
        os.link(selected, selected.with_name("second"))
    elif kind == "fifo":
        target = selected.with_name("fifo")
        os.mkfifo(target, 0o600)
    else:
        target = selected.parent
    with pytest.raises(KeyAccessError):
        with open_selected(target)[1]:
            pytest.fail("Unsupported object admitted")


@pytest.mark.parametrize("payload", [b"", b"x" * (MAX_KEY_BYTES + 1)])
def test_actual_size_bound(selected, payload):
    selected.write_bytes(payload)
    with pytest.raises(KeyAccessError):
        with open_selected(selected)[1]:
            pytest.fail("Invalid size admitted")


def acl_bytes():
    # Mask zero keeps mode0600/0700 while a named entry is still present.
    entries = [(1, 7, 0xFFFFFFFF), (2, 4, 65534), (4, 0, 0xFFFFFFFF),
               (16, 0, 0xFFFFFFFF), (32, 0, 0xFFFFFFFF)]
    return struct.pack("<I", 2) + b"".join(struct.pack("<HHI", *e) for e in entries)


@pytest.mark.parametrize("where", ["key", "parent_access", "parent_default"])
def test_extended_acl_rejected_even_with_zero_mask(selected, where):
    target = selected if where == "key" else selected.parent
    name = "system.posix_acl_default" if where == "parent_default" else "system.posix_acl_access"
    value = acl_bytes()
    if where == "key":
        value = value[:6] + struct.pack("<H", 6) + value[8:]  # owner rw, not executable
    os.setxattr(target, name, value)
    assert stat.S_IMODE(target.stat().st_mode) in {0o600, 0o700}
    with pytest.raises(KeyAccessError) as error:
        with open_selected(selected)[1]:
            pytest.fail("Extended ACL admitted")
    assert error.value.outcome is Outcome.DENIED


@pytest.mark.parametrize("change", ["content", "replacement", "missing", "mode", "parent_mode"])
def test_actual_rotation_and_permission_rechecked_before_use(selected, change):
    resolver, store, runner, ref, handle = enroll(selected)
    prior = selected.stat()
    if change == "content":
        selected.write_bytes(b"X" * len(CANARY))
        os.utime(selected, ns=(prior.st_atime_ns, prior.st_mtime_ns))
    elif change == "replacement":
        replacement = selected.with_name("replacement")
        replacement.write_bytes(CANARY)
        replacement.chmod(0o600)
        os.replace(replacement, selected)
    elif change == "missing":
        selected.unlink()
    elif change == "mode":
        selected.chmod(0o644)
    else:
        selected.parent.chmod(0o755)
    assert resolver.invoke(handle, **request()).outcome in {
        Outcome.REVOKED, Outcome.DENIED, Outcome.ABSENT}
    assert runner.calls == 0


def test_permission_and_path_rechecks_while_snapshot_is_held(selected):
    with open_selected(selected)[1] as key:
        selected.chmod(0o644)
        with pytest.raises(KeyAccessError):
            key.recheck()
    selected.chmod(0o600)
    with open_selected(selected)[1] as key:
        selected.rename(selected.with_name("moved"))
        with pytest.raises(KeyAccessError):
            key.recheck()


def test_original_mutation_cannot_change_already_admitted_snapshot(selected):
    with open_selected(selected)[1] as key:
        selected.write_bytes(b"X" * len(CANARY))
        assert os.read(key.handle, MAX_KEY_BYTES) == CANARY
        with pytest.raises(KeyAccessError):
            key.recheck()


def test_callback_failure_closes_snapshot_and_does_not_repeat(selected):
    resolver, store, runner, ref, handle = enroll(selected)
    seen = []
    def lost(key):
        seen.append(key.handle)
        raise RuntimeError(CANARY.decode())
    runner.callback = lost
    report = resolver.invoke(handle, **request()).report()
    assert report["outcome"] == "UNKNOWN" and report["retry_automatically"] is False
    assert runner.calls == 1 and CANARY.decode() not in json.dumps(report)
    with pytest.raises(OSError) as error:
        os.fstat(seen[0])
    assert error.value.errno == errno.EBADF


def test_actual_new_session_cannot_use_parent_selection(selected):
    resolver, store, runner, ref, handle = enroll(selected)
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            os.setsid()
            result = resolver.invoke(handle, **request()).outcome.value
            os.write(write_fd, result.encode("ascii"))
            os._exit(0)
        except BaseException:
            os._exit(1)
    os.close(write_fd)
    try:
        result = os.read(read_fd, 64)
        _, status = os.waitpid(pid, 0)
    finally:
        os.close(read_fd)
    assert os.waitstatus_to_exitcode(status) == 0 and result == b"DENIED"


def test_wrong_principal_and_failed_creation_leave_external_files(selected, monkeypatch):
    native = LinuxKeyNative()
    with pytest.raises(KeyAccessError):
        with native.open_key(str(selected), os.getuid() + 1):
            pytest.fail("Wrong user admitted")
    before = len(os.listdir("/proc/self/fd"))
    def unavailable(*args):
        raise OSError(errno.ENOSYS, CANARY.decode())
    monkeypatch.setattr(os, "memfd_create", unavailable)
    for _ in range(3):
        with pytest.raises(KeyAccessError) as error:
            with native.open_key(str(selected), os.getuid()):
                pytest.fail("Unavailable memory facility admitted")
        assert CANARY.decode() not in str(error.value)
    assert len(os.listdir("/proc/self/fd")) == before and selected.read_bytes() == CANARY
