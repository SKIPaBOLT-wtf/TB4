"""Synthetic state-machine tests; real native storage tests are separate."""
import copy
from dataclasses import asdict
import hashlib
import json
from types import SimpleNamespace

import pytest

from tb4.commissioning_state import Setup, DenyActivation, Reconciliation, Validation
from tb4.commissioning_checks import Environment, Prerequisites
from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.drive.commissioning import SetupSpec
from tb4.drive.commissioning_bootstrap import AuthorityHandle
from tb4.exchange_layout import Capacity
from tb4.instructions import CATALOG, ENTRY, REPOSITORY, REPOSITORY_ID, Head, RuntimeFacts
from tb4.private_settings import PrivateSettings, SettingsError
from test_private_settings import MemoryNative
from test_ballpark_contract import fixture as descriptor_fixture
from test_credential_contract import FixtureStore, TARGET, TRUST

DOMAIN = "00000000-0000-4000-8000-000000000001"
ACTOR = "00000000-0000-4000-8000-000000000002"
ENVIRONMENT = Environment("WINDOWS", "X64", "USER", "DESKTOP_SESSION", "INTERACTIVE")
FACTS = RuntimeFacts("a" * 40, 2, frozenset({"setup-v2"}))


class Source:
    """Synthetic qualified source for testing actual RP007 selection."""
    def __init__(self):
        self.status, self.fail, self.calls = "RELEASED", False, 0
    def resolve(self, repository, repository_id, ref, request_id):
        self.calls += 1
        if self.fail:
            raise ValueError("SYNTHETIC_PRIVATE_CANARY")
        return Head(repository, repository_id, "1" * 40, request_id, True)
    def read(self, repository, repository_id, commit, path):
        instructions = "skill/tb4/operations/synthetic.md"
        if path != CATALOG:
            return b"synthetic"
        digest = hashlib.sha256(b"synthetic").hexdigest()
        return json.dumps(dict(schema_version=1, repository=REPOSITORY, repository_id=REPOSITORY_ID,
            entry=ENTRY, entry_sha256=digest, profiles=[dict(id="synthetic", status=self.status,
            builds=[FACTS.build_commit], protocol=2, requires=["setup-v2"], instructions=instructions,
            files={instructions:digest})])).encode()


def storage_record():
    spec = SetupSpec("synthetic-root", DOMAIN, "b" * 64, ACTOR, "NATIVE_DOCS", Capacity(1,1,1,1))
    return dict(spec=asdict(spec), authority=AuthorityHandle("synthetic-authority", "c" * 64, "tab").record())


class Storage:
    def __init__(self):
        self.calls, self.fail = 0, False
    def verify(self, record):
        self.calls += 1
        if self.fail:
            raise SettingsError("STORAGE_UNAVAILABLE")
        assert record == storage_record()


def system(*, configured=True):
    native = MemoryNative()
    model = Setup(PrivateSettings(native), create=True)
    if configured:
        descriptor = descriptor_fixture()
        descriptor["installation_id"] = model.installation_id
        model.choose(dict(role="watchdog", storage=storage_record(), network_scope=["192.0.2.0/24"],
                          descriptor=descriptor))
    source, storage = Source(), Storage()
    store = FixtureStore(model.installation_id)
    resolver = CredentialResolver(model.installation_id, store, clock=lambda: store.now)
    checker = Prerequisites(environment=lambda: ENVIRONMENT, storage=storage, credentials=resolver,
                            source=source, runtime=FACTS, clock=lambda: 100)
    return model, native, checker, source, storage, resolver, store


def test_persist_identity_once_cancel_resume_and_restart_ready_invalidation():
    model, native, checker, *_ = system()
    original, nonce = model.installation_id, model._payload["setup_nonce"]
    assert model.review(checker)["settings_validated"]
    restarted = Setup(PrivateSettings(native), create=True)
    assert restarted.installation_id == original and restarted._payload["setup_nonce"] == nonce
    assert restarted.status()["reason"] == "REVALIDATION_REQUIRED"
    assert not restarted.status()["settings_validated"]
    restarted.cancel()
    cancelled = Setup(PrivateSettings(native))
    assert cancelled.review(checker)["state"] == "CANCELLED"
    cancelled.resume()
    assert cancelled.review(checker)["state"] == "SETTINGS_READY"
    assert cancelled.installation_id == original


