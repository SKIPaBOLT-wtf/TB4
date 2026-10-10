"""Inherited effect evidence, immediate ownership and native admission races."""
import copy
from dataclasses import replace
import hashlib
import json
from math import ceil
from pathlib import Path

import pytest

from tb4.commissioning_state import Setup
from tb4.configuration_contract import ConfigurationError, configuration
from tb4.drive.authority_transaction import OwnerGuard, RecordMutation
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.leadership import Leadership
from tb4.private_settings import PrivateSettings
from tb4.reconfiguration_effects import Effects, KEY, SLOT, SCHEMA, SCHEMA_SHA256, ledger
from tb4.reconfiguration_evidence import ProtectedEvidence
from tb4.reconfiguration_maintenance import Maintenance
from tb4.watchdog.checkpoint_store import NativeCheckpoint
from tb4.watchdog.leadership_runtime import Action, Capabilities, Checkpoint, Receipt, Work
from reconfiguration_controller_support import TRANSITION, resolution_archive
from reconfiguration_effects_support import guarded_system, runtime
from test_native_docs_transport import wire_document
from test_native_leadership import ACTORS, clock, tid
from tests.security.test_private_settings import MemoryNative


def acquire_fallback(value):
    setup = Setup(PrivateSettings(MemoryNative()),create=True)
    choices = value.setup.private_choices(); choices["descriptor"]["installation_id"] = setup.installation_id
    setup.choose(choices)
    leader = Leadership(value.flow.leader.backend,actor=setup.installation_id,
        enrollment={**value.flow.leader.enrollment,setup.installation_id:"synthetic-guarded-fallback"})
    incumbent = value.flow.leader.backend.read().document()["records"]["global.leadership"]["body"]
    sample = clock(ceil(incumbent["heartbeat_at"] + leader.profile.lease_stale_s))
    plan = leader.acquire(leader.observe(sample),transition=tid("guarded-fallback"))
    report = leader.commit(plan,mode="START"); assert report.outcome == "CONFIRMED"
    grant = leader.confirmed_grant(plan,report)
    checkpoint = NativeCheckpoint(PrivateSettings(MemoryNative()),installation_id=setup.installation_id,
        binding=leader.backend.binding,create=True,owner_authorized=True,initial=Checkpoint(grant=grant))
    effects = Effects(leader,checkpoint,PrivateSettings(MemoryNative()))
    baseline = ProtectedEvidence(PrivateSettings(MemoryNative()),installation_id=setup.installation_id,
        transition_id=TRANSITION)
    caps = Capabilities(setup.installation_id,True,True,frozenset(Action))
    context = replace(value.context,setup=setup,leadership=leader,checkpoint=checkpoint,effects=effects,
        store=PrivateSettings(MemoryNative()),baseline=baseline,clock=lambda:sample,capabilities=lambda:caps)
    return Maintenance(context),effects,context


def test_guarded_entry_reserves_native_runtime_and_changes_only_two_records():
    value = guarded_system()
    value.effects.ensure(value.checkpoint.read())
    before = copy.deepcopy(value.provider.store.document); profile = value.setup.store.read()
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    after = value.provider.store.document
    assert {key for key in before["records"] if before["records"][key] != after["records"][key]} == {SLOT,"global.settings"}
    assert value.checkpoint.read().maintenance == TRANSITION
    assert ledger(after["records"][SLOT])["barrier"]["local_clear"]
    assert value.setup.store.read() == profile
    decision,status = value.controller.proposal()
    assert not status["requires_resolution"]
    assert value.controller.resolve(decision,resolution_archive(value),owner_authorized=True) == "RESOLVED"


def test_external_unknown_survives_fallback_without_acknowledgements_or_replay():
    value = guarded_system(); runner,sample,scheduled = runtime(value)
    assert runner.tick()
    seen = []
    work = Work(Action.SSH,tid("guarded-ssh"),lambda *args:seen.append(args) or "UNKNOWN")
    assert runner.perform(work) == "UNKNOWN" and len(seen) == 1
    assert value.effects.receipt(Action.SSH)["outcome"] == "UNKNOWN"
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    adopter,effects,context = acquire_fallback(value)
    assert adopter.begin(owner_authorized=True) == "MAINTENANCE"
    decision,status = adopter.proposal()
    assert status["original_evidence_required"] and status["counts"]["SHARED_EFFECT_UNKNOWN"] == 1
    with pytest.raises(ConfigurationError,match="ORIGINAL_EVIDENCE_REQUIRED"):
        adopter.resolve(decision,ProtectedEvidence(PrivateSettings(MemoryNative()),
            installation_id=context.setup.installation_id,transition_id=TRANSITION),owner_authorized=True)
    assert value.checkpoint.read().receipts[0].outcome == "UNKNOWN" and len(seen) == 1
    assert effects.receipt(Action.SSH)["outcome"] == "UNKNOWN"


