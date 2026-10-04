"""Actual first-run/publication/profile promotion on synthetic SDK authority."""
from types import SimpleNamespace
from tb4.reconfiguration_promotion import PromotionContext,ProfilePromotion
from reconfiguration_candidate_support import private
from reconfiguration_commit_support import system as commit_system


def system(*,promotion_store=None,prepare=None,**kwargs):
    s=commit_system(**kwargs)
    if prepare is not None:prepare(s)
    assert s.commit.begin(s.checker,owner_authorized=True,decided_at=220)=="PREPARED"
    assert s.commit.advance(s.checker,owner_authorized=True)=="PUBLISHED"
    context=PromotionContext(s.commit,promotion_store or private(114))
    return SimpleNamespace(publication=s,context=context,promotion=ProfilePromotion(context),checker=s.checker,value=s.value)
