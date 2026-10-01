"""R2 startup boundary through the actual native request adapter, no live host."""
import copy
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from tb4.drive.authority_transaction import RecordMutation
from tb4.drive.docs_authority import AuthorityError, NativeDocsAuthority
from tb4.drive.leadership import Leadership, LEADER
from tb4.exchange_layout import Capacity, empty_document
from tb4.watchdog.leadership_runtime import (Action, Capabilities, Checkpoint, NativeWatchdogContext,
    NativeWatchdogRuntime, SHARED, Work)
from test_native_docs_transport import BINDING, DOMAIN, WireStore, wire_document
from test_native_leadership import ACTORS, ENROLLMENT, clock, tid


class LocalCheckpoint:
    """Test-only atomic store. It does not qualify an OS durability/ACL adapter."""
    def __init__(self, actor, state=None):
        self.installation_id, self.binding = actor, BINDING
        self.state = state or Checkpoint()
        self.fail = False
        self.after_replace = None

    def read(self): return self.state

    def replace(self, expected, desired):
        if self.fail: raise OSError("PRIVATE_STORE_CANARY")
        if self.state != expected: return False
        self.state = desired
        if self.after_replace: self.after_replace(desired)
        return True


@pytest.fixture
def setup():
    store = WireStore(empty_document(DOMAIN, Capacity(1, 1, 1, 1)))
    def leader(i):
        return Leadership(NativeDocsAuthority(store.client(str(i)), BINDING),
                          actor=ACTORS[i], enrollment=ENROLLMENT)
    first = leader(0)
    plan = first.acquire(first.observe(clock()), transition=tid("first"), commissioning=True)
    report = first.commit(plan, mode="START")
    first_grant = first.confirmed_grant(plan, report)
    def make(i=1, *, utc=101, mono=0, local=None, caps=None, work=None):
        sample = [clock(utc, mono)]
        statuses, scheduled = [], []
        local = local or LocalCheckpoint(ACTORS[i])
        caps = caps or [Capabilities(ACTORS[i], True, True, frozenset(Action))]
        def next_work():
            scheduled.append(True)
            return work
        context = NativeWatchdogContext(leader(i), local, lambda:caps[0], lambda:sample[0],
            next_work, status=lambda *s:statuses.append(s))
        return SimpleNamespace(runtime=NativeWatchdogRuntime(context), context=context, sample=sample,
            statuses=statuses, scheduled=scheduled, local=local, caps=caps)
    def takeover(i, utc=340):
        candidate = leader(i)
        plan = candidate.acquire(candidate.observe(clock(utc)), transition=tid(f"takeover-{i}-{utc}"))
        assert candidate.commit(plan, mode="START").outcome == "CONFIRMED"
    return SimpleNamespace(store=store, leader=leader, first=first, grant=first_grant, make=make, takeover=takeover)


@pytest.mark.parametrize("action", list(Action))
def test_fresh_incumbent_prevents_every_eager_side_effect(setup, action):
    called = []
    client = setup.make(work=Work(action, tid(action), lambda *args:called.append(args)))
    baseline = setup.store.commits
    for _ in range(4): client.runtime.cycle()
    assert client.statuses == [("PAUSED", "OLDER_DOG_DETECTED")]
    assert not called and not client.scheduled
    assert setup.store.commits == baseline and setup.store.reads == 4  # 3 commissioning reads + 1 observation


def test_fallback_observation_does_not_interrupt_incumbent_renewal(setup):
    incumbent = setup.make(0, local=LocalCheckpoint(ACTORS[0], Checkpoint(grant=setup.grant)))
    fallback = setup.make()
    for offset in (0, 20, 40):
        incumbent.sample[0] = fallback.sample[0] = clock(101+offset, offset)
        assert incumbent.runtime.tick()
        before = copy.deepcopy(setup.store.document)
        fallback.runtime.cycle()
        assert setup.store.document == before and not fallback.scheduled
    assert setup.store.document["records"][LEADER]["body"]["owner"] == ACTORS[0]