def test_covered_empty_fallback_can_explicitly_resolve_with_old_machine_unavailable():
    value = guarded_system(); assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    adopter,effects,context = acquire_fallback(value)
    commits = value.provider.store.commits
    assert adopter.begin(owner_authorized=True) == "MAINTENANCE"
    decision,status = adopter.proposal()
    assert not status["original_evidence_required"] and not status["requires_resolution"]
    archive = ProtectedEvidence(PrivateSettings(MemoryNative()),installation_id=context.setup.installation_id,
        transition_id=TRANSITION)
    assert adopter.resolve(decision,archive,owner_authorized=True) == "RESOLVED"
    assert value.provider.store.commits == commits
    assert Maintenance(context).require_resolved(archive) == decision
    from jsonschema import Draft202012Validator
    from tb4.reconfiguration_maintenance import WAL_SCHEMA
    schema = json.loads((Path(__file__).parents[2]/WAL_SCHEMA).read_bytes())
    assert Draft202012Validator(schema).is_valid(context.store.read().payload)


def test_lost_journal_reply_restarts_inspect_only_and_never_invokes_external_work():
    value = guarded_system(); runner,_,_ = runtime(value); assert runner.tick()
    value.effects.ensure(value.checkpoint.read())
    before = wire_document(value.provider.store.document,"guarded-stale-read")
    def lost():
        value.provider.store.on_read = lambda *args:before
        raise TimeoutError("SYNTHETIC_LOST_EFFECT_REPLY")
    value.provider.store.after_write = lost
    seen = []
    work = Work(Action.SSH,tid("not-invoked"),lambda *args:seen.append(args) or "COMPLETE")
    assert runner.perform(work) == "UNKNOWN" and not seen
    assert value.effects._state()[0]["pending"] is not None
    value.provider.store.after_write = value.provider.store.on_read = None
    commits = value.provider.store.commits
    resumed = Effects(value.flow.leader,value.checkpoint,value.effects.store)
    assert resumed.inspect() == "CONFIRMED" and value.provider.store.commits == commits
    assert runner.perform(work) == "UNKNOWN" and not seen
    assert resumed.receipt(Action.SSH)["outcome"] == "UNKNOWN"


def test_native_reservation_during_unknown_guard_cas_prevents_late_invocation():
    value = guarded_system(); runner,_,scheduled = runtime(value); assert runner.tick()
    value.effects.ensure(value.checkpoint.read())
    def reserve(_):
        value.provider.store.before_write = None
        value.checkpoint.reserve(TRANSITION,owner_authorized=True)
    value.provider.store.before_write = reserve
    seen = []
    with pytest.raises(ConfigurationError,match="MAINTENANCE"):
        runner.perform(Work(Action.SSH,tid("reservation-race"),lambda *args:seen.append(args) or "COMPLETE"))
    assert not seen and value.effects.receipt(Action.SSH)["outcome"] == "UNKNOWN"
    assert value.checkpoint.read().maintenance == TRANSITION
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    assert runner.tick() and not scheduled


def test_actual_late_reply_preserves_reservation_and_requires_fresh_local_evidence():
    value = guarded_system(); runner,_,_ = runtime(value); assert runner.tick()
    seen = []
    def invoke(*args):
        seen.append(args)
        assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
        return "COMPLETE"
    assert runner.perform(Work(Action.SSH,tid("late-complete"),invoke)) == "COMPLETE"
    assert value.checkpoint.read().maintenance == TRANSITION
    assert value.checkpoint.read().receipts[0].outcome == "COMPLETE"
    assert value.effects.receipt(Action.SSH)["outcome"] == "COMPLETE"
    decision,status = value.controller.proposal()
    assert status["counts"] == {"SHARED_EVIDENCE_REQUIRED":1}
    with pytest.raises(ConfigurationError,match="RESOLUTION_REQUIRED"):
        value.controller.resolve(decision,resolution_archive(value),owner_authorized=True)
    assert value.controller.refresh_local_evidence(owner_authorized=True) == "CONFIRMED"
    decision,status = value.controller.proposal(); assert not status["requires_resolution"]
    assert value.controller.resolve(decision,resolution_archive(value),owner_authorized=True) == "RESOLVED"
    assert len(seen) == 1