def test_only_missing_owner_choices_are_requested_before_probes():
    model, _, checker, source, storage, *_ = system(configured=False)
    assert model.missing_choices() == ("role", "storage", "network_scope")
    model.choose({"role":"fetcher", "network_scope":[]})
    assert model.review(checker)["missing_choices"] == ["storage"]
    assert storage.calls == source.calls == 0
    model.choose({"storage":storage_record()})
    assert model.review(checker)["reason"] == "DESCRIPTOR_REQUIRED"
    assert model.missing_choices() == ()


def test_default_activation_remains_independently_denied():
    model, _, checker, *_ = system()
    result = model.activate(checker, DenyActivation())
    assert result["reason"] == "ACTIVATION_NOT_AUTHORIZED" and not result["runtime_active"]


def test_activation_refreshes_pin_and_never_enters_after_revocation():
    model, _, checker, source, *_ = system()
    assert model.review(checker)["settings_validated"]
    source.status = "REVOKED"
    calls = []
    activation = SimpleNamespace(enter=lambda *_:calls.append("entered"))
    assert model.activate(checker, activation)["reason"] == "INSTRUCTIONS_UNAVAILABLE"
    assert not calls and source.calls == 2


def test_synthetic_authorized_activation_checks_again_after_review():
    model, _, checker, source, *_ = system()
    model.review(checker)
    calls = []
    def enter(payload, validation):
        assert type(validation) is Validation and validation.pin.runtime == FACTS
        assert payload["installation_id"] == model.installation_id
        calls.append("entered")
    assert model.activate(checker, SimpleNamespace(enter=enter))["runtime_active"]
    assert len(calls) == 1 and source.calls == 2


@pytest.mark.parametrize("stage", ["environment", "storage", "descriptor", "instructions"])
def test_failed_prerequisite_has_closed_reason_and_never_enters(stage):
    model, _, checker, source, storage, *_ = system()
    if stage == "environment":
        checker.environment = lambda: {"ready":True}
    elif stage == "storage":
        storage.fail = True
    elif stage == "descriptor":
        model.choose({"descriptor":None})
    else:
        source.fail = True
    called = []
    result = model.activate(checker, SimpleNamespace(enter=lambda *_:called.append(1)))
    assert result["state"] == "BLOCKED" and not called
    assert "SYNTHETIC_PRIVATE_CANARY" not in json.dumps(result)


@pytest.mark.parametrize("state", [Outcome.ABSENT, Outcome.DENIED, Outcome.LOCKED, Outcome.EXPIRED,
                                  Outcome.REVOKED, Outcome.STORE_UNAVAILABLE])
def test_exact_opaque_credential_is_rechecked_without_use(state):
    model, _, checker, _, _, resolver, store = system()
    handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator="synthetic-slot",
        purposes=frozenset({Purpose.FETCHER_STATUS}), expires_at=200, owner_authorized=True)
    model.choose({"credentials":[dict(handle=handle,target_id=TARGET,target_trust=TRUST,
                                     purposes=[Purpose.FETCHER_STATUS.value])]})
    assert model.review(checker)["settings_validated"]
    store.state = state
    assert model.review(checker)["reason"] == "CREDENTIAL_UNAVAILABLE"
    assert store.executions == 0 and handle not in json.dumps(model.status())


def test_saved_opaque_handle_does_not_fabricate_missing_restart_binding():
    model, native, checker, _, _, resolver, _ = system()
    handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator="synthetic-slot",
        purposes=frozenset({Purpose.FETCHER_START}), expires_at=200, owner_authorized=True)
    model.choose({"credentials":[dict(handle=handle,target_id=TARGET,target_trust=TRUST,
                                     purposes=[Purpose.FETCHER_START.value])]})
    model.review(checker)
    checker.credentials = CredentialResolver(model.installation_id, FixtureStore(model.installation_id),
                                             clock=lambda:100)
    restarted = Setup(PrivateSettings(native))
    assert restarted.review(checker)["reason"] == "CREDENTIAL_UNAVAILABLE"
    assert restarted.private_choices()["credentials"][0]["handle"] == handle


