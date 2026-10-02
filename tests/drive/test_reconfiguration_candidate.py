"""Actual same-first-run candidate, retained history and failure boundaries."""
import copy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json

import pytest

from tb4.commissioning_checks import Environment
from tb4.commissioning_state import Setup
from tb4.configuration_contract import ConfigurationError
from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.desktop.reconfiguration import CandidateController
from tb4.private_settings import SettingsError
from tb4.reconfiguration_candidate import Candidate, SCHEMA, SCHEMA_SHA256, seed
from reconfiguration_candidate_support import system
from test_credential_contract import FixtureStore, TARGET, TRUST


def test_original_complete_payload_and_history_retained_with_one_authority(capsys):
    s = system(); v = s.value
    original = copy.deepcopy(v.profile_native.files)
    document = copy.deepcopy(v.provider.store.document)
    created, commits = copy.deepcopy(v.provider.created), v.provider.store.commits
    assert s.candidate.begin(owner_authorized=True)["phase"] == "STAGED"
    archive = s.context.archive.read()
    assert archive.revision == 1 and archive.previous is None
    assert archive.payload["profile"] == v.setup._payload
    assert {"discovery","ballpark_draft","ballpark_publication"} <= set(archive.payload["profile"])
    model = Setup(s.context.profile)
    assert model._payload == seed(v.setup._payload)
    assert model.installation_id == v.setup.installation_id
    assert model._payload["operations"] == v.setup._payload["operations"]
    assert v.profile_native.files == original and v.provider.store.document == document
    assert v.provider.store.commits == commits and v.provider.created == created
    assert capsys.readouterr() == ("", "")


def test_actual_first_run_choice_review_restart_and_descriptor_timing_change():
    s = system(); c,v = s.candidate,s.value
    original = v.setup.store.read(); document = copy.deepcopy(v.provider.store.document)
    c.begin(owner_authorized=True)
    timing = copy.deepcopy(v.setup.private_choices()["timing"])
    timing["standby_s"] += 1
    c.choose({"network_scope":["198.51.100.0/24"],"timing":timing},owner_authorized=True)
    assert c.review(s.checker)["settings_validated"]
    certificate = c.require_validated(s.checker)
    assert certificate.validation.pin.runtime == v.context.runtime
    assert certificate.decision == v.controller.require_resolved(s.context.resolution)
    restarted = Candidate(s.context)
    assert not restarted.view()["settings_validated"]
    assert not Setup(s.context.profile).status()["settings_validated"]
    assert restarted.review(s.checker)["settings_validated"]
    assert v.setup.store.read() == original and v.provider.store.document == document


def test_default_desktop_activation_remains_denied_and_old_profile_unchanged():
    s = system(); old = s.value.setup.store.read(); s.candidate.begin(owner_authorized=True)
    controller = CandidateController(s.candidate,lambda:s.checker)
    assert controller.refresh()["settings_validated"]
    result = controller.activate()
    assert result["reason"] == "ACTIVATION_NOT_AUTHORIZED" and not result["runtime_active"]
    assert not result["settings_validated"] and not result["automatic_replay"]
    assert s.value.setup.store.read() == old


@pytest.mark.parametrize("patch", [{"role":"fetcher"},{"storage":None},
    {"storage_request":{"mode":"NATIVE_DOCS","location":"synthetic-new-root"}}])
def test_owner_cannot_replace_identity_backend_or_root_in_this_candidate_unit(patch):
    s = system(); s.candidate.begin(owner_authorized=True)
    before = s.context.profile.read(); original = s.value.setup.store.read()
    with pytest.raises(ConfigurationError,match="CANDIDATE_IDENTITY"):
        s.candidate.choose(patch,owner_authorized=True)
    assert s.context.profile.read() == before and s.value.setup.store.read() == original


def test_arbitrary_ready_checker_and_saved_ready_flag_do_not_qualify_access():
    s = system(); s.candidate.begin(owner_authorized=True)
    before = s.context.profile.read()
    with pytest.raises(ConfigurationError,match="CANDIDATE_CHECKER"):
        s.candidate.review(SimpleNamespace(validate=lambda _:{"ready":True}))
    assert s.context.profile.read() == before
    model = Setup(s.context.profile)
    model._save({**model._payload,"state":"SETTINGS_READY","reason":"SETTINGS_VALIDATED"})
    assert not Candidate(s.context).view()["settings_validated"]
    s.checker.environment = lambda:Environment("OTHER","OTHER","USER","EXTERNAL","UNQUALIFIED")
    with pytest.raises(ConfigurationError,match="REVALIDATION_REQUIRED"):
        s.candidate.require_validated(s.checker)
    assert s.value.setup.store.read().payload != s.context.profile.read().payload


def test_exact_candidate_credentials_rechecked_after_ready_without_execution():
    s = system(); s.candidate.begin(owner_authorized=True)
    old = s.value.setup.store.read()
    store = FixtureStore(s.value.setup.installation_id)
    resolver = CredentialResolver(store.installation_id,store,clock=lambda:store.now)
    handle = resolver.enroll(target_id=TARGET,target_trust=TRUST,store_locator="synthetic-slot",
        purposes=frozenset({Purpose.FETCHER_STATUS}),expires_at=200,owner_authorized=True)
    s.candidate.choose({"credentials":[dict(handle=handle,target_id=TARGET,target_trust=TRUST,
        purposes=[Purpose.FETCHER_STATUS.value])]},owner_authorized=True)
    s.checker.credentials = resolver
    assert s.candidate.review(s.checker)["settings_validated"]
    store.state = Outcome.REVOKED
    assert s.candidate.review(s.checker)["reason"] == "CREDENTIAL_UNAVAILABLE"
    with pytest.raises(ConfigurationError,match="REVALIDATION_REQUIRED"):
        s.candidate.require_validated(s.checker)
    assert store.executions == 0 and s.value.setup.store.read() == old
    assert handle not in json.dumps(s.candidate.view())


