"""Actual post-root first-run and same-authority publication fixtures."""
from types import SimpleNamespace

from tb4.reconfiguration_commit import CommitContext,ConfigurationCommit
from reconfiguration_candidate_support import private
from reconfiguration_post_root_support import system as post_root_system


def system(*, commit_store=None, **kwargs):
    s=post_root_system(**kwargs)
    assert s.candidate.begin(owner_authorized=True)["phase"]=="STAGED"
    context=CommitContext(s.candidate,commit_store or private(113))
    return SimpleNamespace(post_root=s,context=context,commit=ConfigurationCommit(context),checker=s.checker,
        value=s.rebind.value)
