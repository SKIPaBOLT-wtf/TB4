"""Closed authority scope; portable policy fixtures never authenticate or dispatch RPC."""
from dataclasses import replace
import json
import pytest

from tb4.commissioning_state import Setup
from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.credential_persistence import export_private, restore_private
from tb4.enrollment_records import own_credentials
from tb4.linux_credentials import LinuxKeyStore
from tb4.private_settings import PrivateSettings
from tests.security.test_linux_credentials import Native, Runner, INSTALLATION, TARGET, TRUST, USER
from tests.security.test_private_settings import MemoryNative

AUTH = frozenset({Purpose.FOLDER_AUTHORITY})
THREE = frozenset({Purpose.FETCHER_STATUS, Purpose.FETCHER_START, Purpose.FOLDER_PROBE})
FOUR = THREE | AUTH
CANARY = "SYNTHETIC_PRIVATE_AUTHORITY_CANARY"


class AuthorityRunner(Runner):
    authorities = 0
    probes = 0

    def folder_authority(self, key, target, trust):
        assert self.native.held == 1 and target == TARGET and trust == TRUST
        key.recheck()
        self.authorities += 1
        if self.lost:
            raise RuntimeError(CANARY)
        return self.result

    def folder_probe(self, key, target, trust):
        self.probes += 1
        return Outcome.SUCCEEDED


def pair(installation=INSTALLATION, *, missing=False, clock=None):
    native = Native()
    runner = Runner(native) if missing else AuthorityRunner(native)
    now = [100] if clock is None else clock
    store = LinuxKeyStore(installation, native=native, runner=runner, clock=lambda: now[0])
    return store, CredentialResolver(installation, store, clock=lambda: now[0]), native, runner, now


def system(*, purposes=AUTH, mode="headless", missing=False, installation=INSTALLATION):
    store, resolver, native, runner, now = pair(installation, missing=missing)
    reference = store.select(path="/synthetic/private/authority-key", target_id=TARGET,
        target_trust=TRUST, purposes=purposes, expires_at=200, access_mode="existing_key",
        launch_mode=mode, owner_authorized=True)
    handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator=reference,
        purposes=purposes, expires_at=200, owner_authorized=True)
    return store, resolver, native, runner, now, reference, handle


def request(purpose=Purpose.FOLDER_AUTHORITY):
    return dict(purpose=purpose, target_id=TARGET, target_trust=TRUST)


@pytest.mark.parametrize("mode", ["desktop", "headless"])
def test_authority_scope_uses_only_its_fixed_callback_with_one_held_key(mode):
    _, resolver, native, runner, _, _, handle = system(mode=mode)
    assert resolver.capability(handle, **request()).available
    assert resolver.invoke(handle, **request()).outcome is Outcome.SUCCEEDED
    assert runner.authorities == 1 and runner.calls == runner.probes == native.held == 0


@pytest.mark.parametrize("purpose", [
    Purpose.FETCHER_STATUS, Purpose.FETCHER_START, Purpose.FOLDER_PROBE,
    "FOLDER_AUTHORITY", None, 7])
def test_authority_only_scope_refuses_other_and_untyped_uses_before_native_access(purpose):
    _, resolver, native, runner, _, _, handle = system()
    native.on_open = lambda: pytest.fail("ungranted purpose opened a native key")
    assert resolver.invoke(handle, **request(purpose)).outcome is Outcome.DENIED
    assert runner.authorities == runner.calls == runner.probes == native.held == 0


@pytest.mark.parametrize("purposes", [
    frozenset({Purpose.FOLDER_PROBE}),
    frozenset({Purpose.FETCHER_STATUS, Purpose.FETCHER_START}), THREE])
def test_historical_scope_restart_keeps_exact_image_and_does_not_grant_authority(purposes):
    store, resolver, _, _, _, reference, handle = system(purposes=purposes)
    image = export_private(store, resolver)
    fresh, new, native, runner, _ = pair()
    restore_private(image, fresh, new)
    native.on_open = lambda: pytest.fail("restored historical scope opened a native key")
    assert export_private(fresh, new) == image
    assert new._bindings[handle].store_locator == reference
    assert new.invoke(handle, **request()).outcome is Outcome.DENIED
    assert runner.authorities == runner.calls == runner.probes == native.held == 0


