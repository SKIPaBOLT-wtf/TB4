"""Actual rootless same-authority publication/promotion; synthetic SDK only."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from tb4.ballpark_records import shared
from tb4.commissioning_state import Setup
from tb4.configuration_contract import ConfigurationError,configuration
from tb4.drive.docs_authority import AuthorityError
from tb4.private_settings import SettingsError
from tb4.reconfiguration_admission import AdmissionContext,ConfigurationAdmission
from tb4.reconfiguration_candidate import SCHEMA,SCHEMA_SHA256
from tb4.reconfiguration_effects import SLOT,ledger,changed_row
from tb4.reconfiguration_retained import RetainedConfigurationCommit,RetainedConfigurationMutation,work_sha
from tb4.reconfiguration_retained_promotion import RetainedProfilePromotion
from tb4.watchdog.leadership_runtime import Action
from tests.drive.reconfiguration_retained_support import system,publish,promote
from tests.drive.test_native_leadership import clock


def test_later_rootless_configuration_keeps_earlier_exact_root_proof_without_rebind_or_relocation():
    from tests.drive.reconfiguration_retained_support import after_previous_root_system
    s=after_previous_root_system();original=s.commit.candidate.original.store.read()
    storage=copy.deepcopy(original.payload["choices"]["storage"])
    marker=copy.deepcopy(s.value.provider.store.document["records"]["global.commissioning"])
    moves=copy.deepcopy(s.previous.promotion.publication.post_root.rebind.moves)
    assert storage["root_transition"]!=s.candidate.context.maintenance.context.baseline.transition_id
    promote(s)
    assert s.value.setup.store.read().previous==original.payload
    assert s.value.setup.store.read().payload["choices"]["storage"]==storage
    assert s.value.provider.store.document["records"]["global.commissioning"]==marker
    assert s.previous.promotion.publication.post_root.rebind.moves==moves


def test_rootless_actual_publication_preserves_exact_root_commissioning_gc_summary_work_and_all_local_history():
    s=system();v=s.value;before=copy.deepcopy(v.provider.store.document);original=v.setup.store.read()
    metadata=copy.deepcopy(v.provider.metadata);writes=len(v.provider.store.calls)
    storage=copy.deepcopy(v.setup.private_choices()["storage"])
    publish(s);after=v.provider.store.document
    assert {k for k in before["records"] if before["records"][k]!=after["records"][k]}=={
        "global.settings","global.registry","target.000.catalogue"}
    assert after["records"][SLOT]==before["records"][SLOT]
    assert work_sha(after)==work_sha(before) and after["records"]["global.commissioning"]==before["records"]["global.commissioning"]
    assert v.provider.metadata==metadata and v.setup.store.read()==original
    assert v.setup.private_choices()["storage"]==storage and len(v.provider.store.calls)==writes+1
    assert shared(after)["revision"]==shared(before)["revision"]+1
    assert configuration(after)=={**configuration(before),"revision":configuration(before)["revision"]+1,"phase":"ACTIVE"}
    assert RetainedConfigurationCommit(s.context).advance(s.checker,owner_authorized=True)=="PUBLISHED"
    assert len(v.provider.store.calls)==writes+1


def test_full_original_archive_previous_own_identity_and_current_fresh_admission_do_not_need_old_wals():
    s=system();v=s.value;original=v.setup.store.read();promote(s)
    saved=v.setup.store.read();assert saved.revision==original.revision+1 and saved.previous==original.payload
    assert s.candidate.context.archive.read().payload["profile"]==original.payload
    assert saved.payload["state"]=="INCOMPLETE" and saved.payload["reason"]=="REVALIDATION_REQUIRED"
    for key in ("installation_id","setup_nonce","operations"):
        assert saved.payload[key]==original.payload[key]
    assert saved.payload["choices"]["storage"]==original.payload["choices"]["storage"]
    context=AdmissionContext(v.setup.store,v.checkpoint,v.flow.leader,s.checker,v.context.capabilities,v.context.clock)
    admission=ConfigurationAdmission(context)
    assert v.checkpoint.read().maintenance is not None
    revision=admission.release(owner_authorized=True)
    assert revision==configuration(v.provider.store.document)["revision"]
    def obsolete():raise SettingsError("SYNTHETIC_OBSOLETE_WAL_UNAVAILABLE")
    for store in (s.context.store,s.promotion_context.store,s.candidate.context.transaction,
                  s.candidate.context.archive,s.candidate.context.profile,v.context.store,v.context.baseline.store):
        store.read=obsolete
    assert ConfigurationAdmission(context).revision()==revision
    assert Setup(v.setup.store).status()["runtime_active"] is False


@pytest.mark.parametrize("after",[False,True])
def test_ambiguous_shared_reply_restarts_same_dispatch_inspect_only_and_never_repeats(after):
    s=system();v=s.value;store=v.provider.store
    s.commit.begin(s.checker,owner_authorized=True,decided_at=220);writes=len(store.calls)
    original=v.setup.store.read();on_read=store.on_read
    def lost():
        if after:store.on_read=lambda *_:(_ for _ in ()).throw(TimeoutError("SYNTHETIC_READ_LOST"))
        raise TimeoutError("SYNTHETIC_REPLY_LOST")
    if after:store.after_write=lost
    else:store.before_write=lambda _:lost()
    assert s.commit.advance(s.checker,owner_authorized=True)=="UNKNOWN"
    store.before_write=store.after_write=None;store.on_read=on_read
    fresh=RetainedConfigurationCommit(s.context)
    assert fresh._state()[0]["dispatch"]=="INVOKING"
    assert fresh.advance(s.checker,owner_authorized=True)==("PUBLISHED" if after else "UNKNOWN")
    assert len(store.calls)==writes+1 and v.setup.store.read()==original


@pytest.mark.parametrize("fault",["source","root_permission","clock","caps","force","work","profile","stage","unknown","barrier"])
def test_fresh_final_boundaries_refuse_without_shared_write_or_main_replacement(fault):
    s=system();v=s.value;store=v.provider.store
    s.commit.begin(s.checker,owner_authorized=True,decided_at=220);writes=len(store.calls);original=v.setup.store.read()
    if fault=="source":v.source.catalog["profiles"][0]["status"]="REVOKED";v.source.save()
    elif fault=="root_permission":v.provider.metadata[v.setup.private_choices()["storage"]["spec"]["root_id"]]["capabilities"]["canEdit"]=False
    elif fault=="clock":object.__setattr__(s.commit.ctx,"clock",lambda:clock(trusted=False))
    elif fault=="caps":object.__setattr__(s.commit.ctx,"capabilities",lambda:None)
    elif fault=="force":store.document["records"]["global.force_request"].update(retention="BUSY",body={"synthetic":True})
    elif fault=="work":store.document["records"]["target.000.status"]["body"]={"synthetic":True}
    elif fault=="profile":v.setup.choose({"network_scope":v.setup.private_choices()["network_scope"]})
    elif fault=="stage":s.candidate.choose({"network_scope":["192.0.2.0/24"]},owner_authorized=True)
    else:
        row=store.document["records"][SLOT];value=ledger(row)
        if fault=="unknown":value["entries"]["SSH"]=dict(owner=v.setup.installation_id,epoch=1,operation_id="b"*64,outcome="UNKNOWN")
        else:value["barrier"]["local_clear"]=False
        store.document["records"][SLOT]=changed_row(row,value)
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):
        s.commit.advance(s.checker,owner_authorized=True)
    assert len(store.calls)==writes
    if fault!="profile":assert v.setup.store.read()==original


def test_stage_change_during_actual_first_run_cannot_pass_the_last_publication_boundary():
    s=system();v=s.value;s.commit.begin(s.checker,owner_authorized=True,decided_at=220)
    original=v.setup.store.read();writes=len(v.provider.store.calls);environment=s.checker.environment;seen=[]
    def late():
        if not seen:
            seen.append(True);s.candidate.choose({"network_scope":["192.0.2.0/24"]},owner_authorized=True)
        return environment()
    s.checker.environment=late
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):
        s.commit.advance(s.checker,owner_authorized=True)
    assert seen and len(v.provider.store.calls)==writes and v.setup.store.read()==original


def test_closed_distinct_native_metadata_and_hash_keep_existing_post_root_contract_separate():
    from jsonschema import Draft202012Validator
    s=system();raw=(Path(__file__).parents[2]/SCHEMA).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SCHEMA_SHA256
    with pytest.raises(ConfigurationError,match="STORE_ALIAS"):
        RetainedConfigurationCommit(replace(s.context,store=s.candidate.context.profile))
    s.commit.begin(s.checker,owner_authorized=True,decided_at=220);frame=s.context.store.read().payload
    schema=json.loads(raw);validator=Draft202012Validator(schema["$defs"]["retainedConfigurationCommit"])
    assert validator.is_valid(frame) and not validator.is_valid({**frame,"foreign":True})
    assert not Draft202012Validator(schema["$defs"]["configurationCommit"]).is_valid(frame)
    assert len(frame["pin"]["files"])<=17
    s.commit.advance(s.checker,owner_authorized=True)
    s.promotion.begin(s.checker,owner_authorized=True);p=s.promotion_context.store.read().payload
    assert Draft202012Validator(schema["$defs"]["retainedProfilePromotion"]).is_valid(p)
    assert not Draft202012Validator(schema["$defs"]["profilePromotion"]).is_valid(p)


def test_force_request_during_first_run_refuses_profile_promotion_without_touching_main():
    s=system();publish(s);s.promotion.begin(s.checker,owner_authorized=True)
    original=s.value.setup.store.read();environment=s.checker.environment;seen=[]
    def late():
        if not seen:
            seen.append(True);s.value.provider.store.document["records"]["global.force_request"].update(
                retention="BUSY",body={"synthetic":True})
        return environment()
    s.checker.environment=late
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):
        s.promotion.advance(s.checker,owner_authorized=True)
    assert seen and s.value.setup.store.read()==original
