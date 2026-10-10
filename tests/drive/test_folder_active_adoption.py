"""Required actual Linux current-role Folder ACTIVE adoption and native cuts."""
from contextlib import contextmanager
import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest
from jsonschema import Draft202012Validator

from tb4.ballpark_records import provenance,validate_receipt
from tb4.commissioning_state import Setup,DenyActivation
from tb4.configuration_contract import ConfigurationError
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority import DB,JOURNAL,identity
from tb4.drive.leadership import Leadership
from tb4.private_settings import SettingsError
from tb4.reconfiguration_active_adoption import ActiveAdoption
from tb4.reconfiguration_candidate import SCHEMA,SCHEMA_SHA256
from tb4.reconfiguration_effects import KEY,SLOT,ledger,changed_row
from tb4.reconfiguration_folder_active_adoption import FolderActiveAdoption,current_folder_admission
from tb4.watchdog.leadership_runtime import Action,Work
from tests.drive.test_folder_commissioning import context  # noqa: F401
from tests.drive.test_native_leadership import tid
from tests.drive.folder_active_adoption_support import system,finish,runtime

pytestmark=pytest.mark.skipif(sys.platform!="linux",reason="actual native Linux Folder ACTIVE adoption")
ERRORS=(ConfigurationError,SettingsError,AuthorityError)


def change(s,edit):
    backend=s.local.leadership.backend;snap=backend.read();doc=snap.document();edit(doc)
    assert backend.compare_replace(snap,doc).name=="ACCEPTED"
    return doc


@pytest.mark.parametrize("moved",[False,True])
def test_actual_new_folder_role_adopts_without_old_host_mapping_wal_ack_and_preserves_objects(context,tmp_path,moved):
    s=system(context,tmp_path,moved=moved);before=s.local.leadership.backend.read().document()
    files={p.name:(identity(p),p.read_bytes() if p.name not in {DB,JOURNAL} else None) for p in s.port.root.iterdir()}
    admission=finish(s);frame=s.local.profile.read();value=frame.payload;active=value["ballpark_publication"]["active"]
    assert s.local.checkpoint.read().grant.epoch==2 and s.local.leadership.profile.control_s==7
    assert value["choices"]["timing"]==s.timing and admission.revision()==2
    assert frame.previous==s.before.payload and frame.revision==s.before.revision+1
    assert s.context.archive.read().payload["profile"]==s.before.payload
    for name in ("installation_id","setup_nonce","operations"):
        assert value[name]==s.before.payload[name]
    assert value["operations"]=={"f"*64:"CONFIRMED"}
    assert value.get("credential_image")==s.before.payload.get("credential_image")
    assert value.get("network_table")==s.before.payload.get("network_table")
    assert value["choices"]["descriptor"]["devices"][0]["interfaces"]==s.before.payload["choices"]["descriptor"]["devices"][0]["interfaces"]
    assert value["choices"]["network_scope"]==["198.51.100.0/24"]
    assert value["choices"]["storage"]==s.before.payload["choices"]["storage"]
    assert active["adoption"]["kind"]=="CURRENT_FOLDER_ACTIVE_ADOPTION"
    assert active["adoption"]["provenance"]==before["records"]["global.registry"]["body"]["provenance"]
    assert provenance(active)!=active["adoption"]["provenance"]
    assert s.local.leadership.backend.read().document()==before
    assert files=={p.name:(identity(p),p.read_bytes() if p.name not in {DB,JOURNAL} else None) for p in s.port.root.iterdir()}
    assert value["state"]=="INCOMPLETE" and not s.adoption.view()["runtime_active"]
    def unavailable(*args,**kwargs):raise OSError("SYNTHETIC_OWN_FOLDER_ADOPTION_WAL_UNAVAILABLE")
    for store in (s.context.profile,s.context.archive,s.context.transaction):store.read=store.save=unavailable
    fresh=current_folder_admission(s.local);assert fresh.revision()==2
    runner=runtime(s,fresh);assert runner.tick()
    calls=[];work=Work(Action.WOL,tid("new-folder-active-work"),lambda *args:calls.append(True) or "COMPLETE")
    assert runner.perform(work)==runner.perform(work)=="COMPLETE" and len(calls)==1
    assert fresh.revision()==2


