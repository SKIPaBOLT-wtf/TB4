"""Actual protected Windows/Linux authority metadata; callbacks never authenticate or send RPC."""
import json
import os
import pytest

from tb4.commissioning_state import Setup
from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.credential_persistence import export_private, restore_private
from tb4.key_policy import KeyAccessError
from tb4.private_settings import native_settings
from tests.security.test_private_settings_native import fixture, protect_fixture, SUPPORTED

pytestmark = pytest.mark.skipif(not SUPPORTED, reason="Actual Windows/Linux authority-purpose protection")
INSTALLATION = "00000000-0000-4000-8000-000000000229"
TARGET = "00000000-0000-4000-8000-000000000228"
TRUST = "e" * 64
CANARY = b"synthetic-native-authority-key-never-copy"
AUTH = frozenset({Purpose.FOLDER_AUTHORITY})
THREE = frozenset({Purpose.FETCHER_STATUS, Purpose.FETCHER_START, Purpose.FOLDER_PROBE})
FOUR = THREE | AUTH


class Runner:
    authorities = 0
    probes = 0
    fetchers = 0
    saved = None
    reply = Outcome.SUCCEEDED
    lost = False

    def verify_target(self, target, trust):
        return target == TARGET and trust == TRUST

    def folder_authority(self, key, target, trust):
        assert target == TARGET and trust == TRUST
        key.recheck()
        self.saved = key
        self.authorities += 1
        if self.lost:
            raise RuntimeError("SYNTHETIC_PRIVATE_AUTHORITY_CANARY")
        return self.reply

    def folder_probe(self, key, *_):
        key.recheck()
        self.probes += 1
        return Outcome.SUCCEEDED

    def fetcher_status(self, key, *_):
        key.recheck()
        self.fetchers += 1
        return Outcome.SUCCEEDED

    fetcher_start = fetcher_status


def pair(now=None, installation=INSTALLATION):
    clock = [100] if now is None else now
    if os.name == "nt":
        from tb4.windows_key_native import WindowsKeyNative
        from tb4.windows_credentials import WindowsKeyStore
        kind, native = WindowsKeyStore, WindowsKeyNative()
    else:
        from tb4.linux_key_native import LinuxKeyNative
        from tb4.linux_credentials import LinuxKeyStore
        kind, native = LinuxKeyStore, LinuxKeyNative()
    runner = Runner()
    store = kind(installation, native=native, runner=runner, clock=lambda: clock[0])
    return store, CredentialResolver(installation, store, clock=lambda: clock[0]), runner, clock


def selected(root, *, purposes=AUTH, installation=INSTALLATION):
    path = root.parent / "synthetic-authority-key"
    path.write_bytes(CANARY)
    protect_fixture(path)
    store, resolver, runner, now = pair(installation=installation)
    mode = dict(interactive_required=False) if os.name == "nt" else dict(
        access_mode="existing_key", launch_mode="headless")
    reference = store.select(path=str(path), target_id=TARGET, target_trust=TRUST,
        purposes=purposes, expires_at=200, owner_authorized=True, **mode)
    handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator=reference,
        purposes=purposes, expires_at=200, owner_authorized=True)
    return path, store, resolver, runner, now, reference, handle


def request(purpose=Purpose.FOLDER_AUTHORITY):
    return dict(purpose=purpose, target_id=TARGET, target_trust=TRUST)


def test_actual_native_four_scope_setup_restart_preserves_image_identity_history_and_closed_key(fixture, capsys):
    root, settings = fixture
    setup = Setup(settings, create=True)
    setup.choose({"role": "watchdog"})
    path, store, resolver, _, _, reference, handle = selected(
        root, purposes=FOUR, installation=setup.installation_id)
    setup.persist_credentials(store, resolver, [dict(handle=handle, target_id=TARGET,
        target_trust=TRUST, purposes=sorted(p.value for p in FOUR))])
    before = settings.read()
    reopened = Setup(native_settings(root))
    fresh, new, runner, _ = pair(installation=setup.installation_id)
    reopened.restore_credentials(fresh, new)
    assert export_private(fresh, new) == before.payload["credential_image"]
    assert new._bindings[handle].store_locator == reference
    for purpose in (Purpose.FOLDER_AUTHORITY, Purpose.FOLDER_PROBE,
                    Purpose.FETCHER_STATUS, Purpose.FETCHER_START):
        assert new.invoke(handle, **request(purpose)).outcome is Outcome.SUCCEEDED
    assert (runner.authorities, runner.probes, runner.fetchers) == (1, 1, 2)
    with pytest.raises(KeyAccessError): _ = runner.saved.handle
    assert native_settings(root).read() == before and path.read_bytes() == CANARY
    assert CANARY not in (root / "settings.json").read_bytes()
    report = reopened.status()
    assert not report["runtime_active"] and not report["automatic_replay"]
    assert all(v not in json.dumps(report) for v in (str(path), reference, handle, TRUST, TARGET))
    assert capsys.readouterr() == ("", "")


