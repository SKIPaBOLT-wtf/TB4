"""Actual current role continues the exact BEFORE remainder, never a saved grant."""
import copy
from dataclasses import replace
import json
import pytest

from tb4.commissioning_checks import CommissionedStorage
from tb4.configuration_contract import ConfigurationError
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.leadership import ClockSample
from tb4.private_settings import SettingsError
from tb4.reconfiguration_root_resume import ResumedDocsRootMoves,ResumeRootContext,SCHEMA
from tb4.reconfiguration_root_settlement import InheritedRootSettlement,ProvenNoDispatchSettlement
from tb4.watchdog.leadership_runtime import Action
from reconfiguration_candidate_support import private
from reconfiguration_root_resume_support import system,adopter,old_stores_unavailable
from test_reconfiguration_effects import acquire_fallback
from test_reconfiguration_roots import updates


@pytest.mark.parametrize("moved",[0,1,3])
@pytest.mark.parametrize("fallback",[False,True])
def test_actual_current_role_adopts_only_remaining_same_fixed_objects_without_old_private_host(moved,fallback):
    s=system();s.roots.begin(owner_authorized=True)
    for _ in range(moved):
        assert s.roots.advance(owner_authorized=True) in {"CONFIRMED","MOVED"}
    r=adopter(s,context=None if fallback else s.value.context)
    proof=r.inspector.inspect();before=copy.deepcopy(s.value.provider.store.document)
    profile=r.ctx.setup.store.read();ids=set(s.media)|{r.ctx.leadership.backend.binding.document_id}
    if fallback:
        old_stores_unavailable(s)
    assert r.begin(proof,owner_authorized=True) == ("MOVED" if moved==3 else "MOVING")
    state=r.context.store.read().payload
    assert state["index"]==state["adopted_index"]==moved and state["pending"] is None
    assert s.value.provider.store.document==before and len(updates(s))==moved
    from jsonschema import Draft202012Validator
    from pathlib import Path
    Draft202012Validator(json.loads((Path(__file__).parents[2]/SCHEMA).read_bytes())).validate(state)
    assert r.context.evidence.store.read().revision==1
    for _ in range(3-moved):
        assert r.advance(owner_authorized=True) in {"CONFIRMED","MOVED"}
    assert r.verify_moved() and len(updates(s))==3 and len(set(s.moves))==3 and set(s.moves)==ids
    assert r.ctx.setup.store.read()==profile and s.media=={k:b"synthetic retained artifact" for k in s.media}
    assert {k for k,v in before["records"].items() if s.value.provider.store.document["records"][k]!=v} <= {"global.summary"}
    assert r.ctx.checkpoint.read().maintenance==state["transition_id"]
    with pytest.raises(AuthorityError):
        CommissionedStorage(r.ctx.storage_port).verify(r.ctx.setup.private_choices()["storage"])


def test_exact_inherited_applied_unknown_must_settle_before_adoption_then_old_stores_can_be_absent():
    s=system();s.roots.begin(owner_authorized=True);s.failure[0]="after"
    assert s.roots.advance(owner_authorized=True)=="UNKNOWN" and len(updates(s))==1
    r=adopter(s);proof=r.inspector.inspect()
    with pytest.raises(ConfigurationError,match="ROOT_EVIDENCE"):
        r.begin(proof,owner_authorized=True)
    assert r.context.store.read() is None and r.context.evidence.store.read() is None
    old_stores_unavailable(s)
    helper=InheritedRootSettlement(r.ctx)
    assert helper.settle(helper.inspect(),owner_authorized=True)=="CONFIRMED"
    s.failure[0]=None
    assert r.begin(r.inspector.inspect(),owner_authorized=True)=="MOVING"
    assert r.context.store.read().payload["index"]==1
    assert r.advance(owner_authorized=True)=="CONFIRMED"
    assert r.advance(owner_authorized=True)=="MOVED" and len(updates(s))==3


@pytest.mark.parametrize("applied",[False,True])
def test_newly_armed_adopted_sdk_reply_loss_only_inspects_same_operation_never_reissues(applied):
    s=system();s.roots.begin(owner_authorized=True);r=adopter(s)
    r.begin(r.inspector.inspect(),owner_authorized=True)
    s.failure[0]="after" if applied else "before"
    assert r.advance(owner_authorized=True)=="UNKNOWN" and len(updates(s))==1
    fresh=ResumedDocsRootMoves(r.context)
    assert fresh.advance(owner_authorized=True)==("CONFIRMED" if applied else "UNKNOWN")
    assert len(updates(s))==1 and fresh.ctx.effects.receipt(Action.IDENTITY)["outcome"]==("COMPLETE" if applied else "UNKNOWN")
    if not applied:
        with pytest.raises(ConfigurationError,match="NOT_PREPARED"):
            fresh.revoke_prepared(owner_authorized=True)


def test_adopted_actual_prepared_native_revocation_has_exact_origin_and_new_retry_not_replay():
    s=system();s.roots.begin(owner_authorized=True);r=adopter(s)
    r.begin(r.inspector.inspect(),owner_authorized=True);start=r.ctx.effects.start
    def pause(*args,**kwargs):
        assert start(*args,**kwargs)=="CONFIRMED"
        raise ConfigurationError("SYNTHETIC_AFTER_SHARED_BEFORE_SEND")
    r.ctx.effects.start=pause
    with pytest.raises(ConfigurationError,match="SYNTHETIC_AFTER_SHARED"):
        r.advance(owner_authorized=True)
    r.ctx.effects.start=start
    proof=r.revoke_prepared(owner_authorized=True)
    assert ProvenNoDispatchSettlement(r.ctx).settle(proof,owner_authorized=True)=="CONFIRMED"
    assert r.resume_revoked(proof,owner_authorized=True)=="READY" and not updates(s)
    assert r.advance(owner_authorized=True)=="CONFIRMED" and len(updates(s))==1