@pytest.mark.parametrize("retention",["BUSY","UNREAD","UNKNOWN"])
def test_actual_inherited_folder_work_and_unknown_effect_remain_without_old_ack_or_replay(context,tmp_path,retention):
    s=system(context,tmp_path)
    def edit(doc):
        doc["records"]["target.000.work"]=dict(generation=17,operation_id="a"*64,retention=retention,body={"synthetic_work":True})
        old=ledger(doc["records"][SLOT])
        old["entries"][Action.SSH.value]=dict(owner=s.port.spec.bootstrap_actor,epoch=1,
            operation_id=tid("old-folder-unknown-effect"),outcome="UNKNOWN")
        doc["records"][SLOT]=changed_row(doc["records"][SLOT],old)
    before=change(s,edit);admission=finish(s)
    assert s.local.leadership.backend.read().document()==before and admission.revision()==2
    runner=runtime(s,admission);assert runner.tick();calls=[]
    assert runner.perform(Work(Action.SSH,tid("old-folder-unknown-effect"),
        lambda *args:calls.append(True) or "COMPLETE"))=="UNKNOWN"
    assert not calls and s.effects.receipt(Action.SSH)["outcome"]=="UNKNOWN"
    assert s.local.leadership.backend.read().document()["records"]["target.000.work"]==before["records"]["target.000.work"]


@pytest.mark.parametrize("fault",["source","profile","force","artifact","clock","caps"])
def test_actual_folder_current_fact_loss_refuses_main_promotion_with_no_shared_mutation(context,tmp_path,fault):
    s=system(context,tmp_path);s.adoption.begin(owner_authorized=True)
    s.adoption.prepare(owner_authorized=True,decided_at=s.local.clock().utc)
    if fault=="source":s.source.catalog["profiles"][0]["status"]="REVOKED";s.source.save()
    elif fault=="profile":Setup(s.local.profile).cancel()
    elif fault=="force":
        leader=Leadership(s.local.leadership.backend,actor=s.port.spec.bootstrap_actor,
            enrollment=s.local.leadership.enrollment,profile=s.local.leadership.profile)
        plan=leader.request_force(leader.observe(s.local.clock()),request_id=tid("force-folder-active"),user_requested=True)
        assert leader.commit(plan,mode="START").outcome=="CONFIRMED"
    elif fault=="artifact":
        allocation=s.port.prepare(s.port.spec.artifact_keys[0],s.port.spec.operation(s.port.spec.artifact_keys[0]))
        os.chmod(s.port.root/allocation.object_id,0o644)
    elif fault=="clock":
        local=replace(s.local,clock=lambda:replace(s.local.clock(),wall_trusted=False))
        s.adoption=FolderActiveAdoption(replace(s.context,local=local))
    else:
        local=replace(s.local,capabilities=lambda:replace(s.local.capabilities(),coordinate=False))
        s.adoption=FolderActiveAdoption(replace(s.context,local=local))
    main=s.local.profile.read();cp=s.local.checkpoint.read();doc=s.local.leadership.backend.read().document()
    with pytest.raises(ERRORS):s.adoption.advance(owner_authorized=True)
    assert s.local.profile.read()==main and s.local.checkpoint.read()==cp
    assert s.local.leadership.backend.read().document()==doc


@pytest.mark.parametrize("fault",["stage","role"])
def test_actual_change_during_folder_first_run_refuses_local_confirmation(context,tmp_path,fault):
    s=system(context,tmp_path);s.adoption.begin(owner_authorized=True);main=s.local.profile.read()
    probe=s.checker.environment;seen=[]
    def late():
        if not seen:
            seen.append(True)
            if fault=="stage":Setup(s.context.profile).choose(dict(network_scope=["203.0.113.0/24"]))
            else:change(s,lambda d:d["records"]["global.leadership"]["body"].update(epoch=3))
        return probe()
    s.checker.environment=late
    with pytest.raises(ERRORS):s.adoption.prepare(owner_authorized=True,decided_at=s.local.clock().utc)
    assert seen and s.local.profile.read()==main and s.context.transaction.read().payload["phase"]=="STAGED"