def test_actual_native_historical_three_scope_restart_cannot_acquire_authority(fixture):
    root, settings = fixture
    path, store, resolver, _, _, reference, handle = selected(root, purposes=THREE)
    image = export_private(store, resolver)
    settings.save({"registry": image}, expected_revision=0)
    before = settings.read()
    fresh, new, runner, _ = pair()
    restore_private(before.payload["registry"], fresh, new)
    assert export_private(fresh, new) == image and new._bindings[handle].store_locator == reference
    assert new.invoke(handle, **request()).outcome is Outcome.DENIED
    assert runner.authorities == runner.probes == runner.fetchers == 0
    assert native_settings(root).read() == before and path.read_bytes() == CANARY


@pytest.mark.parametrize("reply", ["lost", "raw"])
def test_actual_native_ambiguous_authority_callback_closes_handle_without_replay_or_profile_change(fixture, reply, capsys):
    root, settings = fixture
    path, store, resolver, runner, _, reference, handle = selected(root)
    settings.save({"registry": export_private(store, resolver)}, expected_revision=0)
    before = settings.read()
    if reply == "lost": runner.lost = True
    else: runner.reply = {"private": "SYNTHETIC_PRIVATE_AUTHORITY_CANARY"}
    report = resolver.invoke(handle, **request()).report()
    assert report == dict(outcome="UNKNOWN", retry_automatically=False, inspection_required=True)
    assert runner.authorities == 1 and runner.probes == runner.fetchers == 0
    with pytest.raises(KeyAccessError): _ = runner.saved.handle
    assert native_settings(root).read() == before and path.read_bytes() == CANARY
    assert all(v not in json.dumps(report) for v in (
        str(path), reference, handle, TRUST, "SYNTHETIC_PRIVATE_AUTHORITY_CANARY"))
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("change,expected", [
    ("rotated", Outcome.REVOKED), ("permissions", Outcome.DENIED),
    ("expired", Outcome.EXPIRED), ("binding", Outcome.REVOKED),
    ("selection", Outcome.REVOKED)])
def test_actual_native_restart_rechecks_lost_authority_credential_and_preserves_history(fixture, change, expected):
    root, settings = fixture
    path, store, resolver, runner, _, reference, handle = selected(root)
    assert resolver.invoke(handle, **request()).outcome is Outcome.SUCCEEDED
    if change == "binding": resolver.revoke(handle, owner_authorized=True)
    if change == "selection": store.revoke_selection(reference, owner_authorized=True)
    settings.save({"registry": export_private(store, resolver)}, expected_revision=0)
    before = settings.read()
    if change == "rotated": path.write_bytes(b"synthetic-later-authority-key")
    if change == "permissions": protect_fixture(path, broad=True)
    fresh, new, current, _ = pair([200] if change == "expired" else [100])
    restore_private(before.payload["registry"], fresh, new)
    assert new._bindings[handle].store_locator == reference
    assert new.capability(handle, **request()).outcome is expected
    assert new.invoke(handle, **request()).outcome is expected
    assert current.authorities == current.probes == current.fetchers == 0 and runner.authorities == 1
    with pytest.raises(KeyAccessError): _ = runner.saved.handle
    assert native_settings(root).read() == before


@pytest.mark.parametrize("purpose", [Purpose.FOLDER_PROBE, Purpose.FETCHER_STATUS, Purpose.FETCHER_START])
def test_actual_native_authority_only_scope_cannot_borrow_proof_or_fetcher_methods(fixture, purpose):
    root, settings = fixture
    path, store, resolver, runner, _, _, handle = selected(root)
    settings.save({"registry": export_private(store, resolver)}, expected_revision=0)
    before = settings.read()
    assert resolver.invoke(handle, **request(purpose)).outcome is Outcome.DENIED
    assert runner.authorities == runner.probes == runner.fetchers == 0
    assert native_settings(root).read() == before and path.read_bytes() == CANARY

