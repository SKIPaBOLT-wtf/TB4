"""Actual conditional Docs rebind and retained work, no live provider access."""
import copy
from dataclasses import asdict,replace
import hashlib
import json
from pathlib import Path

import pytest

from tb4.commissioning_checks import CommissionedStorage,Prerequisites
from tb4.commissioning_state import validated
from tb4.configuration_contract import ConfigurationError,configuration
from tb4.drive.authority_transaction import OwnerGuard
from tb4.drive.commissioning import SetupSpec,digest,seed_document,frozen_plan
from tb4.drive.docs_authority import AuthorityError
from tb4.exchange_layout import Capacity,encoded
from tb4.private_settings import SettingsError
from tb4.reconfiguration_effects import SLOT,ledger,changed_row
from tb4.reconfiguration_rebind import RemoteRebind,RebindContext,RebindMutation,SCHEMA,SCHEMA_SHA256
from tb4.reconfiguration_root_plan import root_plan,references,stable_records
from tb4.watchdog.leadership_runtime import Action
from reconfiguration_rebind_support import system,fallback,TARGET
from reconfiguration_candidate_support import private
from test_native_docs_transport import BINDING,wire_document
from test_native_leadership import ACTORS,clock,tid


def test_actual_all_after_rebind_same_document_metadata_media_work_first_run_and_original_profile():
    s=system();v=s.value;old=copy.deepcopy(v.provider.store.document);profile=v.setup.store.read()
    metadata=copy.deepcopy(v.provider.metadata);media=copy.deepcopy(s.media);writes=len(v.provider.store.calls)
    assert s.rebind.begin(owner_authorized=True)=="PREPARED"
    assert s.rebind.advance(owner_authorized=True)=="REBOUND"
    doc=v.provider.store.document
    assert {k for k in old["records"] if old["records"][k]!=doc["records"][k]}=={
        "global.commissioning","target.000.catalogue"}
    for key in ("global.commissioning","target.000.catalogue"):
        assert doc["records"][key]["generation"]==old["records"][key]["generation"]+1
    assert doc["records"]["target.000.catalogue"]["body"]["artifacts"].keys()=={"input","output"}
    assert {k:x["id"] for k,x in doc["records"]["target.000.catalogue"]["body"]["artifacts"].items()}=={
        k:x["id"] for k,x in old["records"]["target.000.catalogue"]["body"]["artifacts"].items()}
    assert v.provider.metadata==metadata and s.media==media and len(s.moves)==3
    assert v.setup.store.read()==profile and len(v.provider.store.calls)==writes+1
    assert s.rebind.advance(owner_authorized=True)=="REBOUND" and len(v.provider.store.calls)==writes+1
    proof=s.rebind.verify_current(owner_authorized=True)
    assert s.rebind.require_current(proof,owner_authorized=True)==proof
    state=s.rebind._state()[0];plan=RebindMutation.restore(state["plan"],v.flow.leader.backend.binding)
    port,storage=s.rebind._objects(plan)
    assert CommissionedStorage(port).verify(storage)==doc
    with pytest.raises(SettingsError):CommissionedStorage(v.flow.port).verify(v.setup.private_choices()["storage"])
    candidate=s.candidate._setup(s.candidate._state()[0]);payload=copy.deepcopy(candidate._payload)
    payload["choices"]["storage"]=storage;payload=validated(payload)
    checker=Prerequisites(environment=s.checker.environment,storage=CommissionedStorage(port),credentials=None,
        source=v.source,runtime=v.context.runtime,clock=lambda:220)
    assert checker.validate(payload).pin is not None
    assert configuration(doc)["phase"]=="MAINTENANCE" and v.setup.store.read()==profile


@pytest.mark.parametrize("after",[False,True])
def test_actual_lost_conditional_reply_inspects_without_repeating_before_or_after(after):
    s=system();v=s.value;store=v.provider.store;s.rebind.begin(owner_authorized=True)
    before=len(store.calls);on_read=store.on_read
    def lost():
        if after:store.on_read=lambda *_:(_ for _ in ()).throw(TimeoutError("SYNTHETIC_READ_UNAVAILABLE"))
        raise TimeoutError("SYNTHETIC_REBIND_REPLY_LOST")
    if after:store.after_write=lost
    else:store.before_write=lambda _:lost()
    assert s.rebind.advance(owner_authorized=True)=="UNKNOWN"
    store.after_write=store.before_write=None;store.on_read=on_read
    assert s.rebind._state()[0]["dispatch"]=="INVOKING"
    assert s.rebind.advance(owner_authorized=True)==("REBOUND" if after else "UNKNOWN")
    assert s.rebind.inspect()==("REBOUND" if after else "UNKNOWN")
    assert len(store.calls)==before+1 and len(s.moves)==3


