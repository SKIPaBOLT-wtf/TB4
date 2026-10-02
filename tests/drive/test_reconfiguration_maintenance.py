"""Explicit maintenance/resolution/crash/fallback predicates, no live mutation."""
import copy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

import pytest

from tb4.ballpark import catalogue
from tb4.ballpark_records import shared
from tb4.configuration_contract import ConfigurationError, configuration
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.leadership import Leadership
from tb4.commissioning_state import Setup
from tb4.exchange_layout import encoded
from tb4.private_settings import PrivateSettings, SettingsError
from tb4.reconfiguration_evidence import ProtectedEvidence
from tb4.reconfiguration_maintenance import Maintenance, MaintenanceMutation, WAL_SCHEMA, WAL_SCHEMA_SHA256
from tb4.watchdog.leadership_runtime import Action, Capabilities, Checkpoint, Receipt
from reconfiguration_controller_support import TRANSITION, resolution_archive, restart, system
from test_native_docs_transport import wire_document
from test_native_leadership import ACTORS, clock, tid
from test_native_watchdog_startup import LocalCheckpoint
from tests.security.test_private_settings import MemoryNative


def test_enter_is_one_settings_cas_after_native_wal_and_preserves_every_other_record(capsys):
    value = system()
    before = copy.deepcopy(value.provider.store.document)
    profile = value.setup.store.read()
    commits, objects = value.provider.store.commits, copy.deepcopy(value.provider.created)
    def see_intent(_):
        saved = value.context.store.read()
        assert saved.payload["phase"] == "ENTERING" and saved.payload["pending"] is not None
        assert value.context.baseline.store.read() is not None
    value.provider.store.before_write = see_intent
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    assert value.provider.store.commits == commits + 1 and value.provider.created == objects
    after = value.provider.store.document
    assert {k for k in before["records"] if before["records"][k] != after["records"][k]} == {"global.settings"}
    assert shared(after) == catalogue(value.setup.private_choices()["descriptor"])
    assert value.setup.store.read() == profile
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("failure", ["not-owner-approved", "action", "typed-action", "root-access", "withdrawn", "schema-pin"])
def test_no_default_grant_or_authority_mutation_on_failed_prerequisite(failure):
    value = system()
    if failure == "action":
        value.caps[0] = replace(value.caps[0], actions=frozenset({Action.SCAN}))
    elif failure == "typed-action":
        value.caps[0] = replace(value.caps[0], actions=frozenset({"IDENTITY"}))
    elif failure == "root-access":
        value.provider.metadata[value.flow.port.root_id]["capabilities"]["canEdit"] = False
    elif failure == "withdrawn":
        value.source.catalog["profiles"][0]["status"] = "REVOKED"
        value.source.save()
    elif failure == "schema-pin":
        value.source.files[value.source.head][WAL_SCHEMA] = b"{}"
        value.source.catalog["profiles"][0]["files"][WAL_SCHEMA] = hashlib.sha256(b"{}").hexdigest()
        value.source.save()
    before = copy.deepcopy(value.provider.store.document)
    with pytest.raises(ConfigurationError):
        value.controller.begin(owner_authorized=failure != "not-owner-approved")
    assert value.provider.store.document == before and value.context.store.read() is None
    assert value.context.baseline.store.read() is None


@pytest.mark.parametrize("retention", ["BUSY", "UNREAD", "UNKNOWN"])
def test_explicit_checkbox_cannot_resolve_retained_work_or_erase_its_evidence(retention):
    value = system()
    row = dict(generation=7, operation_id="a" * 64, retention=retention, body={"private":"SYNTHETIC_CANARY"})
    value.provider.store.document["records"]["target.000.work"] = copy.deepcopy(row)
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    decision, status = value.controller.proposal()
    assert status["counts"]["SHARED_"+retention] == 1
    archive = resolution_archive(value)
    with pytest.raises(ConfigurationError, match="RESOLUTION_REQUIRED"):
        value.controller.resolve(decision, archive, owner_authorized=True)
    assert value.provider.store.document["records"]["target.000.work"] == row
    assert archive.store.read() is None
    preserved = value.context.baseline.store.read()
    assert preserved.payload["inspection"]["blockers"][0]["kind"] == "SHARED_"+retention


