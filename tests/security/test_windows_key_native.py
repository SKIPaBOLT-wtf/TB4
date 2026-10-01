"""Actual native tests only touch new synthetic pytest-owned files."""
from contextlib import contextmanager
import ctypes as C
from ctypes import wintypes as W
from dataclasses import replace
import json
import os

import pytest

from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.windows_credentials import KeyAccessError, WindowsKeyStore
from tb4.windows_key_native import MAX_KEY_BYTES, WindowsKeyNative

pytestmark = pytest.mark.skipif(os.name != "nt", reason="requires actual Windows token/DACL/file handles")
INSTALLATION = "00000000-0000-4000-8000-000000000020"
TARGET = "00000000-0000-4000-8000-000000000021"
TRUST = "a" * 64
CANARY = b"synthetic-native-key-canary"


def protect(api, path, extra=""):
    """TEST ONLY: set DACL only on a freshly created synthetic fixture."""
    sid = api.identity().sid
    descriptor = C.c_void_p()
    convert = api.a.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [W.LPCWSTR, W.DWORD, C.POINTER(C.c_void_p), C.POINTER(W.DWORD)]
    convert.restype = W.BOOL
    apply = api.a.SetFileSecurityW
    apply.argtypes = [W.LPCWSTR, W.DWORD, C.c_void_p]
    apply.restype = W.BOOL
    assert convert("O:" + sid + "D:P(A;;FA;;;" + sid + ")(A;;FA;;;SY)(A;;FA;;;BA)" + extra,
                   1, C.byref(descriptor), None), "fixture descriptor failed"
    try:
        assert apply(str(path), 0x80000005, descriptor), "fixture owner/DACL failed"
    finally:
        api.k.LocalFree(descriptor)


def owner_matches_user(api, path):
    """Return only a boolean; never export the actual native owner/token SID."""
    handle = api.k.CreateFileW(str(path), 0x20000, 7, None, 3, 0, None)
    assert handle != C.c_void_p(-1).value, "fixture owner read handle failed"
    owner, descriptor = C.c_void_p(), C.c_void_p()
    try:
        assert api.a.GetSecurityInfo(handle, 1, 1, C.byref(owner), None,
                                     None, None, C.byref(descriptor)) == 0
        return api._sid(owner) == api.identity().sid
    finally:
        if descriptor:
            api.k.LocalFree(descriptor)
        api.k.CloseHandle(handle)


def test_fixture_explicit_owner_is_independent_of_process_default(tmp_path):
    api = WindowsKeyNative()
    path = tmp_path / "synthetic-owner-check"
    path.write_bytes(CANARY)
    before = owner_matches_user(api, path)
    protect(api, path)
    after = owner_matches_user(api, path)
    print(json.dumps({"default_owner_matches_user": before, "selected_owner_matches_user": after}))
    assert after is True
    with api.open_key(str(path), api.identity().sid):
        pass


@pytest.fixture
def fixture(tmp_path):
    api = WindowsKeyNative()
    path = tmp_path / "synthetic-key"
    path.write_bytes(CANARY)
    protect(api, path)
    return api, path


class Runner:
    calls = 0
    saved = None
    def verify_target(self, target, trust):
        return target == TARGET and trust == TRUST
    def fetcher_status(self, key, target, trust):
        self.saved = key
        data = C.create_string_buffer(1024)
        count = W.DWORD()
        assert key._api.k.ReadFile(key.handle, data, len(data), C.byref(count), None)
        assert data.raw[:count.value] == CANARY
        self.calls += 1
        return Outcome.SUCCEEDED
    fetcher_start = fetcher_status


def enroll(api, path, runner=None):
    runner = runner or Runner()
    store = WindowsKeyStore(INSTALLATION, native=api, runner=runner, clock=lambda: 100)
    ref = store.select(path=str(path), target_id=TARGET, target_trust=TRUST,
                       purposes=frozenset(Purpose), expires_at=200,
                       interactive_required=False, owner_authorized=True)
    resolver = CredentialResolver(INSTALLATION, store, clock=lambda: 100)
    handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator=ref,
                             purposes=frozenset(Purpose), expires_at=200, owner_authorized=True)
    return resolver, store, runner, ref, handle


def request():
    return dict(purpose=Purpose.FETCHER_STATUS, target_id=TARGET, target_trust=TRUST)


def test_native_token_acl_content_version_and_borrowed_lifetime(fixture, capsys):
    api, path = fixture
    resolver, store, runner, ref, handle = enroll(api, path)
    assert resolver.capability(handle, **request()).outcome is Outcome.READY
    report = resolver.invoke(handle, **request()).report()
    assert report["outcome"] == "SUCCEEDED" and runner.calls == 1
    with pytest.raises(KeyAccessError):
        _ = runner.saved.handle
    public = json.dumps(report) + repr(store._selections[ref]) + repr(runner.saved)
    assert all(value not in public for value in [str(path), CANARY.decode(), api.identity().sid, ref, handle])
    assert path.read_bytes() == CANARY
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_native_null_and_broad_dacl_fail_closed(fixture):
    api, path = fixture
    resolver, store, runner, ref, handle = enroll(api, path)
    protect(api, path, "(A;;GR;;;WD)")
    assert resolver.capability(handle, **request()).outcome is Outcome.DENIED
    assert resolver.invoke(handle, **request()).outcome is Outcome.DENIED
    assert runner.calls == 0
    # A NULL DACL means full access; it must never be interpreted as private.
    set_security = api.a.SetNamedSecurityInfoW
    set_security.argtypes = [W.LPWSTR, W.DWORD, W.DWORD] + [C.c_void_p] * 4
    set_security.restype = W.DWORD
    assert set_security(str(path), 1, 4, None, None, None, None) == 0
    try:
        assert resolver.capability(handle, **request()).outcome is Outcome.DENIED
    finally:
        protect(api, path)


