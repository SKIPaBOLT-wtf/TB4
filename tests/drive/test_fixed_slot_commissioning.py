"""Synthetic state-machine conformance; native provider/journal cases are separate."""
import copy
from dataclasses import replace
import json

import pytest

from tb4.drive.commissioning import (Allocation, Commissioner, SetupSpec, digest, seed_document)
from tb4.drive.docs_authority import AuthorityError, NativeDocsAuthority
from tb4.drive.leadership import Grant, Leadership
from tb4.exchange_layout import Capacity
from test_native_docs_transport import BINDING, DOMAIN, WireStore
from test_native_leadership import ACTORS, ENROLLMENT, clock, tid


class Journal:
    protected=locked=True
    def __init__(self,spec,actor):
        self.installation_id,self.setup_id=actor,spec.setup_id
        self.value={"spec":spec.fingerprint,"pending":None}
        self.fail=False
    def read(self):return copy.deepcopy(self.value)
    def save(self,value):
        if self.fail:raise AuthorityError("SYNTHETIC_JOURNAL_FAILURE")
        self.value=copy.deepcopy(value)


class Objects:
    mode="NATIVE_DOCS"
    llm_authorized=True
    def __init__(self,spec):
        self.spec,self.root_id=spec,spec.root_id
        self.created,self.calls={},[]
        self.before=None;self.lost=False
    def check_root(self):pass
    def prepare(self,key,op):return Allocation("raw-"+key.replace(".","-"),op)
    def create(self,key,allocation):
        self.calls.append(key)
        if self.before:self.before()
        assert allocation.object_id not in self.created
        self.created[allocation.object_id]=replace(allocation,seal=digest([key,allocation.object_id]))
        if self.lost:raise TimeoutError("SYNTHETIC_PRIVATE_CANARY")
    def inspect(self,key,allocation):
        found=self.created.get(allocation.object_id)
        if found is not None and allocation.seal is not None:
            assert found==allocation
        return found


def setup(capacity=Capacity(1,1,1,1)):
    spec=SetupSpec("synthetic-root",DOMAIN,tid("setup"),ACTORS[0],"NATIVE_DOCS",capacity)
    document=json.loads(seed_document(spec,ENROLLMENT[ACTORS[0]],clock()))
    assert document["records"]["global.force_request"] == dict(
        generation=1,operation_id=None,retention="FREE",body=None)
    store=WireStore(document)
    backend=NativeDocsAuthority(store.client(),BINDING)
    leader=Leadership(backend,actor=ACTORS[0],enrollment=ENROLLMENT)
    grant=Grant(ACTORS[0],1,spec.operation("authority"))
    assert leader.current_before_dispatch(grant,clock())
    port,journal=Objects(spec),Journal(spec,ACTORS[0])
    return spec,store,leader,grant,port,journal,Commissioner(spec,leader,grant,port,journal)


def finish(commissioner,limit=300,now=100):
    for _ in range(limit):
        state=commissioner.advance(clock(now))
        if state=="STORAGE_READY":return
        assert state in {"CONFIRMED","INSPECT_REQUIRED"}
    pytest.fail("Bounded commissioning did not finish")


@pytest.mark.parametrize("capacity",[Capacity(1,1,1,1),Capacity(),Capacity(64,16,128,32)],
                         ids=["minimum","default","maximum"])
def test_complete_fixed_capacity_once_and_repeat_preserves_bindings(capacity):
    spec,store,_,_,port,journal,c=setup(capacity)
    finish(c)
    before=copy.deepcopy(store.document)
    count=len(port.calls)
    assert count==2*capacity.devices and len(port.created)==count
    assert store.document["records"]["global.commissioning"]["body"]["state"]=="STORAGE_READY"
    assert store.document["records"]["global.settings"]["body"]["descriptor_state"]=="UNCONFIGURED"
    assert all(store.document["records"][k]["retention"]=="FREE" for k in spec.artifact_keys)
    assert c.advance(clock())=="STORAGE_READY"
    assert store.document==before and len(port.calls)==count and journal.read()["pending"] is None


def test_lost_creation_reply_inspects_allocated_id_without_duplicate():
    _,_,_,_,port,_,c=setup()
    port.lost=True
    assert c.advance(clock())=="UNKNOWN"
    assert len(port.created)==len(port.calls)==1
    port.lost=False
    assert c.advance(clock())=="CONFIRMED"
    finish(c)
    assert len(port.calls)==2


def test_no_receipt_or_absent_observation_never_authorizes_recreation():
    _,store,_,_,port,_,c=setup()
    def interrupted():raise TimeoutError("SYNTHETIC_PRIVATE_CANARY")
    port.before=interrupted
    assert c.advance(clock())=="UNKNOWN"
    assert not port.created and len(port.calls)==1
    port.before=None
    for _ in range(3):assert c.advance(clock())=="UNKNOWN"
    assert not port.created and len(port.calls)==1
    assert store.document["records"]["artifact.000.input"]["retention"]=="UNKNOWN"