def shared_work(action, label, seen):
    def prepare(snapshot, owner):
        seen.append(action)
        return RecordMutation.prepare(snapshot, owner=owner, protect=set(), changes={
            "global.summary": dict(generation=1, operation_id=tid(label), retention="BUSY", body={"test_action":action.value})})
    return Work(action, tid(label), prepare)


@pytest.mark.parametrize("action", list(Action))
def test_stale_start_acquires_before_each_effect_and_persists_receipt(setup, action):
    seen = []
    work = (shared_work(action, action.value, seen) if action in SHARED else
            Work(action, tid(action), lambda grant, operation:seen.append((grant.epoch,operation)) or "COMPLETE"))
    client = setup.make(utc=220, work=work)
    client.runtime.cycle()
    assert client.runtime.state == "RUNNING" and seen
    assert client.local.state.grant.epoch == 2
    assert client.local.state.receipts[0].outcome == "COMPLETE"
    before = len(seen)
    client.runtime.perform(work)
    assert len(seen) == before  # Same operation is not repeated.


@pytest.mark.parametrize("action", list(Action))
def test_resumed_old_owner_cannot_prepare_or_dispatch_any_action(setup, action):
    client = setup.make(utc=220)
    assert client.runtime.tick()
    setup.takeover(2)
    with pytest.raises(AuthorityError, match="OWNER_SUPERSEDED"):
        client.runtime.perform(Work(action,tid("old"),lambda *args:pytest.fail("old effect ran")))
    assert client.runtime.state == "PAUSED" and not client.local.state.receipts


def test_owner_changes_during_shared_preparation_rejects_old_write(setup):
    client = setup.make(utc=220); assert client.runtime.tick()
    before = copy.deepcopy(setup.store.document["records"]["global.summary"])
    def prepare(snapshot, owner):
        setup.takeover(2)
        return shared_work(Action.REGISTER,"registration",[]).execute(snapshot,owner)
    assert client.runtime.perform(Work(Action.REGISTER,tid("registration"),prepare)) == "UNKNOWN"
    assert setup.store.document["records"]["global.summary"] == before
    assert client.runtime.inspect_shared() == "SUPERSEDED"
    assert client.local.state.receipts[0].outcome == "SUPERSEDED"


def test_owner_changes_during_durable_external_intent_prevents_dispatch(setup):
    client=setup.make(utc=220); assert client.runtime.tick()
    def changed(state):
        if state.receipts:
            client.local.after_replace=None
            setup.takeover(2)
    client.local.after_replace=changed
    with pytest.raises(AuthorityError, match="OWNER_SUPERSEDED"):
        client.runtime.perform(Work(Action.WOL,tid("wake"),lambda *args:pytest.fail("dispatch ran")))
    assert client.local.state.receipts[0].outcome == "NOT_DISPATCHED"


def test_forced_requester_claims_fresh_incumbent_without_ack(setup):
    client=setup.make()
    candidate=client.context.leadership
    request=candidate.request_force(candidate.observe(clock(101)),request_id=tid("force"),user_requested=True)
    assert candidate.commit(request,mode="START").outcome == "CONFIRMED"
    assert client.runtime.tick() and client.local.state.grant.epoch == 2


def test_restart_uses_own_persisted_grant_but_never_computer_name(setup):
    client=setup.make(utc=220); assert client.runtime.tick()
    restarted=setup.make(utc=221,local=client.local)
    assert restarted.runtime.tick() and restarted.local.state.grant.epoch == 2
    no_grant=setup.make(utc=222)
    assert not no_grant.runtime.tick() and no_grant.runtime.reason == "OLDER_DOG_DETECTED"


def test_another_installation_cannot_use_copied_grant_or_capability(setup):
    client=setup.make(utc=220); assert client.runtime.tick()
    copied=setup.make(2,utc=221,local=LocalCheckpoint(ACTORS[2],client.local.state))
    assert not copied.runtime.tick() and not copied.scheduled
    wrong_caps=[Capabilities(ACTORS[0],True,True,frozenset(Action))]
    other=setup.make(2,utc=340,caps=wrong_caps)
    before=setup.store.commits
    assert not other.runtime.tick() and setup.store.commits == before


