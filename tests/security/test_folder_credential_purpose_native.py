"""Actual native keys/private metadata; no authenticated SSH or live endpoint."""
import json
import os
import pytest

from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.credential_persistence import export_private, restore_private
from tb4.key_policy import KeyAccessError
from tb4.private_settings import native_settings
from tests.security.test_private_settings_native import fixture, protect_fixture, SUPPORTED

pytestmark = pytest.mark.skipif(not SUPPORTED, reason="Actual Windows/Linux protected credential purpose")
INSTALLATION = "00000000-0000-4000-8000-000000000227"
TARGET = "00000000-0000-4000-8000-000000000228"
TRUST = "e" * 64
CANARY = b"synthetic-native-folder-probe-key-never-copy"


class Runner:
    probes = 0
    fetchers = 0
    saved = None
    lost = False

    def verify_target(self, target, trust):
        return target == TARGET and trust == TRUST

    def folder_probe(self, key, target, trust):
        assert target == TARGET and trust == TRUST
        self.saved = key
        key.recheck()
        self.probes += 1
        if self.lost:
            raise RuntimeError("SYNTHETIC_PRIVATE_CANARY")
        return Outcome.SUCCEEDED

    def fetcher_status(self, *_):
        self.fetchers += 1
        return Outcome.SUCCEEDED

    fetcher_start = fetcher_status


def pair(now=None):
    clock = now if now is not None else [100]
    if os.name == "nt":
        from tb4.windows_key_native import WindowsKeyNative
        from tb4.windows_credentials import WindowsKeyStore
        kind, native = WindowsKeyStore, WindowsKeyNative()
    else:
        from tb4.linux_key_native import LinuxKeyNative
        from tb4.linux_credentials import LinuxKeyStore
        kind, native = LinuxKeyStore, LinuxKeyNative()
    runner = Runner()
    store = kind(INSTALLATION, native=native, runner=runner, clock=lambda: clock[0])
    return store, CredentialResolver(INSTALLATION, store, clock=lambda: clock[0]), runner, clock


def selected(root, *, purposes=frozenset({Purpose.FOLDER_PROBE})):
    path = root.parent / "synthetic-folder-probe-key"
    path.write_bytes(CANARY)
    protect_fixture(path)
    store, resolver, runner, clock = pair()
    args = dict(interactive_required=False) if os.name == "nt" else dict(
        access_mode="existing_key", launch_mode="headless")
    reference = store.select(path=str(path), target_id=TARGET, target_trust=TRUST,
        purposes=purposes, expires_at=200, owner_authorized=True, **args)
    handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator=reference,
        purposes=purposes, expires_at=200, owner_authorized=True)
    return path, store, resolver, runner, clock, reference, handle


def request():
    return dict(purpose=Purpose.FOLDER_PROBE, target_id=TARGET, target_trust=TRUST)


def test_actual_native_three_scope_image_restarts_with_one_borrowed_fixed_probe(fixture, capsys):
    root, settings = fixture
    path, store, resolver, _, _, reference, handle = selected(root, purposes=frozenset({
        Purpose.FETCHER_STATUS, Purpose.FETCHER_START, Purpose.FOLDER_PROBE}))
    image = export_private(store, resolver)
    settings.save({"registry": image}, expected_revision=0)
    before = native_settings(root).read()
    new_store, new_resolver, runner, _ = pair()
    restore_private(before.payload["registry"], new_store, new_resolver)
    assert export_private(new_store, new_resolver) == image
    assert new_resolver._bindings[handle].store_locator == reference
    report = new_resolver.invoke(handle, **request()).report()
    assert report["outcome"] == "SUCCEEDED" and runner.probes == 1 and runner.fetchers == 0
    with pytest.raises(KeyAccessError): _ = runner.saved.handle
    assert native_settings(root).read() == before and path.read_bytes() == CANARY
    assert CANARY not in (root / "settings.json").read_bytes()
    assert all(value not in json.dumps(report) for value in (str(path), reference, handle, TRUST))
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("change,expected", [
    ("rotated", Outcome.REVOKED), ("permissions", Outcome.DENIED),
    ("expired", Outcome.EXPIRED), ("revoked", Outcome.REVOKED)])
def test_actual_native_restart_refuses_lost_folder_credential_without_probe_or_profile_reset(fixture, change, expected):
    root, settings = fixture
    path, store, resolver, runner, _, reference, handle = selected(root)
    assert resolver.invoke(handle, **request()).outcome is Outcome.SUCCEEDED
    if change == "revoked": resolver.revoke(handle, owner_authorized=True)
    settings.save({"registry": export_private(store, resolver)}, expected_revision=0)
    before = native_settings(root).read()
    if change == "rotated": path.write_bytes(b"synthetic-changed-folder-probe-key")
    if change == "permissions": protect_fixture(path, broad=True)
    new_store, new_resolver, new_runner, _ = pair([200] if change == "expired" else [100])
    restore_private(before.payload["registry"], new_store, new_resolver)
    assert new_resolver._bindings[handle].store_locator == reference
    assert new_resolver.capability(handle, **request()).outcome is expected
    assert new_resolver.invoke(handle, **request()).outcome is expected
    assert new_runner.probes == new_runner.fetchers == 0 and runner.probes == 1
    assert native_settings(root).read() == before


def test_actual_native_lost_probe_reply_closes_handle_and_preserves_key_private_history(fixture, capsys):
    root, settings = fixture
    path, store, resolver, runner, _, reference, handle = selected(root)
    settings.save({"registry": export_private(store, resolver)}, expected_revision=0)
    before = settings.read()
    runner.lost = True
    report = resolver.invoke(handle, **request()).report()
    assert report == dict(outcome="UNKNOWN", retry_automatically=False, inspection_required=True)
    assert runner.probes == 1 and runner.fetchers == 0
    with pytest.raises(KeyAccessError): _ = runner.saved.handle
    assert settings.read() == before and path.read_bytes() == CANARY
    assert all(value not in json.dumps(report) for value in (
        str(path), reference, handle, TRUST, "SYNTHETIC_PRIVATE_CANARY"))
    assert capsys.readouterr() == ("", "")