def test_private_intent_failure_precedes_shared_or_object_mutation():
    _,store,_,_,port,journal,c=setup()
    journal.fail=True
    with pytest.raises(AuthorityError):c.advance(clock())
    assert not port.calls and store.commits==0


def test_recovered_pending_cas_is_inspect_only_even_if_creation_not_dispatched():
    spec,store,leader,grant,port,journal,c=setup()
    # Fail the local clearing checkpoint after shared intent has committed.
    original=journal.save
    def save(value):
        if value["pending"] is None:raise AuthorityError("SYNTHETIC_JOURNAL_FAILURE")
        original(value)
    journal.save=save
    with pytest.raises(AuthorityError):c.advance(clock())
    assert store.commits==1 and not port.calls and journal.read()["pending"] is not None
    journal.save=original
    resumed=Commissioner(spec,leader,grant,port,journal)
    assert resumed.advance(clock())=="CONFIRMED"
    assert resumed.advance(clock())=="UNKNOWN" and not port.calls


def test_standby_cannot_create_and_stale_successor_can_inspect_old_creation():
    spec,store,_,grant,port,_,old=setup()
    other=Leadership(NativeDocsAuthority(store.client("b"),BINDING),actor=ACTORS[1],enrollment=ENROLLMENT)
    journal=Journal(spec,ACTORS[1])
    standby=Commissioner(spec,other,Grant(ACTORS[1],1,grant.acquisition_id),port,journal)
    assert standby.advance(clock())=="SUPERSEDED" and not port.calls
    assert old.advance(clock())=="INSPECT_REQUIRED"
    plan=other.acquire(other.observe(clock(220)),transition=tid("takeover"))
    new=other.confirmed_grant(plan,other.commit(plan,mode="START"))
    resumed=Commissioner(spec,other,new,port,journal)
    assert resumed.advance(clock(220))=="CONFIRMED"
    assert old.advance(clock(220))=="SUPERSEDED"
    finish(resumed,now=220)
    assert len(port.calls)==2


@pytest.mark.parametrize("change",["root","mode","llm","journal-actor","journal-lock"])
def test_wrong_setup_capability_or_journal_refuses_before_create(change):
    spec,store,leader,grant,port,journal,_=setup()
    if change=="root":port.root_id="foreign"
    if change=="mode":port.mode="DRIVE_SYNC"
    if change=="llm":port.llm_authorized=False
    if change=="journal-actor":journal.installation_id=ACTORS[1]
    if change=="journal-lock":journal.locked=False
    with pytest.raises(AuthorityError):
        Commissioner(spec,leader,grant,port,journal).advance(clock())
    assert not port.calls and store.commits==0


def test_owner_changes_before_creation_intent_cas_no_old_create():
    spec,store,_,grant,port,_,old=setup()
    other=Leadership(NativeDocsAuthority(store.client("b"),BINDING),actor=ACTORS[1],enrollment=ENROLLMENT)
    def take_over(_):
        store.before_write=None
        plan=other.acquire(other.observe(clock(220)),transition=tid("race"))
        assert other.commit(plan,mode="START").outcome=="CONFIRMED"
    store.before_write=take_over
    assert old.advance(clock())=="SUPERSEDED"
    assert not port.calls
    assert store.document["records"]["artifact.000.input"]["retention"]=="FREE"

def test_ready_capacity_exhaustion_does_not_allocate_more_or_reset_records():
    spec,store,_,_,port,_,c=setup()
    finish(c)
    rows=store.document["records"]
    for key in spec.artifact_keys:
        rows[key]=dict(generation=1,operation_id=tid(key),retention="UNREAD",body={"synthetic":"retained"})
    from tb4.exchange_layout import admission
    assert not admission(store.document,0)["new_work_has_space"]
    before=copy.deepcopy(store.document)
    assert c.advance(clock())=="STORAGE_READY"
    assert store.document==before and len(port.calls)==2

@pytest.mark.parametrize("bad",["capacity","setup","domain","catalogue","duplicate-id"])
def test_changed_blueprint_or_allocation_never_silently_expands_or_replaces(bad):
    spec,store,_,_,port,_,c=setup()
    if bad=="capacity":
        store.document["capacity"]["devices"]=2
    elif bad=="setup":
        store.document["records"]["global.commissioning"]["body"]["setup_id"]=tid("other")
    elif bad=="domain":
        store.document["domain_id"]=ACTORS[2]
    elif bad=="catalogue":
        store.document["records"]["target.000.catalogue"]=dict(
            generation=1,operation_id=tid("enrolled"),retention="RETAINED",body={"synthetic":"occupied"})
    else:
        old_prepare=port.prepare
        port.prepare=lambda key,op:replace(old_prepare(key,op),object_id="same-raw")
        # Prove the external port itself cannot justify two canonical bindings.
        port.create=lambda key,allocation:port.created.update({
            allocation.object_id:replace(allocation,seal=digest([key,allocation.object_id]))})
    with pytest.raises((AuthorityError,AssertionError)):
        finish(c)
    assert store.document["records"]["global.commissioning"]["body"]["state"]=="PREPARING"