def test_context_rejects_other_installation_checkpoint(setup):
    client=setup.make()
    with pytest.raises(AuthorityError,match="LOCAL_INSTALLATION_BINDING"):
        NativeWatchdogRuntime(replace(client.context,checkpoint=LocalCheckpoint(ACTORS[0])))


def test_lost_acquisition_reply_restart_inspects_same_transition_once(setup):
    client=setup.make(utc=220)
    old=wire_document(setup.store.document,"old-visible-revision")
    def lost():
        setup.store.on_read=lambda count,response:old
        raise TimeoutError("SYNTHETIC")
    setup.store.after_write=lost
    assert not client.runtime.tick() and client.local.state.election is not None
    commits=setup.store.commits
    setup.store.after_write=setup.store.on_read=None
    restarted=setup.make(utc=221,local=client.local)
    assert restarted.runtime.tick()
    # Restart also renews the now confirmed acquisition, once.
    assert setup.store.commits == commits+1 and restarted.local.state.grant.epoch == 2


def test_failed_local_intent_persistence_never_writes_authority(setup):
    client=setup.make(utc=220); client.local.fail=True
    before=setup.store.commits
    assert not client.runtime.tick() and setup.store.commits == before
    assert client.statuses[-1] == ("PAUSED","AUTHORITY_UNAVAILABLE")


def test_external_unknown_survives_restart_and_does_not_block_new_leadership(setup):
    calls=[]
    work=Work(Action.SSH,tid("start"),lambda *args:calls.append(args) or "UNKNOWN")
    client=setup.make(utc=220); assert client.runtime.tick()
    assert client.runtime.perform(work) == "UNKNOWN"
    restarted=setup.make(utc=221,local=client.local); assert restarted.runtime.tick()
    assert restarted.runtime.perform(work) == "UNKNOWN" and len(calls) == 1
    assert restarted.runtime.perform(Work(Action.SSH,tid("new-start"),work.execute)) == "UNKNOWN"
    # Role continues and an independently scoped permitted action can proceed.
    assert restarted.runtime.perform(Work(Action.SCAN,tid("probe"),lambda *args:"COMPLETE")) == "COMPLETE"


def test_lost_shared_reply_is_reconciled_without_another_write(setup):
    client=setup.make(utc=220); assert client.runtime.tick()
    old=wire_document(setup.store.document,"stale-result-view")
    def lost():
        setup.store.on_read=lambda count,response:old
        raise TimeoutError("SYNTHETIC")
    setup.store.after_write=lost
    work=shared_work(Action.ROUTE,"route",[])
    assert client.runtime.perform(work) == "UNKNOWN"
    commits=setup.store.commits
    setup.store.after_write=setup.store.on_read=None
    assert client.runtime.inspect_shared() == "CONFIRMED" and setup.store.commits == commits
    assert client.local.state.receipts[0].outcome == "COMPLETE"


def test_partition_blocks_admission_and_rejoin_observes_new_owner(setup):
    client=setup.make(utc=220); assert client.runtime.tick()
    def unavailable(*args): raise TimeoutError("PRIVATE_PROVIDER_CANARY")
    setup.store.on_read=unavailable
    client.runtime.cycle()
    assert client.runtime.state == "PAUSED" and not client.scheduled
    setup.store.on_read=None; setup.takeover(2)
    client.sample[0]=clock(341,121)
    assert not client.runtime.tick() and client.runtime.reason == "OLDER_DOG_DETECTED"


def test_clock_uncertainty_uses_bounded_monotonic_standby_observations(setup):
    client=setup.make(); client.sample[0]=clock(None,0,False)
    assert not client.runtime.tick()
    client.sample[0]=clock(None,120,False)
    assert client.runtime.tick()


def test_read_capability_loss_performs_no_provider_call(setup):
    client=setup.make(caps=[Capabilities(ACTORS[1],False,False,frozenset())])
    reads=setup.store.reads
    assert not client.runtime.tick() and setup.store.reads == reads