@pytest.mark.parametrize("fault",["access","metadata","readback","withdrawn","schema"])
def test_new_access_readback_and_pin_failure_never_promotes_original(fault):
    s = system(); s.candidate.begin(owner_authorized=True)
    v = s.value; original = copy.deepcopy(v.profile_native.files)
    created,commits = copy.deepcopy(v.provider.created),v.provider.store.commits
    if fault == "access":
        v.provider.metadata[v.flow.port.root_id]["capabilities"]["canEdit"] = False
    elif fault == "metadata":
        v.provider.metadata[v.flow.port.root_id]["trashed"] = True
    elif fault == "readback":
        v.provider.store.on_read = lambda *_: (_ for _ in ()).throw(TimeoutError("SYNTHETIC_READBACK_FAILURE"))
    elif fault == "withdrawn":
        v.source.catalog["profiles"][0]["status"] = "REVOKED"; v.source.save()
    else:
        v.source.files[v.source.head][SCHEMA] = b"{}"
        v.source.catalog["profiles"][0]["files"][SCHEMA] = hashlib.sha256(b"{}").hexdigest(); v.source.save()
    with pytest.raises((ConfigurationError,SettingsError)):
        s.candidate.require_validated(s.checker)
    assert v.profile_native.files == original and v.provider.created == created
    assert v.provider.store.commits == commits


@pytest.mark.parametrize("fault",["history","nonce","derived-package","boolean-revision","extra-field"])
def test_saved_candidate_tampering_cannot_erase_history_or_construct_readiness(fault):
    s = system(); s.candidate.begin(owner_authorized=True)
    original = s.value.setup.store.read(); calls = s.history_calls.copy()
    store = s.context.profile if fault in {"history","nonce","derived-package"} else s.context.transaction
    snap = store.read(); changed = copy.deepcopy(snap.payload)
    if fault == "history":
        changed["operations"] = {}
    elif fault == "nonce":
        changed["setup_nonce"] = "e"*64
    elif fault == "derived-package":
        changed["discovery"] = copy.deepcopy(original.payload["discovery"])
    elif fault == "boolean-revision":
        changed["configuration_revision"] = True
    else:
        changed["ready"] = True
    store.save(changed,expected_revision=snap.revision)
    with pytest.raises((ConfigurationError,SettingsError)):
        Candidate(s.context).require_validated(s.checker)
    assert s.value.setup.store.read() == original and s.history_calls == calls


def test_alias_and_rewritten_archive_are_refused_without_old_configuration_change():
    s = system(); original = s.value.setup.store.read()
    with pytest.raises(ConfigurationError,match="STORE_ALIAS"):
        Candidate(replace(s.context,profile=s.value.setup.store))
    with pytest.raises(ConfigurationError,match="STORE_ALIAS"):
        Candidate(replace(s.context,archive=s.value.context.store))
    s.candidate.begin(owner_authorized=True)
    snap = s.context.archive.read()
    s.context.archive.save(snap.payload,expected_revision=snap.revision)
    with pytest.raises(ConfigurationError,match="CANDIDATE_ARCHIVE"):
        s.candidate.review(s.checker)
    assert s.value.setup.store.read() == original


def test_new_unread_work_invalidates_explicit_resolution_and_candidate_review():
    s = system(); s.candidate.begin(owner_authorized=True)
    original = s.value.setup.store.read(); staged = s.context.profile.read()
    row = s.value.provider.store.document["records"]["target.000.work"]
    row.update(generation=7,operation_id="a"*64,retention="UNREAD",body={"private":"SYNTHETIC_CANARY"})
    with pytest.raises(ConfigurationError,match="RESOLUTION_CHANGED"):
        s.candidate.choose({"network_scope":[]},owner_authorized=True)
    assert s.value.setup.store.read() == original and s.context.profile.read() == staged
    assert row["generation"] == 7 and row["retention"] == "UNREAD"


@pytest.mark.parametrize("which",["transaction","archive","profile"])
def test_local_staging_cut_is_same_candidate_inspection_not_remote_replay(which):
    s = system(); store = getattr(s.context,which)
    original = s.value.setup.store.read(); commits = s.value.provider.store.commits
    store.native.failure = "promote"
    with pytest.raises(SettingsError,match="COMMIT_UNCONFIRMED"):
        s.candidate.begin(owner_authorized=True)
    pending = store.native.files["settings.pending"]
    store.native.failure = None
    with pytest.raises(ConfigurationError,match="OWNER_REQUIRED"):
        s.candidate.recover_local(which)
    assert s.candidate.recover_local(which,owner_authorized=True) == "INSPECT_REQUIRED"
    assert store.native.files["settings.json"] == pending
    assert Candidate(s.context).resume_staging(owner_authorized=True)["phase"] == "STAGED"
    assert s.value.setup.store.read() == original and s.value.provider.store.commits == commits


def test_schema_exact_pin_native_metadata_and_nonidentifying_status():
    from jsonschema import Draft202012Validator
    s = system(); s.candidate.begin(owner_authorized=True)
    raw = (Path(__file__).parents[2]/SCHEMA).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SCHEMA_SHA256
    assert Draft202012Validator(json.loads(raw)).is_valid(s.context.transaction.read().payload)
    view = s.candidate.view()
    assert set(view) == {"phase","settings_validated","runtime_active","automatic_replay"}
    assert s.value.setup.installation_id not in json.dumps(view)
    assert "SYNTHETIC" not in repr(s.candidate.context)