@pytest.mark.parametrize("after",[False,True])
def test_actual_role_first_cas_race_and_shared_after_need_no_old_host_ack(after,monkeypatch):
    s=system();v=s.value;store=v.provider.store;s.rebind.begin(owner_authorized=True);taken=[]
    def take(*_):
        store.before_write=store.after_write=None;taken.append(fallback(s))
    if after:store.after_write=take
    else:store.before_write=take
    assert s.rebind.advance(owner_authorized=True)==("REBOUND" if after else "SUPERSEDED")
    current=taken[0];profile=current.ctx.setup.store.read()
    if not after:
        assert current.begin(owner_authorized=True)=="PREPARED"
        assert current.advance(owner_authorized=True)=="REBOUND"
    def absent():raise SettingsError("SYNTHETIC_OLD_HOST_UNAVAILABLE")
    for old in (v.setup.store,v.context.store,v.context.baseline.store,v.checkpoint.store,v.effects.store,
                s.roots.context.store,s.candidate.context.profile,s.candidate.context.archive,
                s.candidate.context.transaction,s.candidate.context.resolution.store,s.context.store):
        monkeypatch.setattr(old,"read",absent)
    proof=current.verify_current(owner_authorized=True)
    assert proof.storage["spec"]["root_id"]==TARGET
    if after:assert current.context.store.read() is None
    assert current.require_current(proof,owner_authorized=True)==proof
    assert current.ctx.setup.store.read()==profile and len(s.moves)==3
    assert v.provider.store.document["records"]["global.leadership"]["body"]["owner"]==current.ctx.setup.installation_id


@pytest.mark.parametrize("fault",["permission","source","clock","caps","election","work","unknown","metadata","authority","profile"])
def test_actual_changed_preconditions_refuse_without_remote_write_or_reset(fault,monkeypatch):
    s=system();v=s.value;store=v.provider.store;s.rebind.begin(owner_authorized=True)
    writes=len(store.calls);profile=v.setup.store.read()
    if fault=="source":v.source.fail_resolve=True
    elif fault=="clock":object.__setattr__(s.rebind.ctx,"clock",lambda:None)
    elif fault=="caps":object.__setattr__(s.rebind.ctx,"capabilities",lambda:None)
    elif fault=="election":
        cp=v.checkpoint.read();leader=v.flow.leader
        plan=leader.renew(leader.observe(clock(220)),cp.grant,transition=tid("rebind-pending-renew"))
        assert v.checkpoint.replace(cp,replace(cp,election=plan))
    elif fault=="work":
        store.document["records"]["target.000.work"].update(generation=1,operation_id="b"*64,retention="UNKNOWN")
    elif fault=="unknown":
        row=store.document["records"][SLOT];value=ledger(row);value["entries"]["SSH"]=dict(
            owner=v.setup.installation_id,epoch=v.checkpoint.read().grant.epoch,operation_id="b"*64,outcome="UNKNOWN")
        store.document["records"][SLOT]=changed_row(row,value)
    elif fault=="metadata":
        ref=store.document["records"]["target.000.catalogue"]["body"]["artifacts"]["input"]["id"]
        v.provider.metadata[ref]["parents"]=[v.provider.spec.root_id]
    elif fault=="authority":v.provider.metadata[BINDING.document_id]["properties"]["tb4Reconfiguration"]="0"*64
    elif fault=="profile":v.setup.choose({"network_scope":v.setup.private_choices()["network_scope"]})
    with pytest.raises((AuthorityError,SettingsError,ConfigurationError)):
        s.rebind.advance(owner_authorized=fault!="permission")
    assert len(store.calls)==writes and len(s.moves)==3
    if fault!="profile":assert v.setup.store.read()==profile


@pytest.mark.parametrize("fault",["work","catalogue","metadata","forged-proof"])
def test_fresh_shared_after_proof_never_accepts_saved_or_changed_facts(fault):
    s=system();v=s.value;s.rebind.begin(owner_authorized=True);assert s.rebind.advance(owner_authorized=True)=="REBOUND"
    proof=s.rebind.verify_current(owner_authorized=True);writes=len(v.provider.store.calls)
    if fault=="work":v.provider.store.document["records"]["target.000.status"]["body"]={"synthetic":True}
    elif fault=="catalogue":v.provider.store.document["records"]["target.000.catalogue"]["body"]["extra"]="synthetic"
    elif fault=="metadata":
        ref=proof.storage["authority"]["object_id"];v.provider.metadata[ref]["parents"]=["synthetic-foreign-root"]
    else:proof=replace(proof,storage={**proof.storage,"root_transition":"b"*64})
    with pytest.raises((AuthorityError,SettingsError,ConfigurationError)):
        s.rebind.require_current(proof,owner_authorized=True)
    assert len(v.provider.store.calls)==writes and len(s.moves)==3


