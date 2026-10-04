"""Actual post-root first-run adapters on a fresh synthetic SDK authority."""
from types import SimpleNamespace

from tb4.commissioning_checks import CommissionedStorage, Environment, Prerequisites
from tb4.commissioning_state import storage_spec
from tb4.drive.commissioning_native import NativeCommissioning
from tb4.reconfiguration_post_root import PostRootContext, PostRootCandidate
from reconfiguration_candidate_support import private
from reconfiguration_rebind_support import system as rebind_system


def checker_for(rebind, *, environment=None):
    proof = rebind.verify_current(owner_authorized=True)
    spec,_ = storage_spec(proof.storage)
    ctx = rebind.ctx
    port = NativeCommissioning(ctx.storage_port.drive,ctx.storage_port.docs,spec,llm_authorized=True,
        root_transition=proof.storage["root_transition"])
    return Prerequisites(environment=environment or (
        lambda:Environment("WINDOWS","X64","USER","DESKTOP_SESSION","INTERACTIVE")),
        storage=CommissionedStorage(port),credentials=None,source=ctx.source,runtime=ctx.runtime,clock=lambda:220)


def candidate_for(rebind, *, profile=None, archive=None, transaction=None):
    context = PostRootContext(rebind,profile or private(110),archive or private(111),transaction or private(112))
    return context,PostRootCandidate(context)


def system(*, profile=None, archive=None, transaction=None, **kwargs):
    s = rebind_system(**kwargs)
    assert s.rebind.begin(owner_authorized=True) == "PREPARED"
    assert s.rebind.advance(owner_authorized=True) == "REBOUND"
    context,candidate = candidate_for(s.rebind,profile=profile,archive=archive,transaction=transaction)
    return SimpleNamespace(rebind=s,context=context,candidate=candidate,checker=checker_for(s.rebind))