@pytest.mark.parametrize("at",["intent","archive","stage","staged","prepared","original","confirmed"])
def test_actual_folder_native_cut_recovers_only_same_pending_frame_without_shared_send(context,tmp_path,at):
    s=system(context,tmp_path);store=s.context.transaction
    if at in {"prepared","original","confirmed"}:s.adoption.begin(owner_authorized=True)
    if at in {"original","confirmed"}:s.adoption.prepare(owner_authorized=True,decided_at=s.local.clock().utc)
    selected={"archive":s.context.archive,"stage":s.context.profile,"original":s.local.profile}.get(at,store)
    locked=selected.native.locked
    @contextmanager
    def cut():
        with locked() as port:
            promote=port.promote
            def stop():
                value=selected._decode(port.read("settings.pending"),port.binding).payload
                if at in {"archive","stage","original"} or value["phase"]=={
                    "intent":"STAGING","staged":"STAGED","prepared":"PREPARED","confirmed":"PROMOTED"}[at]:
                    raise OSError("SYNTHETIC_FOLDER_ACTIVE_NATIVE_CUT")
                return promote()
            port.promote=stop;yield port
    selected.native.locked=cut;doc=s.local.leadership.backend.read().document()
    with pytest.raises(ERRORS):
        if at in {"intent","archive","stage","staged"}:s.adoption.begin(owner_authorized=True)
        elif at=="prepared":s.adoption.prepare(owner_authorized=True,decided_at=s.local.clock().utc)
        else:s.adoption.advance(owner_authorized=True)
    selected.native.locked=locked
    with locked() as port:pending=port.read("settings.pending")
    assert pending is not None
    which={"archive":"archive","stage":"profile","original":"original"}.get(at,"transaction")
    status=s.source.catalog["profiles"][0]["status"]
    s.source.catalog["profiles"][0]["status"]="REVOKED";s.source.save()
    with pytest.raises(ERRORS):s.adoption.recover_local(which,owner_authorized=True)
    with locked() as port:assert port.read("settings.pending")==pending
    s.source.catalog["profiles"][0]["status"]=status;s.source.save()
    assert s.adoption.recover_local(which,owner_authorized=True)=="INSPECT_REQUIRED"
    with locked() as port:assert port.read("settings.json")==pending and port.read("settings.pending") is None
    fresh=FolderActiveAdoption(s.context);phase=fresh.view()["phase"]
    if phase=="STAGING":fresh.resume_staging(owner_authorized=True);phase=fresh.view()["phase"]
    if phase=="STAGED":fresh.prepare(owner_authorized=True,decided_at=s.local.clock().utc)
    assert fresh.advance(owner_authorized=True)=="PROFILE_PROMOTED"
    assert current_folder_admission(s.local).release(owner_authorized=True)==2
    assert s.local.profile.read().previous==s.before.payload and s.local.leadership.backend.read().document()==doc


def test_actual_folder_closed_kinds_receipts_alias_owner_and_default_activation(context,tmp_path):
    s=system(context,tmp_path)
    with pytest.raises(ConfigurationError,match="OWNER_REQUIRED"):s.adoption.begin()
    with pytest.raises(ConfigurationError,match="STORE_ALIAS"):
        FolderActiveAdoption(replace(s.context,profile=s.local.profile))
    with pytest.raises(ConfigurationError,match="ACTIVE_ADOPTION_CONTEXT"):ActiveAdoption(s.context)
    with pytest.raises(ConfigurationError,match="FOLDER_ACTIVE_ADOPTION_CONTEXT"):
        FolderActiveAdoption(replace(s.context,local=object()))
    s.adoption.begin(owner_authorized=True);raw=(Path(__file__).parents[2]/SCHEMA).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SCHEMA_SHA256
    schema=json.loads(raw);v=Draft202012Validator(schema["$defs"]["folderActiveAdoption"])
    assert v.is_valid(s.context.transaction.read().payload)
    assert not Draft202012Validator(schema["$defs"]["activeAdoption"]).is_valid(s.context.transaction.read().payload)
    s.adoption.prepare(owner_authorized=True,decided_at=s.local.clock().utc);assert v.is_valid(s.context.transaction.read().payload)
    s.adoption.advance(owner_authorized=True);value=s.local.profile.read().payload;active=value["ballpark_publication"]["active"]
    assert Draft202012Validator(schema["$defs"]["folderActiveAdoptionReceipt"]).is_valid(active["adoption"])
    for fault in ("mode","kind","binding","extra"):
        bad=copy.deepcopy(active)
        if fault=="mode":bad["adoption"]["authority"]["mode"]="NATIVE_DOCS"
        elif fault=="kind":bad["adoption"]["kind"]="CURRENT_ACTIVE_ADOPTION"
        elif fault=="binding":bad["adoption"]["authority"]["binding"]["root_id"]="40000000-0000-4000-8000-000000000099"
        else:bad["adoption"]["foreign"]="SYNTHETIC"
        with pytest.raises(ValueError):validate_receipt(bad,value["choices"])
    assert not Setup(s.local.profile).activate(s.checker,DenyActivation())["runtime_active"]


def test_actual_own_local_unknown_refuses_adoption_after_immediate_role_acquisition(context,tmp_path):
    s=system(context,tmp_path);assert s.local.checkpoint.read().grant.epoch==2
    Setup(s.local.profile).perform_once("e"*64,lambda:None,owner_authorized=True)
    main=s.local.profile.read();cp=s.local.checkpoint.read();doc=s.local.leadership.backend.read().document()
    with pytest.raises(ERRORS):s.adoption.begin(owner_authorized=True)
    assert s.context.transaction.read() is None and s.local.profile.read()==main and s.local.checkpoint.read()==cp
    assert s.local.leadership.backend.read().document()==doc