def test_unknown_local_effect_blocks_resolution_without_blocking_role_takeover():
    value = system()
    value.checkpoint.state = replace(value.checkpoint.state,
        receipts=(Receipt(Action.SSH, "b"*64, value.flow.grant.epoch, "UNKNOWN"),))
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    decision, status = value.controller.proposal()
    assert status["counts"]["LOCAL_EFFECT_UNKNOWN"] == 1
    with pytest.raises(ConfigurationError, match="RESOLUTION_REQUIRED"):
        value.controller.resolve(decision, resolution_archive(value), owner_authorized=True)
    candidate = Leadership(value.flow.leader.backend, actor=ACTORS[1],
                           enrollment=value.flow.leader.enrollment)
    plan = candidate.acquire(candidate.observe(clock(340)), transition=tid("maintenance-fallback"))
    assert candidate.commit(plan, mode="START").outcome == "CONFIRMED"
    assert configuration(value.provider.store.document)["phase"] == "MAINTENANCE"
    with pytest.raises(ConfigurationError, match="OWNER_SUPERSEDED"):
        value.controller.proposal()


def test_resolution_is_explicit_fresh_and_invalidated_by_new_work_not_heartbeat():
    value = system()
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    decision, status = value.controller.proposal()
    assert not status["requires_resolution"]
    archive = resolution_archive(value)
    with pytest.raises(ConfigurationError, match="OWNER_REQUIRED"):
        value.controller.resolve(decision, archive)
    plan = value.flow.leader.renew(value.flow.leader.observe(clock(240)), value.flow.grant,
                                  transition=tid("heartbeat-before-resolution"))
    assert value.flow.leader.commit(plan, mode="START").outcome == "CONFIRMED"
    assert value.controller.resolve(decision, archive, owner_authorized=True) == "RESOLVED"
    assert value.controller.require_resolved(archive) == decision
    value.provider.store.document["records"]["ingress.000"] = dict(generation=1,
        operation_id="f"*64, retention="UNKNOWN", body={"pending":True})
    value.provider.store.bump()
    with pytest.raises(ConfigurationError, match="RESOLUTION_CHANGED"):
        value.controller.require_resolved(archive)
    assert value.context.store.read().payload["phase"] == "RESOLVED"  # History is retained.


def test_stale_resolution_or_profile_replacement_cannot_be_approved():
    value = system()
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    decision, _ = value.controller.proposal()
    with pytest.raises(ConfigurationError, match="RESOLUTION_CHANGED"):
        value.controller.resolve(replace(decision, work_sha256="0"*64), resolution_archive(value), owner_authorized=True)
    value.setup._save({**value.setup._payload,"reason":"REVALIDATION_REQUIRED"})
    with pytest.raises(ConfigurationError, match="PROFILE_CHANGED"):
        value.controller.proposal()


def test_lost_shared_reply_restarts_in_inspect_only_and_confirms_after_takeover():
    value = system()
    before = wire_document(value.provider.store.document, "stale-maintenance-read")
    def lost():
        value.provider.store.on_read = lambda count,response:before
        raise TimeoutError("SYNTHETIC_PROVIDER_CANARY")
    value.provider.store.after_write = lost
    assert value.controller.begin(owner_authorized=True) == "UNKNOWN"
    assert value.context.store.read().payload["pending"] is not None
    commits = value.provider.store.commits
    value.provider.store.after_write = value.provider.store.on_read = None
    candidate = Leadership(value.flow.leader.backend, actor=ACTORS[1],
                           enrollment=value.flow.leader.enrollment)
    plan = candidate.acquire(candidate.observe(clock(340)), transition=tid("lost-maintenance-takeover"))
    assert candidate.commit(plan, mode="START").outcome == "CONFIRMED"
    resumed = restart(value)
    with pytest.raises(ConfigurationError, match="INSPECT_REQUIRED"):
        resumed.begin(owner_authorized=True)
    assert resumed.inspect() == "MAINTENANCE"
    assert value.provider.store.commits == commits + 1
    with pytest.raises(ConfigurationError, match="OWNER_SUPERSEDED"):
        resumed.proposal()


def test_unknown_before_apply_is_not_replayed_by_inspection():
    value = system()
    value.provider.store.raise_write = 503
    before = copy.deepcopy(value.provider.store.document)
    result = value.controller.begin(owner_authorized=True)
    assert result in {"UNKNOWN","UNAVAILABLE"}
    sends = len(value.provider.store.calls)
    value.provider.store.raise_write = None
    assert restart(value).inspect() == "UNKNOWN"
    assert len(value.provider.store.calls) == sends and value.provider.store.document == before


@pytest.mark.parametrize("failure", ["stage","promote","readback"])
def test_local_intent_crash_never_reaches_remote_and_recovers_same_payload(failure):
    value = system()
    value.state_native.failure = failure
    commits = value.provider.store.commits
    with pytest.raises((SettingsError,ConfigurationError)):
        value.controller.begin(owner_authorized=True)
    assert value.provider.store.commits == commits
    before = copy.deepcopy(value.state_native.files)
    value.state_native.failure = None
    resumed = restart(value)
    if failure != "readback":
        with pytest.raises(ConfigurationError, match="OWNER_REQUIRED"):
            resumed.recover_local()
        assert resumed.recover_local(owner_authorized=True) == "INSPECT_REQUIRED"
    assert resumed.inspect() == "UNKNOWN"
    assert value.provider.store.commits == commits
    assert set(value.state_native.files) == {"settings.json"}
    assert value.context.store.read().payload["pending"] is not None


