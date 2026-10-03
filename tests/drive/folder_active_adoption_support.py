"""Fresh owned Linux Folder/current-role profiles, old private stores unavailable."""
import copy
from dataclasses import asdict
from math import ceil
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from tb4.commissioning_checks import CommissionedStorage,Prerequisites
from tb4.commissioning_state import Setup,Reconciliation
from tb4.drive.commissioning_folder import FolderCommissioning
from tb4.drive.leadership import Leadership
from tb4.private_settings import native_settings
from tb4.reconfiguration_active_adoption import ActiveAdoptionContext
from tb4.reconfiguration_folder_active_adoption import FolderActiveAdoption,current_folder_admission
from tb4.reconfiguration_admission import AdmissionContext
from tb4.reconfiguration_effects import Effects
from tb4.timing_contract import TimingProfile
from tb4.watchdog.checkpoint_store import NativeCheckpoint
from tb4.watchdog.leadership_runtime import Action,Capabilities,Checkpoint,NativeWatchdogContext,NativeWatchdogRuntime
from tests.drive.folder_retained_support import system as retained_system
from tests.drive.test_native_leadership import ACTORS,clock,tid


def system(context,tmp_path,*,moved=True):
    former=retained_system(context,tmp_path,moved=moved)
    # A non-default coherent profile catches stale timing assumptions.
    timing=asdict(TimingProfile(control_s=7,lease_stale_s=180))
    former.candidate.choose(dict(timing=timing),owner_authorized=True)
    assert former.commit.begin(former.checker,owner_authorized=True,decided_at=220)=="PREPARED"
    assert former.commit.advance(former.checker,owner_authorized=True)=="PUBLISHED"
    # Only this installation's explicitly configured actual current path/identity.
    oldport=former.ctx.storage_port
    port=FolderCommissioning(oldport.root,oldport.spec,root_identity=oldport._config().root_identity,
                             llm_authorized=True)
    stores={name:native_settings(tmp_path/("new-folder-active-"+name),create=True,owner_authorized=True)
            for name in ("original","checkpoint","effects","profile","archive","transaction")}
    with patch("tb4.commissioning_state.uuid4",return_value=UUID(ACTORS[1])):
        model=Setup(stores["original"],create=True)
    choices=copy.deepcopy(former.ctx.setup.private_choices())
    choices["descriptor"]["installation_id"]=model.installation_id
    choices["descriptor"]["topology"]="ISOLATED"
    for d in choices["descriptor"]["devices"]:
        d["display_name"]="Synthetic own Folder installation"
        d["interfaces"]=[dict(name="synthetic-own",segment="fixture",kind="ISOLATED",addresses=["198.51.100.21/24"])]
    choices["network_scope"]=["198.51.100.0/24"]
    # The original path is private input, not a shared path copied from the old host.
    choices["storage_request"]=dict(mode=port.mode,location=str(port.root))
    model.choose(choices)
    model.perform_once("f"*64,lambda:None,owner_authorized=True)
    model.reconcile("f"*64,lambda _:Reconciliation.CONFIRMED)
    leader=Leadership(port.authority(former.value.handle),actor=model.installation_id,
        enrollment=former.ctx.leadership.enrollment,profile=TimingProfile.parse(timing))
    incumbent=leader.backend.read().document()["records"]["global.leadership"]["body"]
    sample=clock(ceil(incumbent["heartbeat_at"]+leader.profile.lease_stale_s))
    plan=leader.acquire(leader.observe(sample),transition=tid("new-folder-active-role"))
    report=leader.commit(plan,mode="START");assert report.outcome=="CONFIRMED"
    grant=leader.confirmed_grant(plan,report)
    cp=NativeCheckpoint(stores["checkpoint"],installation_id=model.installation_id,binding=leader.backend.binding,
        create=True,owner_authorized=True,initial=Checkpoint(grant=grant))
    caps=Capabilities(model.installation_id,True,True,frozenset(Action))
    old=former.checker
    checker=Prerequisites(environment=old.environment,storage=CommissionedStorage(port),credentials=None,
        source=old.source,runtime=old.runtime,clock=lambda:sample.utc)
    local=AdmissionContext(stores["original"],cp,leader,checker,lambda:caps,lambda:sample)
    adoptionctx=ActiveAdoptionContext(local,stores["profile"],stores["archive"],stores["transaction"])
    effects=Effects(leader,cp,stores["effects"])
    before=stores["original"].read()
    # A new owner is never given old private stores, including the old mapping.
    oldstores=[former.ctx.setup.store,former.ctx.store,former.ctx.baseline.store,former.ctx.checkpoint.store,
        former.ctx.effects.store,former.candidate.context.resolution.store,former.candidate.context.profile,
        former.candidate.context.archive,former.candidate.context.transaction,former.context.store,
        former.promotion_context.store,oldport.mapping.store]
    def unavailable(*args,**kwargs):raise OSError("SYNTHETIC_FORMER_FOLDER_HOST_UNAVAILABLE")
    for store in oldstores:store.read=store.save=unavailable
    return SimpleNamespace(former=former,port=port,source=former.value.source,context=adoptionctx,
        adoption=FolderActiveAdoption(adoptionctx),local=local,checker=checker,effects=effects,before=before,timing=timing)


def finish(s):
    assert s.adoption.begin(owner_authorized=True)["phase"]=="STAGED"
    assert s.adoption.prepare(owner_authorized=True,decided_at=s.local.clock().utc)=="PREPARED"
    assert s.adoption.advance(owner_authorized=True)=="PROFILE_PROMOTED"
    admission=current_folder_admission(s.local)
    assert admission.release(owner_authorized=True)==2
    return admission


def runtime(s,admission):
    return NativeWatchdogRuntime(NativeWatchdogContext(s.local.leadership,s.local.checkpoint,
        s.local.capabilities,s.local.clock,lambda:None,configuration_revision=admission.revision,effects=s.effects))