def test_normal_summary_plan_cannot_erase_guard_or_cross_concurrent_initialization():
    value = guarded_system(); snap = value.flow.leader.backend.read()
    owner = OwnerGuard(value.flow.grant.owner,value.flow.grant.epoch)
    row = dict(generation=1,operation_id=tid("ordinary-summary"),retention="RETAINED",body={"message":"synthetic"})
    old_plan = RecordMutation.prepare(snap,owner=owner,changes={SLOT:row},protect=set())
    value.effects.ensure(value.checkpoint.read())
    assert old_plan.evaluate(value.flow.leader.backend.read())[0] == "CONFLICT"
    with pytest.raises(AuthorityError,match="EFFECT_TRANSACTION_REQUIRED"):
        RecordMutation.prepare(value.flow.leader.backend.read(),owner=owner,changes={SLOT:row},protect=set())
    assert value.effects.receipt(Action.SSH) is None


def test_empty_later_owner_cannot_bootstrap_coverage_of_unobserved_old_effects():
    value = guarded_system(); adopter,effects,context = acquire_fallback(value)
    commits = value.provider.store.commits
    with pytest.raises(ConfigurationError,match="LEGACY_EVIDENCE_REQUIRED"):
        effects.ensure(context.checkpoint.read())
    assert value.provider.store.commits == commits and effects.store.read() is None


@pytest.mark.parametrize("retention",["BUSY","UNREAD","UNKNOWN"])
def test_occupied_unresolved_summary_cannot_be_reset_as_a_new_guard(retention):
    value = guarded_system()
    row = dict(generation=1,operation_id=tid("prior-summary-work"),retention=retention,body={"private":"SYNTHETIC"})
    value.provider.store.document["records"][SLOT] = copy.deepcopy(row)
    with pytest.raises(ConfigurationError,match="LEGACY_EVIDENCE_REQUIRED"):
        value.effects.ensure(value.checkpoint.read())
    assert value.provider.store.document["records"][SLOT] == row and value.effects.store.read() is None


def test_even_same_guard_normal_summary_update_cannot_conceal_unresolved_work():
    value = guarded_system(); value.effects.ensure(value.checkpoint.read())
    doc = value.flow.leader.backend.read().document()
    row = copy.deepcopy(doc["records"][SLOT]); row["body"]["ordinary_message"] = "synthetic"
    with pytest.raises(AuthorityError,match="EFFECT_TRANSACTION_REQUIRED"):
        RecordMutation.prepare(value.flow.leader.backend.read(),owner=OwnerGuard(value.flow.grant.owner,
            value.flow.grant.epoch),changes={SLOT:row},protect=set())
    assert value.provider.store.document == doc


@pytest.mark.parametrize("outcome",["COMPLETE","NO_WORK","UNKNOWN"])
def test_shared_terminal_binding_and_same_operation_are_not_replayed(outcome):
    value = guarded_system(); runner,_,_ = runtime(value); assert runner.tick()
    seen = []
    work = Work(Action.SCAN,tid("same-effect"),lambda *args:seen.append(args) or outcome)
    assert runner.perform(work) == outcome
    assert runner.perform(work) == outcome and len(seen) == 1
    assert value.effects.receipt(Action.SCAN)["outcome"] == outcome
    if outcome != "UNKNOWN":
        before = copy.deepcopy(value.provider.store.document)
        with pytest.raises(ConfigurationError,match="EFFECT_UNKNOWN"):
            value.effects.finish(value.flow.grant,Action.SCAN,tid("wrong-effect"),"COMPLETE")
        assert value.provider.store.document == before


def test_effect_schema_pin_and_complete_native_payload_agree():
    from jsonschema import Draft202012Validator
    value = guarded_system(); value.effects.ensure(value.checkpoint.read())
    raw = (Path(__file__).parents[2]/SCHEMA).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SCHEMA_SHA256
    validator = Draft202012Validator(json.loads(raw))
    assert validator.is_valid(value.effects.store.read().payload)
    assert validator.is_valid(ledger(value.provider.store.document["records"][SLOT]))
    corrupted = copy.deepcopy(value.effects.store.read().payload); corrupted["foreign"] = "SYNTHETIC_CANARY"
    assert not validator.is_valid(corrupted)
