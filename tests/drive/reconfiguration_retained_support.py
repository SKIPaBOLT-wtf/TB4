"""Actual same-authority C1/Candidate/first-run and retained publication fixtures."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from tb4.commissioning_checks import detect_environment
from tb4.private_settings import native_settings
from tb4.reconfiguration_candidate import Candidate
from tb4.reconfiguration_evidence import ProtectedEvidence
from tb4.reconfiguration_retained import RetainedCommitContext,RetainedConfigurationCommit
from tb4.reconfiguration_retained_promotion import RetainedPromotionContext,RetainedProfilePromotion
from tests.drive.reconfiguration_candidate_support import system as candidate_system,private


def system(*,commit_store=None,promotion_store=None,**kwargs):
    stores={k:private(i) for k,i in (("profile_store",301),("checkpoint_store",302),
        ("effect_store",303),("state_store",304),("baseline_store",305))}
    s=candidate_system(**{**stores,**kwargs})
    evidence=ProtectedEvidence(private(306),installation_id=s.value.setup.installation_id,
        transition_id=s.value.context.baseline.transition_id)
    decision,status=s.value.controller.proposal();assert not status["requires_resolution"]
    assert s.value.controller.resolve(decision,evidence,owner_authorized=True)=="RESOLVED"
    candidate=Candidate(replace(s.context,resolution=evidence))
    assert candidate.begin(owner_authorized=True)["phase"]=="STAGED"
    context=RetainedCommitContext(candidate,commit_store or private(201))
    commit=RetainedConfigurationCommit(context)
    promotion_context=RetainedPromotionContext(commit,promotion_store or private(202))
    return SimpleNamespace(value=s.value,candidate=candidate,checker=s.checker,context=context,commit=commit,
        promotion_context=promotion_context,promotion=RetainedProfilePromotion(promotion_context))


def publish(s):
    assert s.commit.begin(s.checker,owner_authorized=True,decided_at=220)=="PREPARED"
    assert s.commit.advance(s.checker,owner_authorized=True)=="PUBLISHED"
    return s


def promote(s):
    publish(s)
    assert s.promotion.begin(s.checker,owner_authorized=True)=="PREPARED"
    assert s.promotion.advance(s.checker,owner_authorized=True)=="PROFILE_PROMOTED"
    return s


def native_system(root,store,*,promotion=False):
    root=Path(root)
    stores=[native_settings(root.parent/("retained-private-"+str(i)),create=True,owner_authorized=True)
            for i in range(10)]
    s=candidate_system(profile=stores[0],archive=stores[1],transaction=stores[2],
        profile_store=stores[3],checkpoint_store=stores[4],effect_store=stores[5],
        state_store=stores[6],baseline_store=stores[7],environment=lambda:detect_environment(launch_mode="EXTERNAL"))
    v=s.value
    evidence=ProtectedEvidence(stores[8],installation_id=v.setup.installation_id,
        transition_id=v.context.baseline.transition_id)
    decision,status=v.controller.proposal();assert not status["requires_resolution"]
    assert v.controller.resolve(decision,evidence,owner_authorized=True)=="RESOLVED"
    candidate=Candidate(replace(s.context,resolution=evidence))
    candidate.begin(owner_authorized=True)
    context=RetainedCommitContext(candidate,stores[9] if promotion else store)
    commit=RetainedConfigurationCommit(context)
    pcontext=RetainedPromotionContext(commit,store if promotion else private(203))
    return SimpleNamespace(value=v,candidate=candidate,checker=s.checker,context=context,commit=commit,
        promotion_context=pcontext,promotion=RetainedProfilePromotion(pcontext))


def after_previous_root_system():
    """A later configuration transition keeps the verified former root receipt."""
    from tb4.commissioning_state import Setup
    from tb4.drive.commissioning import digest
    from tb4.reconfiguration_candidate import CandidateContext
    from tb4.reconfiguration_effects import Effects
    from tb4.reconfiguration_maintenance import Maintenance,MaintenanceContext
    from tests.drive.reconfiguration_admission_support import system as previous_system
    previous=previous_system();v=previous.value
    previous.admission.release(owner_authorized=True)
    setup=Setup(v.setup.store);port=previous.checker.storage.port
    leader=previous.context.leadership
    transition=digest(["synthetic-later-retained-configuration",setup.installation_id])
    baseline=ProtectedEvidence(private(501),installation_id=setup.installation_id,transition_id=transition)
    effects=Effects(leader,v.checkpoint,v.effects.store)
    ctx=MaintenanceContext(setup,leader,v.checkpoint,private(502),baseline,port,
        previous.context.clock,previous.context.capabilities,v.source,v.context.runtime,effects)
    maintenance=Maintenance(ctx);assert maintenance.begin(owner_authorized=True)=="MAINTENANCE"
    evidence=ProtectedEvidence(private(503),installation_id=setup.installation_id,transition_id=transition)
    decision,status=maintenance.proposal();assert not status["requires_resolution"]
    assert maintenance.resolve(decision,evidence,owner_authorized=True)=="RESOLVED"
    candidate=Candidate(CandidateContext(maintenance,evidence,private(504),private(505),private(506)))
    candidate.begin(owner_authorized=True)
    ccontext=RetainedCommitContext(candidate,private(507));commit=RetainedConfigurationCommit(ccontext)
    pcontext=RetainedPromotionContext(commit,private(508))
    return SimpleNamespace(previous=previous,value=v,candidate=candidate,checker=previous.checker,
        context=ccontext,commit=commit,promotion_context=pcontext,promotion=RetainedProfilePromotion(pcontext))
