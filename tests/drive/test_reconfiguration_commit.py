"""Actual SDK/native first-run C4 publication; synthetic authorities only."""
import copy
from dataclasses import asdict,replace
import hashlib
import json
from pathlib import Path

import pytest

from tb4.ballpark_records import shared
from tb4.configuration_contract import ConfigurationError,configuration,require_dispatch
from tb4.drive.authority_transaction import OwnerGuard,RecordMutation
from tb4.drive.commissioning import digest,frozen_plan
from tb4.drive.docs_authority import AuthorityError,NativeDocsAuthority
from tb4.exchange_layout import encoded,validate_document
from tb4.private_settings import SettingsError
from tb4.reconfiguration_candidate import SCHEMA
from tb4.reconfiguration_commit import ConfigurationCommit,ConfigurationMutation,SCHEMA_SHA256,work_sha
from tb4.reconfiguration_effects import SLOT,ledger,changed_row
from tb4.watchdog.leadership_runtime import Action
from reconfiguration_commit_support import system
from reconfiguration_rebind_support import fallback,TARGET
from test_native_docs_transport import wire_document
from test_native_leadership import clock


def test_actual_publication_advances_coherent_descriptor_configuration_and_preserves_work_profile_media():
    s=system();v=s.value;before=copy.deepcopy(v.provider.store.document);original=v.setup.store.read()
    metadata=copy.deepcopy(v.provider.metadata);media=copy.deepcopy(s.post_root.rebind.media);writes=len(v.provider.store.calls)
    assert s.commit.begin(s.checker,owner_authorized=True,decided_at=220)=="PREPARED"
    assert v.provider.store.document==before and v.setup.store.read()==original
    assert s.commit.advance(s.checker,owner_authorized=True)=="PUBLISHED"
    after=v.provider.store.document
    assert configuration(after)=={**configuration(before),"phase":"ACTIVE","revision":configuration(before)["revision"]+1}
    assert shared(after)["revision"]==shared(before)["revision"]+1
    assert {k for k in before["records"] if before["records"][k]!=after["records"][k]}=={
        "global.settings","global.registry",SLOT,"target.000.catalogue"}
    old_effects,new_effects=ledger(before["records"][SLOT]),ledger(after["records"][SLOT])
    assert new_effects=={k:x for k,x in old_effects.items() if k!="root_plan"}
    assert after["records"]["global.commissioning"]==before["records"]["global.commissioning"]
    assert work_sha(after)==work_sha(before) and v.provider.metadata==metadata and s.post_root.rebind.media==media
    assert v.setup.store.read()==original and len(v.provider.store.calls)==writes+1
    assert ConfigurationCommit(s.context).advance(s.checker,owner_authorized=True)=="PUBLISHED"
    assert len(v.provider.store.calls)==writes+1 and len(s.post_root.rebind.moves)==3
    with pytest.raises(ConfigurationError):require_dispatch(after)
    with pytest.raises(ConfigurationError):require_dispatch(after,configuration(before)["revision"])
    # The revision itself is not a trusted admission port. Default composition
    # supplies no admission callback and remains closed until its later unit.
    assert not s.post_root.candidate.original.status()["runtime_active"]


@pytest.mark.parametrize("after",[False,True])
def test_actual_lost_reply_restarts_inspect_only_without_same_operation_repeat(after):
    s=system();v=s.value;store=v.provider.store;original=v.setup.store.read()
    s.commit.begin(s.checker,owner_authorized=True,decided_at=220);writes=len(store.calls);on_read=store.on_read
    def lost():
        if after:store.on_read=lambda *_:(_ for _ in ()).throw(TimeoutError("SYNTHETIC_COMMIT_READ_LOST"))
        raise TimeoutError("SYNTHETIC_COMMIT_REPLY_LOST")
    if after:store.after_write=lost
    else:store.before_write=lambda _:lost()
    assert s.commit.advance(s.checker,owner_authorized=True)=="UNKNOWN"
    store.after_write=store.before_write=None;store.on_read=on_read
    fresh=ConfigurationCommit(s.context)
    assert fresh._state()[0]["dispatch"]=="INVOKING"
    assert fresh.advance(s.checker,owner_authorized=True)==("PUBLISHED" if after else "UNKNOWN")
    assert fresh.inspect()==("PUBLISHED" if after else "UNKNOWN")
    assert len(store.calls)==writes+1 and v.setup.store.read()==original


