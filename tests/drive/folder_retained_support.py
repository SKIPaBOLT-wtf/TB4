"""Actual Linux same-folder after relocation and fresh protected C1 Candidate."""
from pathlib import Path
from types import SimpleNamespace

from tb4.private_settings import native_settings
from tb4.reconfiguration_candidate import Candidate,CandidateContext
from tb4.reconfiguration_evidence import ProtectedEvidence
from tb4.reconfiguration_maintenance import Maintenance
from tb4.reconfiguration_retained import RetainedCommitContext,RetainedConfigurationCommit
from tb4.reconfiguration_retained_promotion import RetainedPromotionContext,RetainedProfilePromotion
from tests.drive.folder_relocation_support import system as relocation_system


def system(context,tmp_path,*,moved=True):
    s=relocation_system(context,tmp_path)
    if moved:
        assert s.relocation.begin(owner_authorized=True)=="PREPARED"
        assert s.relocation.advance(owner_authorized=True)=="MOVED"
    maintenance=Maintenance(s.ctx)
    stores=[native_settings(Path(tmp_path)/("folder-final-private-"+str(i)),create=True,owner_authorized=True)
        for i in range(6)]
    evidence=ProtectedEvidence(stores[0],installation_id=s.ctx.setup.installation_id,
        transition_id=s.ctx.baseline.transition_id)
    decision,status=maintenance.proposal();assert not status["requires_resolution"]
    assert maintenance.resolve(decision,evidence,owner_authorized=True)=="RESOLVED"
    candidate=Candidate(CandidateContext(maintenance,evidence,*stores[1:4]))
    candidate.begin(owner_authorized=True)
    ccontext=RetainedCommitContext(candidate,stores[4]);commit=RetainedConfigurationCommit(ccontext)
    pcontext=RetainedPromotionContext(commit,stores[5])
    return SimpleNamespace(relocation=s,value=s.value,ctx=s.ctx,candidate=candidate,checker=s.checker,
        context=ccontext,commit=commit,promotion_context=pcontext,promotion=RetainedProfilePromotion(pcontext))
