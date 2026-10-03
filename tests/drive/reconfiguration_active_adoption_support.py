"""Own new installation adopts ACTIVE with former protected stores unavailable."""
import copy
from dataclasses import replace
from types import SimpleNamespace

from tb4.commissioning_checks import CommissionedStorage, Prerequisites
from tb4.commissioning_state import Setup, Reconciliation
from tb4.reconfiguration_active_adoption import ActiveAdoptionContext, ActiveAdoption, current_admission
from tb4.reconfiguration_admission import AdmissionContext
from tb4.reconfiguration_effects import Effects
from tb4.watchdog.checkpoint_store import NativeCheckpoint
from tb4.watchdog.leadership_runtime import NativeWatchdogContext, NativeWatchdogRuntime
from reconfiguration_candidate_support import private
from reconfiguration_promotion_support import system as published_system
from test_reconfiguration_effects import acquire_fallback


def new_owner(former, *, stores=None):
    # Acquire actually expired role first. No adoption/source proof is an election gate.
    _,_,ctx = acquire_fallback(former.value)
    model = Setup(ctx.setup.store)
    local = model.private_choices()["descriptor"]
    local["topology"] = "ISOLATED"
    for d in local["devices"]:
        d["display_name"] = "Synthetic own installation"
        d["interfaces"] = [dict(name="synthetic-own",segment="fixture",kind="ISOLATED",addresses=["198.51.100.21/24"])]
    model.choose(dict(descriptor=local,network_scope=["198.51.100.0/24"]))
    model.perform_once("f"*64,lambda:None,owner_authorized=True)
    model.reconcile("f"*64,lambda _:Reconciliation.CONFIRMED)
    stores = {} if stores is None else stores
    original = stores.get("original") or private(301)
    original.save(copy.deepcopy(model._payload),expected_revision=0)
    model = Setup(original)
    cp = NativeCheckpoint(stores.get("checkpoint") or private(302),installation_id=model.installation_id,
        binding=ctx.leadership.backend.binding,create=True,owner_authorized=True,initial=ctx.checkpoint.read())
    old = former.checker
    # Former SDK connection is an injected synthetic own connection, never an old WAL.
    checker = Prerequisites(environment=old.environment,storage=CommissionedStorage(former.value.flow.port),
        credentials=None,source=old.source,runtime=old.runtime,clock=old.clock)
    localctx = AdmissionContext(original,cp,ctx.leadership,checker,ctx.capabilities,ctx.clock)
    context = ActiveAdoptionContext(localctx,stores.get("profile") or private(303),
        stores.get("archive") or private(304),stores.get("transaction") or private(305))
    effects = Effects(ctx.leadership,cp,stores.get("effects") or private(306))
    before = original.read()
    # All former private inputs now unavailable. Production adopts only shared rows
    # and current object metadata from the new connection.
    def unavailable(*args,**kwargs):
        raise OSError("SYNTHETIC_FORMER_HOST_UNAVAILABLE")
    all_stores = [former.value.setup.store,former.value.checkpoint.store,former.value.effects.store,
        former.value.context.store,former.value.context.baseline.store]
    publication = getattr(former,"publication",None)
    if publication is not None:
        candidate = publication.commit.candidate
        all_stores += [candidate.context.profile,candidate.context.archive,candidate.context.transaction,
            publication.context.store,former.context.store]
    for store in all_stores:
        store.read = store.save = unavailable
    return SimpleNamespace(former=former,context=context,adoption=ActiveAdoption(context),checker=checker,
        value=former.value,effects=effects,before=before,local=localctx)


def system(**kwargs):
    return new_owner(published_system(),**kwargs)


def finish(s):
    assert s.adoption.begin(owner_authorized=True)["phase"] == "STAGED"
    assert s.adoption.prepare(owner_authorized=True,decided_at=s.local.clock().utc) == "PREPARED"
    assert s.adoption.advance(owner_authorized=True) == "PROFILE_PROMOTED"
    admission = current_admission(s.local)
    assert admission.release(owner_authorized=True) == 2
    return admission


def runtime(s, admission):
    return NativeWatchdogRuntime(NativeWatchdogContext(s.local.leadership,s.local.checkpoint,
        s.local.capabilities,s.local.clock,lambda:None,configuration_revision=admission.revision,effects=s.effects))