@pytest.mark.parametrize("fault",["owner","forged","other-origin","stale-profile","stale-plan","stale-work",
                                  "source","clock","capability","force","metadata-order","unknown","evidence-alias","wal-alias"])
def test_saved_stale_or_unqualified_facts_do_not_adopt_or_dispatch(fault):
    s=system();s.roots.begin(owner_authorized=True);r=adopter(s);proof=r.inspector.inspect()
    owner=True
    if fault=="owner":owner=False
    elif fault=="forged":proof=replace(proof,_origin=object())
    elif fault=="other-origin":
        from tb4.reconfiguration_root_facts import PartialRootInspection
        proof=PartialRootInspection(r.ctx).inspect()
    elif fault=="stale-profile":r.ctx.setup.choose({"network_scope":r.ctx.setup.private_choices()["network_scope"]})
    elif fault=="stale-plan":s.value.provider.store.document["records"]["global.summary"]["body"]["tb4_effects_v1"]["root_plan"]["target_root"]="synthetic-other-root"
    elif fault=="stale-work":
        s.value.provider.store.document["records"]["target.000.work"].update(generation=1,operation_id="a"*64,retention="BUSY")
    elif fault=="source":r.ctx.source.offline=True
    elif fault=="clock":object.__setattr__(r.ctx,"clock",lambda:None)
    elif fault=="capability":object.__setattr__(r.ctx,"capabilities",lambda:None)
    elif fault=="force":s.value.provider.store.document["records"]["global.force_request"]["retention"]="BUSY"
    elif fault=="metadata-order":
        item=s.context.store.read().payload["objects"][1]
        meta=s.value.provider.metadata[item["id"]]
        meta["parents"]=[r.new.root_id];meta["properties"]=r.new._props(item["key"],r.new.spec.operation(item["key"]))
        proof=r.inspector.inspect()
    elif fault=="unknown":
        old=s.value.provider.store.document["records"]["global.summary"]["body"]["tb4_effects_v1"]
        old["entries"]["SSH"]=dict(owner=r.ctx.setup.installation_id,epoch=2,operation_id="a"*64,outcome="UNKNOWN")
        proof=r.inspector.inspect()
    before=copy.deepcopy(s.value.provider.store.document);profile=r.ctx.setup.store.read()
    if fault in {"evidence-alias","wal-alias"}:
        context=replace(r.context,store=r.ctx.setup.store) if fault=="wal-alias" else replace(
            r.context,evidence=type(r.context.evidence)(r.ctx.setup.store,installation_id=r.ctx.setup.installation_id,
                                                      transition_id=r.context.evidence.transition_id))
        with pytest.raises(ConfigurationError,match="STORE_ALIAS"):
            ResumedDocsRootMoves(context)
    else:
        with pytest.raises((AuthorityError,ConfigurationError,SettingsError)):
            r.begin(proof,owner_authorized=owner)
    assert s.value.provider.store.document==before and r.ctx.setup.store.read()==profile and not updates(s)
    assert r.context.store.read() is None and r.context.evidence.store.read() is None


@pytest.mark.parametrize("change",["index","objects","profile","work","source","force"])
def test_current_actual_rechecks_refuse_cursor_skips_or_changed_inputs_before_any_sdk(change):
    s=system();s.roots.begin(owner_authorized=True);r=adopter(s)
    r.begin(r.inspector.inspect(),owner_authorized=True)
    if change in {"index","objects"}:
        saved=r.context.store.read();state=copy.deepcopy(saved.payload)
        if change=="index":state["index"]=1
        else:state["objects"][0]["id"]="synthetic-wrong-fixed-id"
        r.context.store.save(state,expected_revision=saved.revision)
    elif change=="profile":r.ctx.setup.choose({"network_scope":r.ctx.setup.private_choices()["network_scope"]})
    elif change=="work":s.value.provider.store.document["records"]["target.000.work"].update(generation=1,operation_id="a"*64,retention="BUSY")
    elif change=="source":r.ctx.source.offline=True
    else:s.value.provider.store.document["records"]["global.force_request"]["retention"]="BUSY"
    before=copy.deepcopy(s.value.provider.store.document);profile=r.ctx.setup.store.read()
    with pytest.raises((AuthorityError,ConfigurationError,SettingsError)):
        r.advance(owner_authorized=True)
    assert not updates(s) and s.value.provider.store.document==before and r.ctx.setup.store.read()==profile


def test_another_current_role_takes_over_again_without_ack_and_adopted_old_sender_cannot_send():
    s=system();s.roots.begin(owner_authorized=True);r=adopter(s)
    r.begin(r.inspector.inspect(),owner_authorized=True)
    from types import SimpleNamespace
    value=SimpleNamespace(**{**vars(s.value),"context":r.ctx,"setup":r.ctx.setup,
                             "flow":replace_flow(s.value.flow,r.ctx.leadership)})
    newer=acquire_fallback(value)[2]
    with pytest.raises((AuthorityError,ConfigurationError)):
        r.advance(owner_authorized=True)
    assert not updates(s) and newer.checkpoint.read().grant.epoch==3
    last=adopter(s,context=newer)
    assert last.begin(last.inspector.inspect(),owner_authorized=True)=="MOVING"
    assert last.advance(owner_authorized=True)=="CONFIRMED" and len(updates(s))==1


def replace_flow(flow,leader):
    from types import SimpleNamespace
    return SimpleNamespace(**{**vars(flow),"leader":leader})
