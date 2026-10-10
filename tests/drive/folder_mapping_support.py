"""Real fresh Linux authority and protected C1, synthetic discovery/instructions."""
from dataclasses import asdict
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from tb4.ballpark_publication import Publisher
from tb4.ballpark_setup import GuidedBallpark
from tb4.commissioning_state import Setup
from tb4.discovery_workflow import Discovery
from tb4.drive.folder_mapping import FolderPathMapping,FolderMappingContext,FolderMappingPreparation,SCHEMA
from tb4.private_settings import native_settings
from tb4.reconfiguration_effects import Effects,SCHEMA as EFFECT_SCHEMA
from tb4.reconfiguration_evidence import ProtectedEvidence
from tb4.reconfiguration_maintenance import Maintenance,MaintenanceContext,WAL_SCHEMA
from tb4.watchdog.checkpoint_store import NativeCheckpoint,SCHEMA as CP_SCHEMA
from tb4.watchdog.leadership_runtime import Action,Capabilities,Checkpoint
from tests.drive.test_ballpark_setup import source,confirm,FACTS
from tests.drive.test_discovery_workflow import SCOPE,observation
from tests.drive.test_fixed_slot_commissioning import finish
from tests.drive.test_folder_commissioning import initialized
from tests.drive.test_native_leadership import ACTORS,clock
from tests.drive.reconfiguration_controller_support import TRANSITION


def system(context,tmp_path,*,schemas=(),device_name=None):
    spec,port,journal=context
    _,handle,commissioner=initialized(context);finish(commissioner)
    stores=[native_settings(tmp_path/("protected-"+str(i)),create=True,owner_authorized=True) for i in range(7)]
    with patch("tb4.commissioning_state.uuid4",return_value=UUID(ACTORS[0])):
        setup=Setup(stores[0],create=True)
    setup.choose(dict(role="watchdog",storage=dict(spec=asdict(spec),authority=handle.record()),
                      network_scope=["192.0.2.0/24"]))
    leader=commissioner.leader;grant=commissioner.grant
    caps=Capabilities(setup.installation_id,True,True,frozenset(Action))
    flow=Discovery(setup,storage_port=port,leadership=leader,grant=grant,clock=lambda:clock(220),
                   capabilities=lambda:caps)
    flow.configure(SCOPE,owner_authorized=True)
    flow.observe((observation(**({"name_hint":device_name} if device_name is not None else {})),))
    assert flow.publish()=="CONFIRMED"
    origin=source()
    for name in (WAL_SCHEMA,EFFECT_SCHEMA,CP_SCHEMA,SCHEMA)+tuple(schemas):
        raw=(Path(__file__).parents[2]/name).read_bytes()
        origin.files[origin.head][name]=raw
        origin.catalog["profiles"][0]["files"][name]=hashlib.sha256(raw).hexdigest()
    origin.save()
    guide=GuidedBallpark(setup,source=origin,runtime=FACTS)
    guide.begin();confirm(guide);assert Publisher(guide,flow).publish()=="CONFIRMED"
    checkpoint=NativeCheckpoint(stores[1],installation_id=setup.installation_id,
        binding=leader.backend.binding,create=True,owner_authorized=True,initial=Checkpoint(grant=grant))
    effects=Effects(leader,checkpoint,stores[2])
    baseline=ProtectedEvidence(stores[3],installation_id=setup.installation_id,transition_id=TRANSITION)
    ctx=MaintenanceContext(setup,leader,checkpoint,stores[4],baseline,port,lambda:clock(220),
                           lambda:caps,origin,FACTS,effects)
    maintenance=Maintenance(ctx);assert maintenance.begin(owner_authorized=True)=="MAINTENANCE"
    evidence=ProtectedEvidence(stores[5],installation_id=setup.installation_id,transition_id=TRANSITION)
    decision,status=maintenance.proposal();assert not status["requires_resolution"]
    assert maintenance.resolve(decision,evidence,owner_authorized=True)=="RESOLVED"
    mapping=FolderPathMapping(stores[6]);target=tmp_path/"exchange-after"
    creator=FolderMappingPreparation(FolderMappingContext(maintenance,evidence,mapping,target))
    return SimpleNamespace(port=port,handle=handle,spec=spec,setup=setup,leader=leader,flow=flow,
        checkpoint=checkpoint,effects=effects,ctx=ctx,maintenance=maintenance,evidence=evidence,
        mapping=mapping,creator=creator,target=target,stores=stores,source=origin,caps=caps)