@pytest.mark.parametrize("fault",["source","permission","clock","caps","force","work","profile","stage","unknown","receipt"])
def test_actual_final_guards_refuse_without_shared_write_or_original_profile_reset(fault):
    s=system();v=s.value;store=v.provider.store
    s.commit.begin(s.checker,owner_authorized=True,decided_at=220);writes=len(store.calls);original=v.setup.store.read()
    if fault=="source":v.source.catalog["profiles"][0]["status"]="REVOKED";v.source.save()
    elif fault=="permission":v.provider.metadata[TARGET]["capabilities"]["canEdit"]=False
    elif fault=="clock":object.__setattr__(s.post_root.rebind.rebind.ctx,"clock",lambda:clock(trusted=False))
    elif fault=="caps":object.__setattr__(s.post_root.rebind.rebind.ctx,"capabilities",lambda:None)
    elif fault=="force":store.document["records"]["global.force_request"].update(retention="BUSY",body={"synthetic":True})
    elif fault=="work":store.document["records"]["target.000.status"]["body"]={"synthetic":True}
    elif fault=="profile":v.setup.choose({"network_scope":v.setup.private_choices()["network_scope"]})
    elif fault=="stage":s.post_root.candidate.choose({"network_scope":["192.0.2.0/24"]},owner_authorized=True)
    elif fault=="unknown":
        row=store.document["records"][SLOT];value=ledger(row);value["entries"]["SSH"]=dict(
            owner=v.setup.installation_id,epoch=1,operation_id="b"*64,outcome="UNKNOWN")
        store.document["records"][SLOT]=changed_row(row,value)
    else:store.document["records"]["global.commissioning"]["body"]["reconfiguration"]["root_plan_sha256"]="b"*64
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):
        s.commit.advance(s.checker,owner_authorized=True)
    assert len(store.calls)==writes
    if fault!="profile":assert v.setup.store.read()==original


def test_actual_stage_change_during_final_first_run_probe_cannot_be_published():
    s=system();v=s.value;s.commit.begin(s.checker,owner_authorized=True,decided_at=220)
    original=v.setup.store.read();writes=len(v.provider.store.calls);environment=s.checker.environment;changed=[]
    def late():
        if not changed:
            changed.append(True)
            s.post_root.candidate.choose({"network_scope":["192.0.2.0/24"]},owner_authorized=True)
        return environment()
    s.checker.environment=late
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):
        s.commit.advance(s.checker,owner_authorized=True)
    assert changed and len(v.provider.store.calls)==writes and v.setup.store.read()==original


@pytest.mark.parametrize("after",[False,True])
def test_actual_first_cas_takeover_supersedes_before_and_preserves_readonly_after_without_ack(after):
    s=system();v=s.value;store=v.provider.store;s.commit.begin(s.checker,owner_authorized=True,decided_at=220)
    taken=[];writes=len(store.calls)
    def take(*_):
        store.before_write=store.after_write=None;taken.append(fallback(s.post_root.rebind))
    if after:store.after_write=take
    else:store.before_write=take
    assert s.commit.advance(s.checker,owner_authorized=True)==("PUBLISHED" if after else "SUPERSEDED")
    assert taken and store.document["records"]["global.leadership"]["body"]["epoch"]==2
    assert s.commit.inspect()==("PUBLISHED" if after else "UNKNOWN")
    assert len(store.calls)==writes+2  # One C4 attempt and one first-CAS election.
    assert configuration(store.document)["phase"]==("ACTIVE" if after else "MAINTENANCE")


