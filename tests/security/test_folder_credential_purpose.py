"""Synthetic fixed-use policy; actual borrowed handles are tested separately."""
import json
import pytest

from tb4.commissioning_state import Setup
from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.credential_persistence import export_private, restore_private
from tb4.enrollment_records import own_credentials
from tb4.linux_credentials import LinuxKeyStore
from tb4.private_settings import PrivateSettings
from tests.security.test_linux_credentials import Native, Runner, INSTALLATION, TARGET, TRUST
from tests.security.test_private_settings import MemoryNative

ONLY = frozenset({Purpose.FOLDER_PROBE})
ALL = frozenset(Purpose)
FOREIGN = "00000000-0000-4000-8000-000000000124"
CANARY = "SYNTHETIC_PRIVATE_FOLDER_PROBE_CANARY"


class ProbeRunner(Runner):
    probes = 0

    def folder_probe(self, key, target, trust):
        assert self.native.held == 1 and target == TARGET and trust == TRUST
        key.recheck()
        self.probes += 1
        if self.lost:
            raise RuntimeError(CANARY)
        return self.result


def pair(installation=INSTALLATION, *, legacy=False, clock=None):
    native = Native()
    runner = Runner(native) if legacy else ProbeRunner(native)
    now = clock if clock is not None else [100]
    store = LinuxKeyStore(installation, native=native, runner=runner, clock=lambda: now[0])
    resolver = CredentialResolver(installation, store, clock=lambda: now[0])
    return store, resolver, native, runner, now


def system(*, installation=INSTALLATION, legacy=False, purposes=ONLY, mode="headless"):
    store, resolver, native, runner, now = pair(installation, legacy=legacy)
    reference = store.select(path="/synthetic/private/folder-probe-key", target_id=TARGET,
        target_trust=TRUST, purposes=purposes, expires_at=200, access_mode="existing_key",
        launch_mode=mode, owner_authorized=True)
    handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator=reference,
        purposes=purposes, expires_at=200, owner_authorized=True)
    return store, resolver, native, runner, now, reference, handle


def request(purpose=Purpose.FOLDER_PROBE, target=TARGET, trust=TRUST):
    return dict(purpose=purpose, target_id=target, target_trust=trust)


@pytest.mark.parametrize("mode", ["desktop", "headless"])
def test_folder_scope_calls_exactly_its_fixed_method_and_never_fetcher(mode):
    _, resolver, native, runner, _, _, handle = system(mode=mode)
    assert resolver.capability(handle, **request()).available
    assert resolver.invoke(handle, **request()).outcome is Outcome.SUCCEEDED
    assert runner.probes == 1 and runner.calls == 0 and native.held == 0


@pytest.mark.parametrize("purpose", [Purpose.FETCHER_STATUS, Purpose.FETCHER_START, "FOLDER_PROBE", None])
def test_folder_only_binding_cannot_borrow_another_or_untyped_purpose(purpose):
    _, resolver, native, runner, _, _, handle = system()
    assert resolver.invoke(handle, **request(purpose)).outcome is Outcome.DENIED
    assert runner.probes == runner.calls == native.held == 0


@pytest.mark.parametrize("change", ["target", "trust"])
def test_foreign_target_or_trust_never_reaches_fixed_probe(change):
    _, resolver, native, runner, _, _, handle = system()
    args = request(target=FOREIGN) if change == "target" else request(trust="c" * 64)
    assert resolver.invoke(handle, **args).outcome is Outcome.MISMATCHED
    assert runner.probes == runner.calls == native.held == 0


@pytest.mark.parametrize("change,expected", [
    ("version", Outcome.REVOKED), ("expiry", Outcome.EXPIRED),
    ("binding", Outcome.REVOKED), ("selection", Outcome.REVOKED)])
def test_previously_ready_does_not_authorize_changed_credential(change, expected):
    store, resolver, native, runner, now, reference, handle = system()
    assert resolver.capability(handle, **request()).available
    if change == "version": native.version = 2
    if change == "expiry": now[0] = 200
    if change == "binding": resolver.revoke(handle, owner_authorized=True)
    if change == "selection": store.revoke_selection(reference, owner_authorized=True)
    assert resolver.invoke(handle, **request()).outcome is expected
    assert runner.probes == runner.calls == native.held == 0


def test_legacy_runner_without_folder_method_is_denied_and_never_falls_through_to_start():
    _, resolver, native, runner, _, _, handle = system(legacy=True)
    assert resolver.invoke(handle, **request()).outcome is Outcome.DENIED
    assert runner.calls == native.held == 0


@pytest.mark.parametrize("reply", ["lost", "raw"])
def test_ambiguous_fixed_reply_is_closed_unknown_once_without_private_output(reply, capsys):
    _, resolver, native, runner, _, _, handle = system()
    if reply == "lost": runner.lost = True
    else: runner.result = CANARY
    report = resolver.invoke(handle, **request()).report()
    assert report == dict(outcome="UNKNOWN", retry_automatically=False, inspection_required=True)
    assert runner.probes == 1 and runner.calls == native.held == 0
    assert CANARY not in json.dumps(report) and capsys.readouterr() == ("", "")


@pytest.mark.parametrize("purposes", [ONLY, ALL])
def test_closed_purpose_metadata_restart_keeps_original_handles_and_versions(purposes):
    store, resolver, _, _, _, reference, handle = system(purposes=purposes)
    image = export_private(store, resolver)
    new_store, new_resolver, _, runner, _ = pair()
    restore_private(image, new_store, new_resolver)
    assert export_private(new_store, new_resolver) == image
    assert new_resolver._bindings[handle].store_locator == reference
    assert new_resolver.capability(handle, **request()).available
    assert runner.probes == runner.calls == 0


@pytest.mark.parametrize("purposes", [ONLY, ALL])
def test_actual_setup_metadata_accepts_closed_folder_scope_but_fetcher_summary_keeps_its_two_purposes(purposes):
    native_profile = MemoryNative()
    model = Setup(PrivateSettings(native_profile), create=True)
    model.choose({"role": "watchdog"})
    store, resolver, _, _, _, reference, handle = system(
        installation=model.installation_id, purposes=purposes)
    record = dict(handle=handle, target_id=TARGET, target_trust=TRUST,
                  purposes=sorted(p.value for p in purposes))
    model.persist_credentials(store, resolver, [record])
    before = model._payload["credential_image"]
    reopened = Setup(PrivateSettings(native_profile))
    new_store, new_resolver, _, runner, _ = pair(model.installation_id)
    reopened.restore_credentials(new_store, new_resolver)
    assert reopened._payload["credential_image"] == before
    assert new_resolver._bindings[handle].store_locator == reference
    summary = own_credentials(reopened, new_resolver, TARGET)
    assert set(summary) == {"FETCHER_STATUS", "FETCHER_START"}
    assert all(row["available"] is (purposes == ALL) for row in summary.values())
    assert "FOLDER_PROBE" not in json.dumps(summary)
    assert runner.probes == runner.calls == 0 and not reopened.status()["runtime_active"]