def test_specific_action_requires_own_installation_capability(setup):
    client=setup.make(utc=220,caps=[Capabilities(ACTORS[1],True,True,frozenset({Action.SCAN}))])
    assert client.runtime.tick()
    with pytest.raises(AuthorityError,match="ACTION_CAPABILITY"):
        client.runtime.perform(Work(Action.WOL,tid("denied"),lambda *args:pytest.fail("unauthorized")))
    assert client.runtime.perform(Work(Action.SCAN,tid("allowed"),lambda *args:"COMPLETE")) == "COMPLETE"


def test_unknown_shared_intent_is_not_erased_by_an_external_receipt(setup):
    client=setup.make(utc=220); assert client.runtime.tick()
    setup.store.raise_write=403
    assert client.runtime.perform(shared_work(Action.ROUTE,"failed-route",[])) == "UNKNOWN"
    pending=client.local.state.mutation
    setup.store.raise_write=None
    assert client.runtime.perform(Work(Action.SCAN,tid("independent"),lambda *args:"COMPLETE")) == "COMPLETE"
    assert client.local.state.mutation is pending
    assert client.runtime.inspect_shared() == "UNKNOWN"


@pytest.mark.parametrize("reliable,reverse", [(False,False),(True,True)])
def test_clock_loss_between_tick_and_external_dispatch_is_rejected(setup,reliable,reverse):
    client=setup.make(utc=220,mono=10); assert client.runtime.tick()
    client.sample[0]=clock(221,9 if reverse else 11,reliable=reliable)
    with pytest.raises(AuthorityError,match="RUNTIME_CLOCK"):
        client.runtime.perform(Work(Action.WOL,tid("bad-clock"),lambda *args:pytest.fail("dispatched")))


def test_empty_authority_needs_explicit_commissioning(setup):
    setup.store.document=empty_document(DOMAIN,Capacity(1,1,1,1)); setup.store.bump()
    client=setup.make(); before=setup.store.commits
    assert not client.runtime.tick() and client.runtime.reason == "COMMISSIONING_REQUIRED"
    assert setup.store.commits == before


def test_invalid_shared_callback_cannot_return_arbitrary_effect_plan(setup):
    client=setup.make(utc=220); assert client.runtime.tick()
    with pytest.raises(AuthorityError,match="SHARED_PLAN_BINDING"):
        client.runtime.perform(Work(Action.REPAIR,tid("bad-plan"),lambda *args:object()))
    assert not client.local.state.receipts


def test_stop_before_native_worker_start_never_reads_authority(setup):
    from threading import Event
    from tb4.desktop.worker import run_native_watchdog
    from tb4.desktop.telemetry import Telemetry
    client=setup.make(); stop=Event(); stop.set(); before=setup.store.reads
    assert run_native_watchdog(client.context,Telemetry("watchdog"),stop) == 0
    assert setup.store.reads == before and not client.scheduled


def test_native_factory_does_not_enter_legacy_tree_repair(setup,monkeypatch):
    import tb4.watchdog.runtime as module
    client=setup.make(); before=setup.store.reads
    monkeypatch.setattr(module,"TreeHealer",lambda *args:pytest.fail("legacy tree repair"))
    runtime=module.create_runtime_from_context(client.context)
    assert type(runtime) is NativeWatchdogRuntime and setup.store.reads == before
    assert not runtime.tick()


def test_desktop_entry_emits_paused_reason_without_any_worker_side_effect(setup,monkeypatch):
    from tb4.desktop.worker import run_native_watchdog
    from tb4.desktop.telemetry import Telemetry, decode_snapshot
    from tb4.service_host import ServiceHost
    client=setup.make(); snapshots=[]
    telemetry=Telemetry("watchdog")
    class Stop:
        stopped=False
        def is_set(self): return self.stopped
        def set(self): self.stopped=True
        def wait(self,delay):
            snapshots.append(telemetry.snapshot()); self.set()
    monkeypatch.setattr(ServiceHost,"install_signal_handlers",lambda self:None)
    assert run_native_watchdog(client.context,telemetry,Stop()) == 0
    assert snapshots[0]["process_state"] == "PAUSED" and snapshots[0]["stage"] == "OLDER_DOG_DETECTED"
    assert decode_snapshot(json.dumps(snapshots[0]).encode(), "watchdog") == snapshots[0]
    assert not client.scheduled