def test_current_wal_schema_pin_and_formed_payload_agree():
    from jsonschema import Draft202012Validator
    value = system()
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    raw = (Path(__file__).parents[2] / WAL_SCHEMA).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == WAL_SCHEMA_SHA256
    validator = Draft202012Validator(json.loads(raw))
    state = value.context.store.read().payload
    assert validator.is_valid(state)
    assert not validator.is_valid({**state,"foreign":"SYNTHETIC_PRIVATE_CANARY"})
    assert not validator.is_valid({**state,"configuration_revision":True})
    decision,_ = value.controller.proposal()
    assert value.controller.resolve(decision,resolution_archive(value),owner_authorized=True) == "RESOLVED"
    assert validator.is_valid(value.context.store.read().payload)


def test_fresh_fallback_adopts_role_and_marker_without_claiming_missing_old_local_evidence():
    value = system()
    value.checkpoint.state = replace(value.checkpoint.state,
        receipts=(Receipt(Action.SSH,"9"*64,value.flow.grant.epoch,"UNKNOWN"),))
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    new_setup = Setup(PrivateSettings(MemoryNative()),create=True)
    choices = value.setup.private_choices()
    choices["descriptor"]["installation_id"] = new_setup.installation_id
    new_setup.choose(choices)
    enrollment = {**value.flow.leader.enrollment,
                  new_setup.installation_id:"synthetic-fallback"}
    leader = Leadership(value.flow.leader.backend,actor=new_setup.installation_id,enrollment=enrollment)
    plan = leader.acquire(leader.observe(clock(340)),transition=tid("new-installation-fallback"))
    report = leader.commit(plan,mode="START")
    assert report.outcome == "CONFIRMED"
    grant = leader.confirmed_grant(plan,report)
    baseline = ProtectedEvidence(PrivateSettings(MemoryNative()),installation_id=new_setup.installation_id,
                                 transition_id=TRANSITION)
    checkpoint = LocalCheckpoint(new_setup.installation_id,Checkpoint(grant=grant))
    caps = Capabilities(new_setup.installation_id,True,True,frozenset(Action))
    context = replace(value.context,setup=new_setup,leadership=leader,checkpoint=checkpoint,
        store=PrivateSettings(MemoryNative()),baseline=baseline,clock=lambda:clock(340),capabilities=lambda:caps)
    adopter = Maintenance(context)
    commits = value.provider.store.commits
    assert adopter.begin(owner_authorized=True) == "MAINTENANCE"
    assert value.provider.store.commits == commits
    decision,status = adopter.proposal()
    assert status["original_evidence_required"] and not status["counts"]
    archive = ProtectedEvidence(PrivateSettings(MemoryNative()),installation_id=new_setup.installation_id,
                                transition_id=TRANSITION)
    with pytest.raises(ConfigurationError,match="ORIGINAL_EVIDENCE_REQUIRED"):
        adopter.resolve(decision,archive,owner_authorized=True)
    assert archive.store.read() is None
    assert value.checkpoint.state.receipts[0].outcome == "UNKNOWN"


def test_changed_incumbent_label_refuses_before_acquisition_without_authority_write():
    value = system()
    before = copy.deepcopy(value.provider.store.document)
    commits = value.provider.store.commits
    candidate = Leadership(value.flow.leader.backend, actor=ACTORS[1], enrollment={
        **value.flow.leader.enrollment, value.setup.installation_id: "synthetic-wrong-label"})
    with pytest.raises(AuthorityError, match="LEADERSHIP_IDENTITY"):
        candidate.observe(clock(340))
    assert value.provider.store.document == before
    assert value.provider.store.commits == commits


def test_malformed_pending_cannot_recover_or_change_protected_identity():
    value = system()
    value.provider.store.raise_write = 503
    value.controller.begin(owner_authorized=True)
    current = value.context.store.read()
    corrupted = copy.deepcopy(current.payload)
    corrupted["pending"]["owner"] = ACTORS[2]
    value.context.store.save(corrupted,expected_revision=current.revision)
    sends = len(value.provider.store.calls)
    with pytest.raises(ConfigurationError,match="WAL"):
        restart(value).inspect()
    assert len(value.provider.store.calls) == sends