def test_missing_authority_callback_denies_without_fetcher_or_proof_fallback():
    _, resolver, native, runner, _, _, handle = system(missing=True)
    assert resolver.invoke(handle, **request()).outcome is Outcome.DENIED
    assert runner.calls == native.held == 0


@pytest.mark.parametrize("field", ["target_id", "target_trust"])
def test_foreign_authority_pin_does_not_reach_any_callback(field):
    _, resolver, native, runner, _, _, handle = system()
    args = request()
    args[field] = "00000000-0000-4000-8000-000000000124" if field == "target_id" else "c" * 64
    assert resolver.invoke(handle, **args).outcome is Outcome.MISMATCHED
    assert runner.authorities == runner.calls == runner.probes == native.held == 0


@pytest.mark.parametrize("change,expected", [
    ("version", Outcome.REVOKED), ("expiry", Outcome.EXPIRED),
    ("binding", Outcome.REVOKED), ("selection", Outcome.REVOKED),
    ("principal", Outcome.DENIED), ("session", Outcome.DENIED), ("trust", Outcome.DENIED)])
def test_prior_authority_capability_does_not_authorize_later_changed_native_state(change, expected):
    store, resolver, native, runner, now, reference, handle = system()
    assert resolver.capability(handle, **request()).available
    if change == "version": native.version = 2
    if change == "expiry": now[0] = 200
    if change == "binding": resolver.revoke(handle, owner_authorized=True)
    if change == "selection": store.revoke_selection(reference, owner_authorized=True)
    if change == "principal": native.user = replace(USER, uid=1002)
    if change == "session": native.user = replace(USER, session=72)
    if change == "trust": runner.trusted = False
    assert resolver.invoke(handle, **request()).outcome is expected
    assert runner.authorities == runner.calls == runner.probes == native.held == 0


@pytest.mark.parametrize("reply", ["lost", "raw"])
def test_ambiguous_authority_callback_is_unknown_once_without_payload_or_retry(reply, capsys):
    _, resolver, native, runner, _, reference, handle = system()
    if reply == "lost": runner.lost = True
    else: runner.result = {"private": CANARY}
    report = resolver.invoke(handle, **request()).report()
    assert report == dict(outcome="UNKNOWN", retry_automatically=False, inspection_required=True)
    assert runner.authorities == 1 and runner.calls == runner.probes == native.held == 0
    assert all(v not in json.dumps(report) for v in (CANARY, reference, handle, TRUST, TARGET))
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("purposes", [AUTH, FOUR])
def test_private_authority_metadata_round_trip_preserves_original_refs_versions_and_scopes(purposes):
    store, resolver, _, runner, _, reference, handle = system(purposes=purposes)
    image = export_private(store, resolver)
    fresh, new, native, current, _ = pair()
    restore_private(image, fresh, new)
    assert export_private(fresh, new) == image
    assert new._bindings[handle].store_locator == reference
    assert new.capability(handle, **request()).available
    assert runner.authorities == current.authorities == current.calls == current.probes == native.held == 0


@pytest.mark.parametrize("purposes", [AUTH, FOUR])
def test_setup_authority_image_retains_identity_history_and_original_fetcher_report(purposes):
    memory = MemoryNative()
    setup = Setup(PrivateSettings(memory), create=True)
    setup.choose({"role": "watchdog"})
    store, resolver, _, _, _, reference, handle = system(
        purposes=purposes, installation=setup.installation_id)
    setup.persist_credentials(store, resolver, [dict(handle=handle, target_id=TARGET,
        target_trust=TRUST, purposes=sorted(p.value for p in purposes))])
    before = setup.snapshot
    reopened = Setup(PrivateSettings(memory))
    fresh, new, _, runner, _ = pair(setup.installation_id)
    reopened.restore_credentials(fresh, new)
    assert reopened.snapshot == before and export_private(fresh, new) == before.payload["credential_image"]
    assert new._bindings[handle].store_locator == reference
    assert new.invoke(handle, **request()).outcome is Outcome.SUCCEEDED
    summary = own_credentials(reopened, new, TARGET)
    assert set(summary) == {"FETCHER_STATUS", "FETCHER_START"}
    assert all(row["available"] is (purposes == FOUR) for row in summary.values())
    assert "FOLDER_AUTHORITY" not in json.dumps(summary) and "FOLDER_PROBE" not in json.dumps(summary)
    assert runner.authorities == 1 and runner.calls == runner.probes == 0
    assert reopened.snapshot == before and not reopened.status()["runtime_active"]