def test_unknown_side_effect_survives_cancel_restart_and_cannot_replay():
    model, native, checker, *_ = system()
    calls, operation = [], "e" * 64
    def lost_reply():
        assert Setup(PrivateSettings(native))._payload["operations"][operation] == "UNKNOWN"
        calls.append(1)
        raise OSError("SYNTHETIC_PRIVATE_CANARY")
    model.perform_once(operation, lost_reply, owner_authorized=True)
    model.cancel()
    restarted = Setup(PrivateSettings(native))
    restarted.resume()
    assert restarted.review(checker)["reason"] == "UNKNOWN_OPERATION"
    with pytest.raises(SettingsError, match="INSPECT_REQUIRED"):
        restarted.perform_once(operation, lost_reply, owner_authorized=True)
    with pytest.raises(SettingsError, match="INSPECT_REQUIRED"):
        restarted.choose({"network_scope":[]})
    restarted.reconcile(operation, lambda _:Reconciliation.CONFIRMED)
    assert restarted.review(checker)["settings_validated"]
    with pytest.raises(SettingsError, match="INSPECT_REQUIRED"):
        restarted.perform_once(operation, lost_reply, owner_authorized=True)
    assert calls == [1]


def test_failed_persist_cannot_call_external_action():
    model, native, *_ = system()
    native.failure = "promote"
    calls = []
    with pytest.raises(SettingsError):
        model.perform_once("e"*64, lambda:calls.append(1), owner_authorized=True)
    assert not calls


def test_unapproved_action_or_invented_inspection_cannot_advance():
    model, *_ = system()
    calls = []
    with pytest.raises(SettingsError, match="NOT_AUTHORIZED"):
        model.perform_once("e"*64, lambda:calls.append(1))
    assert not calls
    model.perform_once("e"*64, lambda:None, owner_authorized=True)
    with pytest.raises(SettingsError, match="INSPECTION_INVALID"):
        model.reconcile("e"*64, lambda _:True)


def test_stale_instance_and_saved_ready_flag_cannot_activate():
    model, native, checker, *_ = system()
    model.review(checker)
    other = Setup(PrivateSettings(native))
    other.cancel()
    assert not model.status()["settings_validated"]
    calls = []
    with pytest.raises(SettingsError, match="CHANGED_RELOAD"):
        model.activate(checker, SimpleNamespace(enter=lambda *_:calls.append(1)))
    assert not calls


@pytest.mark.parametrize("patch", [
    {"secret":"SYNTHETIC_PRIVATE_CANARY"}, {"role":"admin"},
    {"network_scope":["192.0.2.1/24"]}, {"network_scope":["192.0.2.0/24"]*2},
    {"storage":{"ready":True}}, {"credentials":[{"password":"SYNTHETIC_PRIVATE_CANARY"}]},
    {"timing":{"lease_stale_s":1}},
], ids=["extra-field","role","host-bits","duplicate-scope","fake-store","secret","timing"])
def test_bad_or_secret_bearing_choices_never_persist(patch):
    model, native, *_ = system()
    before = copy.deepcopy(native.files)
    with pytest.raises(SettingsError) as error:
        model.choose(patch)
    assert native.files == before and "CANARY" not in str(error.value)


def test_safe_rollback_appends_revision_and_never_restores_readiness():
    model, _, checker, *_ = system()
    model.review(checker)
    model.choose({"network_scope":[]})
    revision, identity = model.snapshot.revision, model.installation_id
    with pytest.raises(SettingsError, match="STOPPED"):
        model.rollback_choices(stopped=False)
    model.rollback_choices(stopped=True)
    assert model.snapshot.revision == revision+1 and model.installation_id == identity
    assert model.private_choices()["network_scope"] == ["192.0.2.0/24"]
    assert not model.status()["settings_validated"]


def test_rollback_cannot_erase_recorded_external_effect():
    model, *_ = system()
    model.perform_once("e"*64, lambda:None, owner_authorized=True)
    with pytest.raises(SettingsError, match="ROLLBACK_UNSAFE"):
        model.rollback_choices(stopped=True)


def test_status_and_exception_outputs_omit_all_private_choices(capsys):
    model, _, checker, *_ = system()
    model.review(checker)
    public = json.dumps(model.status()) + repr(model.snapshot)
    for canary in (model.installation_id, "192.0.2.", "synthetic-root", "Duplicate display"):
        assert canary not in public
    assert capsys.readouterr() == ("", "")
