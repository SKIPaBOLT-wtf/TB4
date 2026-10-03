"""Actual native Linux candidate/relocation/fallback, owned synthetic authority."""
from dataclasses import replace
from math import ceil
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from tb4.commissioning_checks import CommissionedStorage,Prerequisites,detect_environment
from tb4.commissioning_state import Setup
from tb4.drive.folder_mapping import FolderMappedCommissioning,FolderMappingPreparation
from tb4.drive.folder_relocation import NativeFolderRename
from tb4.drive.leadership import Leadership
from tb4.private_settings import native_settings,SettingsError
from tb4.reconfiguration_candidate import Candidate,CandidateContext,SCHEMA as CANDIDATE_SCHEMA
from tb4.reconfiguration_effects import Effects
from tb4.reconfiguration_evidence import ProtectedEvidence
from tb4.reconfiguration_folder import FolderRelocation,FolderRelocationContext,SCHEMA
from tb4.reconfiguration_maintenance import Maintenance
from tb4.watchdog.checkpoint_store import NativeCheckpoint
from tb4.watchdog.leadership_runtime import Action,Capabilities,Checkpoint
from tests.drive.folder_mapping_support import system as mapping_system
from tests.drive.test_native_leadership import ACTORS,clock,tid


def system(context,tmp_path,*,unicode=False):
    v=mapping_system(context,tmp_path,schemas=(CANDIDATE_SCHEMA,SCHEMA),
        device_name="Synthetic įrenginys" if unicode else None)
    if unicode:
        v.target=tmp_path/"exchange-after-ą"
        v.creator=FolderMappingPreparation(replace(v.creator.context,target=v.target))
    v.creator.prepare(owner_authorized=True)
    mapped=FolderMappedCommissioning(v.port,v.port._config(),v.mapping)
    leader=Leadership(mapped.authority(v.handle),actor=v.setup.installation_id,enrollment=v.leader.enrollment)
    effects=Effects(leader,v.checkpoint,v.effects.store)
    ctx=replace(v.ctx,leadership=leader,effects=effects,storage_port=mapped)
    maintenance=Maintenance(ctx)
    extra=[native_settings(tmp_path/("relocation-private-"+str(i)),create=True,owner_authorized=True) for i in range(4)]
    candidate=Candidate(CandidateContext(maintenance,v.evidence,*extra[:3]))
    candidate.begin(owner_authorized=True)
    checker=Prerequisites(environment=lambda:detect_environment(launch_mode="EXTERNAL"),
        storage=CommissionedStorage(mapped),credentials=None,source=v.source,runtime=ctx.runtime,clock=lambda:220)
    native=NativeFolderRename()
    relocation=FolderRelocation(FolderRelocationContext(candidate,checker,v.mapping,extra[3],native))
    return SimpleNamespace(value=v,ctx=ctx,mapped=mapped,candidate=candidate,checker=checker,
                           native=native,relocation=relocation,extra=extra,tmp_path=tmp_path)


def takeover(s):
    v=s.value
    stores=[native_settings(s.tmp_path/("fallback-private-"+str(i)),create=True,owner_authorized=True) for i in range(5)]
    with patch("tb4.commissioning_state.uuid4",return_value=UUID(ACTORS[1])):
        setup=Setup(stores[0],create=True)
    choices=s.ctx.setup.private_choices();choices["descriptor"]["installation_id"]=setup.installation_id
    setup.choose(choices)
    leader=Leadership(s.ctx.leadership.backend,actor=setup.installation_id,enrollment=s.ctx.leadership.enrollment)
    incumbent=leader.backend.read().document()["records"]["global.leadership"]["body"]
    sample=clock(ceil(incumbent["heartbeat_at"]+leader.profile.lease_stale_s))
    plan=leader.acquire(leader.observe(sample),transition=tid("folder-fallback-"+str(incumbent["epoch"])))
    report=leader.commit(plan,mode="START");assert report.outcome=="CONFIRMED"
    grant=leader.confirmed_grant(plan,report)
    checkpoint=NativeCheckpoint(stores[1],installation_id=setup.installation_id,binding=leader.backend.binding,
        create=True,owner_authorized=True,initial=Checkpoint(grant=grant))
    effects=Effects(leader,checkpoint,stores[2])
    baseline=ProtectedEvidence(stores[3],installation_id=setup.installation_id,transition_id=s.ctx.baseline.transition_id)
    caps=Capabilities(setup.installation_id,True,True,frozenset(Action))
    return replace(s.ctx,setup=setup,leadership=leader,checkpoint=checkpoint,effects=effects,
        store=stores[4],baseline=baseline,clock=lambda:sample,capabilities=lambda:caps)


def old_stores_unavailable(s,monkeypatch):
    def absent():raise SettingsError("SYNTHETIC_OLD_HOST_UNAVAILABLE")
    for store in (s.ctx.setup.store,s.ctx.store,s.ctx.baseline.store,s.ctx.checkpoint.store,s.ctx.effects.store,
                  s.candidate.context.resolution.store,*s.extra):
        monkeypatch.setattr(store,"read",absent)