def test_closed_named_schema_alias_and_ordinary_writers_cannot_publish_or_consume_effects():
    from jsonschema import Draft202012Validator
    s=system();raw=(Path(__file__).parents[2]/SCHEMA).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SCHEMA_SHA256
    with pytest.raises(ConfigurationError,match="STORE_ALIAS"):
        ConfigurationCommit(replace(s.context,store=s.post_root.context.profile))
    s.commit.begin(s.checker,owner_authorized=True,decided_at=220);frame=s.context.store.read().payload
    schema=json.loads(raw);validator=Draft202012Validator(schema["$defs"]["configurationCommit"])
    assert validator.is_valid(frame) and not validator.is_valid({**frame,"foreign":True})
    assert not Draft202012Validator(schema).is_valid(frame)
    assert len(frame["pin"]["files"])<=17
    snap=s.value.context.leadership.backend.read()
    with pytest.raises(AuthorityError):RecordMutation.prepare(snap,owner=OwnerGuard(s.value.setup.installation_id,1),
        changes={"global.settings":snap.document()["records"]["global.settings"]},protect=set())
    s.commit.advance(s.checker,owner_authorized=True)
    snap=s.value.context.leadership.backend.read();row=snap.document()["records"][SLOT]
    with pytest.raises(AuthorityError):RecordMutation.prepare(snap,owner=OwnerGuard(s.value.setup.installation_id,1),
        changes={SLOT:{**row,"generation":row["generation"]+1}},protect=set())


def large_commit_plan(pin):
    """Actual compact plan/frame budgets only; no physical/provider claim."""
    from test_reconfiguration_rebind import large_plan
    prior,before=large_plan();doc=prior.evaluate(before)[1]
    # This fixture publishes one previously discovered device in a 64-slot
    # domain. All 129 bindings are protected without copying full work.
    from reconfiguration_effects_support import guarded_system
    from tb4.drive.commissioning_bootstrap import AuthorityHandle
    reference_system=guarded_system();reference=reference_system.provider.store.document
    for index in range(64):
        body=doc["records"][f"target.{index:03d}.catalogue"]["body"]
        del body["synthetic_retained_unicode"]
        body["enrollment"]="UNENROLLED"
    for key in ("global.registry","global.settings"):
        doc["records"][key]=copy.deepcopy(reference["records"][key])
    doc["records"]["global.settings"]["body"]["configuration"]=prior._validate()[2]["configuration"]
    doc["records"]["target.000.catalogue"]["body"].update({k:copy.deepcopy(v) for k,v in
        reference["records"]["target.000.catalogue"]["body"].items() if k!="artifacts"})
    doc["records"]["target.063.work"]=dict(generation=19,operation_id=digest(["retained-budget-work"]),
        retention="RETAINED",body={"synthetic_retained_unicode":"ą"*300})
    validate_document(doc)
    shared(doc)
    descriptor=copy.deepcopy(reference_system.setup.private_choices()["descriptor"]);descriptor["revision"]+=1
    # Pure shared fixture digest is the decision's candidate digest, with no
    # runtime/private profile claim; actual runtime binds the private digest.
    owner=prior.owner;config=configuration(doc);spec=prior._validate()[0]
    target=replace(spec,root_id=TARGET)
    handle=AuthorityHandle(before.binding.document_id,digest([
        target.mode,target.root_id,target.domain_id,before.binding.document_id,before.binding.tab_id]),before.binding.tab_id)
    storage=dict(spec=asdict(target),authority=handle.record(),root_transition=config["transition_id"])
    decision=dict(kind="LOCAL_OWNER_CONFIRMATION",at=220,candidate_digest=digest(descriptor))
    decision["id"]=digest(["reconfiguration-commit",config["transition_id"],decision["candidate_digest"],digest(pin),owner.owner,owner.epoch,220])
    snap=NativeDocsAuthority(None,before.binding)._decode(wire_document(doc))
    plan=ConfigurationMutation.prepare(snap,owner,storage=storage,descriptor=descriptor,
        timing=doc["records"]["global.settings"]["body"]["timing"],pin=pin,decision=decision)
    return plan,snap


def test_actual_compact64_slot_plan_preserves_all_command_generations_and_terminal_receipts():
    s=system();s.commit.begin(s.checker,owner_authorized=True,decided_at=220)
    plan,snap=large_commit_plan(s.commit._state()[0]["pin"])
    frozen=frozen_plan(plan);assert len(encoded(frozen))<=192*1024
    assert ConfigurationMutation.restore(frozen,snap.binding).evaluate(snap)[0]=="READY"
    after=plan.evaluate(snap)[1];validate_document(after)
    assert work_sha(after)==work_sha(snap.document())
    assert plan.evaluate(replace(snap,raw=encoded(after)))==("CONFIRMED",None)
    assert len(json.loads(plan.before)["catalogues"])==64