def test_native_wrong_owner_requirement_fails(fixture):
    api, path = fixture
    with pytest.raises(KeyAccessError) as error:
        with api.open_key(str(path), "S-1-0-0"):
            pytest.fail("wrong owner admitted")
    assert error.value.outcome is Outcome.DENIED


def test_native_share_lock_blocks_conflicting_use_and_releases(fixture):
    api, path = fixture
    resolver, store, runner, ref, handle = enroll(api, path)
    held = api.k.CreateFileW(str(path), 0x80000000, 0, None, 3, 0, None)
    assert held != C.c_void_p(-1).value
    try:
        assert resolver.capability(handle, **request()).outcome is Outcome.LOCKED
        assert runner.calls == 0
    finally:
        api.k.CloseHandle(held)
    assert resolver.invoke(handle, **request()).outcome is Outcome.SUCCEEDED


def test_native_held_file_denies_write_and_delete_access(fixture):
    api, path = fixture
    with api.open_key(str(path), api.identity().sid):
        for access in [0x40000000, 0x10000]:
            conflicting = api.k.CreateFileW(str(path), access, 7, None, 3, 0, None)
            if conflicting != C.c_void_p(-1).value:
                api.k.CloseHandle(conflicting)
                pytest.fail("write/delete access admitted while key held")
            assert C.get_last_error() == 32
    assert path.read_bytes() == CANARY


def test_native_changed_content_rejected_even_with_restored_mtime(fixture):
    api, path = fixture
    resolver, store, runner, ref, handle = enroll(api, path)
    before = path.stat()
    path.write_bytes(b"changed-synthetic-material")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert resolver.invoke(handle, **request()).outcome is Outcome.REVOKED
    assert runner.calls == 0


def test_native_replaced_and_missing_file_do_not_rebind(fixture):
    api, path = fixture
    resolver, store, runner, ref, handle = enroll(api, path)
    moved = path.with_name("preserved-original")
    path.rename(moved)
    assert resolver.capability(handle, **request()).outcome is Outcome.ABSENT
    path.write_bytes(CANARY)
    protect(api, path)
    assert resolver.invoke(handle, **request()).outcome is Outcome.REVOKED
    assert moved.read_bytes() == CANARY and runner.calls == 0


@pytest.mark.parametrize("size", [0, MAX_KEY_BYTES + 1])
def test_native_size_bounds(fixture, size):
    api, path = fixture
    path.write_bytes(b"x" * size)
    with pytest.raises(KeyAccessError) as error:
        with api.open_key(str(path), api.identity().sid):
            pytest.fail("invalid size admitted")
    assert error.value.outcome is Outcome.DENIED


def test_native_hard_link_refused(fixture):
    api, path = fixture
    os.link(path, path.with_name("synthetic-alias"))
    with pytest.raises(KeyAccessError) as error:
        with api.open_key(str(path), api.identity().sid):
            pytest.fail("multiple links admitted")
    assert error.value.outcome is Outcome.DENIED


def test_native_acl_change_between_inspect_and_use(fixture):
    api, path = fixture
    resolver, store, runner, ref, handle = enroll(api, path)
    binding = resolver._bindings[handle]
    ready = store.inspect(binding)
    protect(api, path, "(A;;GR;;;WD)")
    assert store.use_fixed(binding, Purpose.FETCHER_STATUS,
                           expected_version=ready.version) is Outcome.DENIED
    assert runner.calls == 0


def test_native_impersonating_thread_is_denied_without_changing_process_identity(fixture):
    api, path = fixture
    impersonate = api.a.ImpersonateSelf
    impersonate.argtypes, impersonate.restype = [W.DWORD], W.BOOL
    revert = api.a.RevertToSelf
    revert.argtypes, revert.restype = [], W.BOOL
    before = api.identity()
    assert impersonate(2), "synthetic same-user impersonation failed"
    try:
        with pytest.raises(KeyAccessError) as error:
            api.identity()
        assert error.value.outcome is Outcome.DENIED
    finally:
        assert revert(), "impersonation restoration failed"
    assert api.identity() == before


def test_native_interactive_query_is_closed_boolean_or_safe_unavailable(fixture):
    api, path = fixture
    # Do not lock, unlock, sign out, switch desktops or require an interactive CI runner.
    try:
        result = api.interactive(api.identity().session)
        assert type(result) is bool
    except KeyAccessError as error:
        assert str(error) in {o.value for o in Outcome}


def test_native_revocation_preserves_selected_and_unrelated_files(fixture):
    api, path = fixture
    other = path.with_name("unrelated-synthetic-key")
    other.write_bytes(b"unrelated-synthetic-material")
    resolver, store, runner, ref, handle = enroll(api, path)
    store.revoke_selection(ref, owner_authorized=True)
    assert resolver.invoke(handle, **request()).outcome is Outcome.REVOKED
    assert path.read_bytes() == CANARY and other.read_bytes() == b"unrelated-synthetic-material"
