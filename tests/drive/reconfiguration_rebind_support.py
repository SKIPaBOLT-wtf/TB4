"""Fresh synthetic SDK fixtures; actual root move and rebind implementations."""
import copy
from types import SimpleNamespace
from dataclasses import replace

from tb4.drive.commissioning_native import FOLDER,FIELDS
from tb4.reconfiguration_roots import DocsRootMoves,RootContext,SCHEMA as ROOT_SCHEMA
from tb4.reconfiguration_rebind import RemoteRebind,RebindContext,SCHEMA
from tb4.commissioning_state import Setup
from tb4.reconfiguration_effects import Effects
from tb4.reconfiguration_evidence import ProtectedEvidence
from tb4.watchdog.checkpoint_store import NativeCheckpoint
from reconfiguration_candidate_support import system as candidate_system,private
from test_native_docs_transport import HttpError

TARGET="synthetic-second-root"


def system(*,root_store=None,rebind_store=None,move=True,**kwargs):
    for name,index in (("profile_store",101),("checkpoint_store",102),("effect_store",103),
                       ("state_store",104),("baseline_store",105)):
        kwargs.setdefault(name,private(index))
    s=candidate_system(schemas=(ROOT_SCHEMA,SCHEMA),**kwargs);s.candidate.begin(owner_authorized=True)
    provider=s.value.provider;provider.metadata[TARGET]=dict(
        id=TARGET,mimeType=FOLDER,trashed=False,capabilities=dict(canEdit=True))
    moves=[];media={ref:b"synthetic retained artifact" for ref,v in provider.metadata.items()
        if v.get("mimeType")=="application/octet-stream"}
    for ref,content in media.items():provider.metadata[ref]["size"]=str(len(content))
    def update(**kw):
        assert set(kw)=={"fileId","body","addParents","removeParents","fields","supportsAllDrives"}
        assert kw["fields"]==FIELDS and kw["supportsAllDrives"] is True
        assert kw["addParents"]==TARGET and kw["removeParents"]==provider.spec.root_id
        assert set(kw["body"])=={"properties"}
        def run():
            value=provider.metadata[kw["fileId"]];assert value["parents"]==[provider.spec.root_id]
            value["parents"]=[TARGET];value["properties"]=copy.deepcopy(kw["body"]["properties"])
            moves.append(kw["fileId"]);return copy.deepcopy(value)
        return provider.request("files.update",kw,run)
    provider.update=update
    roots=DocsRootMoves(RootContext(s.candidate,s.checker,root_store or private(106),TARGET))
    if move:
        assert roots.begin(owner_authorized=True)=="MOVING"
        for _ in roots.old.spec.artifact_keys+("authority",):
            assert roots.advance(owner_authorized=True)=="CONFIRMED"
        assert roots.inspect()=="MOVED"
    context=RebindContext(s.value.context,rebind_store or private(107))
    return SimpleNamespace(value=s.value,candidate=s.candidate,checker=s.checker,roots=roots,moves=moves,media=media,
        context=context,rebind=RemoteRebind(context))


def fallback(s):
    from test_reconfiguration_effects import acquire_fallback
    _,_,context=acquire_fallback(s.value)
    profile=private(201);profile.save(context.setup.store.read().payload,expected_revision=0)
    setup=Setup(profile)
    cp=NativeCheckpoint(private(202),installation_id=setup.installation_id,binding=context.leadership.backend.binding,
        create=True,owner_authorized=True,initial=context.checkpoint.read())
    effects=Effects(context.leadership,cp,private(203))
    context=replace(context,setup=setup,checkpoint=cp,effects=effects,store=private(204),
        baseline=ProtectedEvidence(private(205),installation_id=setup.installation_id,
            transition_id=context.baseline.transition_id))
    return RemoteRebind(RebindContext(context,private(206)))