def test_closed_schema_current_source_pin_store_alias_and_partial_plan_are_not_grants():
    from jsonschema import Draft202012Validator
    s=system();raw=(Path(__file__).parents[2]/SCHEMA).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SCHEMA_SHA256
    with pytest.raises(ConfigurationError,match="STORE_ALIAS"):RemoteRebind(replace(s.context,store=s.value.effects.store))
    s.rebind.begin(owner_authorized=True);frame=s.context.store.read().payload
    validator=Draft202012Validator(json.loads(raw));assert validator.is_valid(frame)
    assert not validator.is_valid({**frame,"foreign":True})
    assert s.rebind.advance(owner_authorized=True)=="REBOUND"
    receipt=s.value.provider.store.document["records"]["global.commissioning"]["body"]["reconfiguration"]
    receipt_schema=json.loads(raw)["$defs"]["rebindReceipt"]
    assert Draft202012Validator(receipt_schema).is_valid(receipt)
    assert not Draft202012Validator(receipt_schema).is_valid({**receipt,"foreign":True})
    partial=system(move=False)
    with pytest.raises((AuthorityError,ConfigurationError)):partial.rebind.begin(owner_authorized=True)
    assert partial.context.store.read() is None and not partial.moves


def large_plan():
    """Only a compact-plan/frame budget fixture; no physical/provider claim."""
    from tb4.drive.docs_authority import NativeDocsAuthority
    spec=SetupSpec("synthetic-source-root",BINDING.domain_id,tid("rebind-large"),ACTORS[0],"NATIVE_DOCS",Capacity(64,1,1,1))
    doc=json.loads(seed_document(spec,"Synthetic įrenginys",clock(220)))
    tx=tid("rebind-large-transition");doc["records"]["global.settings"]=dict(generation=1,operation_id=tx,retention="RETAINED",
        body=dict(descriptor_state="VALIDATED",revision=1,configuration=dict(schema_version=1,revision=1,phase="MAINTENANCE",transition_id=tx)))
    for index in range(64):
        refs={}
        for kind in ("input","output"):
            key=f"artifact.{index:03d}.{kind}";ref="s"*116+f"{index:03d}"+kind[:1]
            refs[kind]=dict(id=ref,seal=digest([spec.mode,spec.root_id,spec.domain_id,ref,spec.operation(key)]))
        doc["records"][f"target.{index:03d}.catalogue"]=dict(generation=17,operation_id=tid("retained-catalogue"),
            retention="RETAINED",body={"artifacts":refs,"synthetic_retained_unicode":"ą"*1500})
    _,refs=references(doc,BINDING)
    planned=root_plan(dict(schema_version=1,mode="NATIVE_DOCS",transition_id=tx,source_root=spec.root_id,
        target_root=TARGET,blueprint_sha256=spec.fingerprint,references_sha256=digest(refs),records_sha256=stable_records(doc)))
    value=dict(schema_version=1,coverage_epoch=1,entries={"IDENTITY":dict(owner=ACTORS[0],epoch=1,
        operation_id=digest(["reconfiguration-root",tx,"authority"]),outcome="COMPLETE")},
        barrier=dict(transition_id=tx,source_owner=ACTORS[0],source_epoch=1,local_clear=True),root_plan=planned)
    doc["records"][SLOT]=changed_row(doc["records"][SLOT],value)
    snap=NativeDocsAuthority(None,BINDING)._decode(wire_document(doc))
    return RebindMutation.prepare(snap,OwnerGuard(ACTORS[0],1)),snap


def test_max129_reference_plan_hashes_large_retained_unicode_instead_of_copying_full_work():
    plan,snap=large_plan();frozen=frozen_plan(plan)
    assert len(encoded(frozen))<=192*1024 and len(snap.raw)>len(encoded(frozen))
    assert RebindMutation.restore(frozen,snap.binding).evaluate(snap)[0]=="READY"
    target=plan.evaluate(snap)[1]
    after=replace(snap,raw=encoded(target))
    assert plan.evaluate(after)==("CONFIRMED",None)
    assert target["records"]["global.commissioning"]["generation"]==1
