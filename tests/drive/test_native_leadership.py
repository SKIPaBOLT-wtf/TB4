"""RP-016 ownership conformance on real request construction and atomic model."""
import copy
from dataclasses import replace
import hashlib
from itertools import permutations
from types import SimpleNamespace

import pytest

from tb4.drive.docs_authority import AuthorityError, NativeDocsAuthority
from tb4.drive.leadership import ClockSample, Grant, Leadership, LEADER, FORCE
from tb4.exchange_layout import Capacity, MAX_GENERATION, empty_document, empty_record
from test_native_docs_transport import BINDING, DOMAIN, MemoryAuthority, WireStore, wire_document


ACTORS = tuple(f"30000000-0000-4000-8000-{i:012d}" for i in (1,2,3))
ENROLLMENT = {actor:f"synthetic-computer-{i}" for i,actor in enumerate(ACTORS)}


def tid(label): return hashlib.sha256(label.encode()).hexdigest()
def clock(utc=100, monotonic=0, trusted=True, reliable=True):
    return ClockSample(utc,monotonic,trusted,reliable)


@pytest.fixture(params=["wire","atomic-model"])
def system(request):
    store = WireStore(empty_document(DOMAIN,Capacity(1,1,1,1)))
    def make(actor):
        backend = NativeDocsAuthority(store.client(actor),BINDING) if request.param=="wire" else MemoryAuthority(store)
        return Leadership(backend,actor=actor,enrollment=ENROLLMENT)
    leaders = [make(actor) for actor in ACTORS]
    first = leaders[0]
    plan = first.acquire(first.observe(clock()),transition=tid("commission"),commissioning=True)
    result = first.commit(plan,mode="START")
    assert result.outcome=="CONFIRMED"
    return store,leaders,first.confirmed_grant(plan,result),make


def takeover(leader,*,utc=220,transition="takeover"):
    plan=leader.acquire(leader.observe(clock(utc)),transition=tid(transition))
    result=leader.commit(plan,mode="START")
    return plan,result


@pytest.mark.parametrize("order",list(permutations(range(3))))
def test_simultaneous_stale_starts_have_one_atomic_winner_and_no_sink_barrier(system,order):
    store,leaders,_,_=system
    store.document["records"]["target.000.work"] = dict(generation=7,operation_id="old-unknown",
        retention="UNKNOWN",body={"effects":"UNKNOWN","target_reachable":False})
    retained=copy.deepcopy(store.document["records"]["target.000.work"])
    plans=[l.acquire(l.observe(clock(220)),transition=tid("claim"+str(i))) for i,l in enumerate(leaders)]
    outcomes=[leaders[i].commit(plans[i],mode="START").outcome for i in order]
    assert outcomes==["CONFIRMED","SUPERSEDED","SUPERSEDED"]
    row=store.document["records"][LEADER]
    assert row["body"]["owner"]==ACTORS[order[0]] and row["generation"]==2
    assert row["body"]["phase"]=="ACTIVE" and store.commits==2
    assert store.document["records"]["target.000.work"]==retained


def test_first_read_of_stale_timestamp_takes_over_without_second_wait_window(system):
    store,leaders,_,_=system
    with pytest.raises(AuthorityError,match="INCUMBENT_FRESH"):
        leaders[1].acquire(leaders[1].observe(clock(219)),transition=tid("early"))
    _,result=takeover(leaders[1])
    assert result.outcome=="CONFIRMED" and result.writes==1


def test_renewal_rejects_prepared_stale_candidate_and_resumed_old_actor(system):
    store,leaders,grant,_=system
    candidate=leaders[1].acquire(leaders[1].observe(clock(220)),transition=tid("candidate"))
    renew=leaders[0].renew(leaders[0].observe(clock(220)),grant,transition=tid("renew"))
    assert leaders[0].commit(renew,mode="START").outcome=="CONFIRMED"
    assert leaders[1].commit(candidate,mode="START").outcome=="SUPERSEDED"
    _,result=takeover(leaders[1],utc=340)
    assert result.outcome=="CONFIRMED"
    assert not leaders[0].current_before_dispatch(grant,clock(340))
    with pytest.raises(AuthorityError,match="OWNER_SUPERSEDED"):
        leaders[0].renew(leaders[0].observe(clock(340)),grant,transition=tid("old-renew"))


def test_forced_flag_stops_old_writes_and_transfers_fresh_role_without_ack(system):
    store,leaders,grant,_=system
    incumbent,requester,_=leaders
    old_renew=incumbent.renew(incumbent.observe(clock(101)),grant,transition=tid("paused-renew"))
    plan=requester.request_force(requester.observe(clock(101)),request_id=tid("force"),user_requested=True)
    assert requester.commit(plan,mode="START").outcome=="CONFIRMED"
    assert store.document["records"][LEADER]["body"]["computer_name"]==ENROLLMENT[ACTORS[0]]
    assert store.document["records"][FORCE]["body"]["computer_name"]==ENROLLMENT[ACTORS[1]]
    assert incumbent.commit(old_renew,mode="START").outcome=="SUPERSEDED"
    assert not incumbent.current_before_dispatch(grant,clock(101))
    claim=requester.claim_requested(requester.observe(clock(101)),request_id=tid("force"))
    report=requester.commit(claim,mode="START")
    new_grant=requester.confirmed_grant(claim,report)
    assert new_grant.epoch==2 and requester.current_before_dispatch(new_grant,clock(101))
    assert store.document["records"][FORCE]==empty_record(2)


def test_competing_force_request_and_wrong_requester_cannot_steal_flag(system):
    _,leaders,_,_=system
    a,b,c=leaders
    with pytest.raises(AuthorityError,match="LOCAL_USER_REQUEST_REQUIRED"):
        b.request_force(b.observe(clock(101)),request_id=tid("force"),user_requested=False)
    plan=b.request_force(b.observe(clock(101)),request_id=tid("force"),user_requested=True)
    assert b.commit(plan,mode="START").outcome=="CONFIRMED"
    with pytest.raises(AuthorityError,match="FORCE_UNAVAILABLE"):
        c.request_force(c.observe(clock(101)),request_id=tid("other"),user_requested=True)
    with pytest.raises(AuthorityError,match="FORCE_UNAVAILABLE"):
        c.claim_requested(c.observe(clock(101)),request_id=tid("force"))


def test_crashed_requester_flag_expires_and_stale_takeover_can_clear_it(system):
    store,leaders,grant,_=system
    a,b,c=leaders
    request=b.request_force(b.observe(clock(101)),request_id=tid("force"),user_requested=True)
    assert b.commit(request,mode="START").outcome=="CONFIRMED"
    with pytest.raises(AuthorityError,match="REQUEST_NOT_EXPIRED"):
        c.expire_request(c.observe(clock(220)))
    # Ordinary stale claim can win before flag expiry, no requester/sink ACK.
    _,result=takeover(c,utc=220)
    assert result.outcome=="CONFIRMED" and store.document["records"][FORCE]==empty_record(2)
    with pytest.raises(AuthorityError,match="FORCE_UNAVAILABLE"):
        b.claim_requested(b.observe(clock(221)),request_id=tid("force"))


def test_explicit_expiry_clear_is_conditional_and_does_not_change_owner(system):
    store,leaders,grant,_=system
    request=leaders[1].request_force(leaders[1].observe(clock(101)),request_id=tid("force"),user_requested=True)
    assert leaders[1].commit(request,mode="START").outcome=="CONFIRMED"
    plan=leaders[2].expire_request(leaders[2].observe(clock(221)))
    assert leaders[2].commit(plan,mode="START").outcome=="CONFIRMED"
    assert store.document["records"][LEADER]["body"]["owner"]==ACTORS[0]
    assert leaders[0].current_before_dispatch(grant,clock(221))


def test_uncertain_wall_clock_uses_bounded_unchanged_heartbeat_not_unrelated_writes(system):
    store,leaders,_,_=system
    b=leaders[1]; start=b.observe(clock(None,0,False))
    assert not b.stale(b.observe(clock(None,119,False)),since=start)
    store.document["records"]["global.summary"]=dict(generation=1,operation_id="summary",retention="RETAINED",body={"value":"changed"})
    store.bump()
    observed=b.observe(clock(None,120,False))
    assert b.stale(observed,since=start)
    plan=b.acquire(observed,transition=tid("uncertain"),since=start)
    report=b.commit(plan,mode="START")
    assert report.outcome=="CONFIRMED"
    assert store.document["records"][LEADER]["body"]["heartbeat_at"] is None
    assert store.document["records"]["global.summary"]["body"]=={"value":"changed"}


def test_heartbeat_progress_and_unreliable_or_reversed_monotonic_prevent_false_staleness(system):
    _,leaders,grant,_=system
    b=leaders[1];start=b.observe(clock(None,20,False))
    assert not b.stale(b.observe(clock(None,10,False)),since=start)
    assert not b.stale(b.observe(clock(None,200,False,False)),since=start)
    renewal=leaders[0].renew(leaders[0].observe(clock(None,100,False)),grant,transition=tid("progress"))
    assert leaders[0].commit(renewal,mode="START").outcome=="CONFIRMED"
    assert not b.stale(b.observe(clock(None,200,False)),since=start)


def test_backward_wall_clock_qualifies_monotonic_window_without_backdated_heartbeat(system):
    store,leaders,_,_=system
    b=leaders[1];start=b.observe(clock(50,0))
    final=b.observe(clock(55,120))
    plan=b.acquire(final,transition=tid("backward"),since=start)
    assert b.commit(plan,mode="START").outcome=="CONFIRMED"
    assert store.document["records"][LEADER]["body"]["heartbeat_at"] is None


def test_partition_stops_authoritative_work_and_rejoin_observes_new_owner(system):
    store,leaders,grant,_=system
    store.on_read=lambda *_:(_ for _ in ()).throw(TimeoutError("synthetic partition"))
    # Wire normalizes transport exceptions; the atomic model is a deliberately
    # minimal independent CAS and may propagate the fixture's TimeoutError.
    with pytest.raises((AuthorityError,TimeoutError)):
        leaders[0].current_before_dispatch(grant,clock(220))
    assert store.commits==1
    store.on_read=None
    _,report=takeover(leaders[1]);assert report.outcome=="CONFIRMED"
    assert not leaders[0].current_before_dispatch(grant,clock(221))


def test_lost_acquisition_reply_is_read_back_once_without_second_claim(system):
    store,leaders,_,_=system
    store.after_write=lambda:(_ for _ in ()).throw(TimeoutError("lost synthetic response"))
    plan,report=takeover(leaders[1])
    assert report.outcome=="CONFIRMED" and report.writes==1 and store.commits==2
    assert leaders[1].confirmed_grant(plan,report).epoch==2


def test_restart_inspects_exact_acquisition_and_never_assumes_success(system):
    store,leaders,_,make=system
    b=leaders[1];plan=b.acquire(b.observe(clock(220)),transition=tid("restart"))
    store.after_write=lambda:(_ for _ in ()).throw(TimeoutError())
    old=wire_document(store.document,"opaque-a-1")
    # Suppress readback only after the actual atomic mutation.
    store.on_read=lambda _,response:copy.deepcopy(old) if store.commits>1 else response
    report=b.commit(plan,mode="START")
    assert report.outcome=="UNKNOWN" and report.inspect_required
    with pytest.raises(AuthorityError,match="ACQUISITION_UNCONFIRMED"):b.confirmed_grant(plan,report)
    store.on_read=None
    resumed=make(ACTORS[1]);report=resumed.commit(plan,mode="INSPECT")
    assert report.outcome=="CONFIRMED" and report.writes==0 and store.commits==2
    assert resumed.confirmed_grant(plan,report).epoch==2


def test_dispatch_check_cannot_revoke_external_effect_after_suspension(system):
    _,leaders,grant,_=system
    effects=[]
    assert leaders[0].current_before_dispatch(grant,clock(220))
    # Simulates suspension AFTER the check; no actual external action is run.
    _,report=takeover(leaders[1]);assert report.outcome=="CONFIRMED"
    effects.append("already-admitted-old-effect")
    assert effects==["already-admitted-old-effect"]
    assert not leaders[0].current_before_dispatch(grant,clock(221))


def test_epoch_overflow_never_wraps_or_reuses_authority(system):
    store,leaders,_,_=system
    row=store.document["records"][LEADER]
    row["generation"]=row["body"]["epoch"]=MAX_GENERATION
    store.document["records"][FORCE]=empty_record(MAX_GENERATION)
    with pytest.raises(AuthorityError,match="EPOCH_EXHAUSTED"):
        leaders[1].acquire(leaders[1].observe(clock(220)),transition=tid("overflow"))
    assert store.commits==1


def test_changed_observation_foreign_plan_or_manufactured_success_cannot_grant_role(system):
    _,leaders,_,_=system
    observed=leaders[1].observe(clock(220))
    altered=replace(observed,progress=b"forged")
    with pytest.raises(AuthorityError,match="OBSERVATION_CHANGED"):
        leaders[1].acquire(altered,transition=tid("forged"))
    plan=leaders[1].acquire(observed,transition=tid("legitimate"))
    with pytest.raises(AuthorityError,match="ELECTION_PLAN"):leaders[2].commit(plan,mode="START")
    with pytest.raises(AuthorityError,match="ACQUISITION_UNCONFIRMED"):
        leaders[1].confirmed_grant(plan,SimpleNamespace(outcome="CONFIRMED"))


@pytest.mark.parametrize("change",["owner","display","epoch","sequence","extra","force-generation"])
def test_malformed_persisted_leadership_stops_before_any_mutation(system,change):
    store,leaders,_,_=system;body=store.document["records"][LEADER]["body"]
    if change=="owner":body["owner"]="not-enrolled"
    elif change=="display":body["computer_name"]="wrong-computer"
    elif change=="epoch":body["epoch"]=True
    elif change=="sequence":body["heartbeat_sequence"]=-1
    elif change=="extra":body["unexpected"]="value"
    else:store.document["records"][FORCE]["generation"]=0
    with pytest.raises(AuthorityError):leaders[1].observe(clock(220))
    assert store.commits==1


@pytest.mark.parametrize("sample",[(None,0,True,True),(100,float("nan"),True,True),
                                  (True,0,True,True),(100,-1,True,True),(100,0,1,True)])
def test_invalid_clock_samples_are_not_freshness_evidence(sample):
    with pytest.raises(AuthorityError):ClockSample(*sample)


def test_same_computer_display_name_is_not_the_owner_identity():
    store=WireStore(empty_document(DOMAIN,Capacity(1,1,1,1)))
    enrollment={a:"same-synthetic-computer-name" for a in ACTORS}
    a,b=[Leadership(NativeDocsAuthority(store.client(actor),BINDING),actor=actor,enrollment=enrollment)
         for actor in ACTORS[:2]]
    plan=a.acquire(a.observe(clock()),transition=tid("commission"),commissioning=True)
    report=a.commit(plan,mode="START");grant=a.confirmed_grant(plan,report)
    assert not b.current_before_dispatch(grant,clock(101))
    with pytest.raises(AuthorityError,match="INCUMBENT_FRESH"):
        b.acquire(b.observe(clock(101)),transition=tid("same-name"))


def test_stale_snapshot_cannot_overwrite_incumbent_renewal_in_actual_cas():
    store=WireStore(empty_document(DOMAIN,Capacity(1,1,1,1)))
    a,b=[Leadership(NativeDocsAuthority(store.client(actor),BINDING),actor=actor,enrollment=ENROLLMENT)
         for actor in ACTORS[:2]]
    p=a.acquire(a.observe(clock()),transition=tid("commission"),commissioning=True)
    r=a.commit(p,mode="START");grant=a.confirmed_grant(p,r)
    observed=b.observe(clock(220));candidate=b.acquire(observed,transition=tid("stale"))
    renew=a.renew(a.observe(clock(220)),grant,transition=tid("renew"))
    assert a.commit(renew,mode="START").outcome=="CONFIRMED"
    old=wire_document(observed.snapshot.document(),observed.snapshot.revision)
    calls=store.reads
    store.on_read=lambda count,response:copy.deepcopy(old) if count==calls+1 else response
    report=b.commit(candidate,mode="START")
    assert report.outcome=="SUPERSEDED" and report.writes==1 and store.commits==2


def test_clock_uncertain_forced_flag_does_not_invent_an_expiry(system):
    _,leaders,_,_=system
    with pytest.raises(AuthorityError,match="FORCE_CLOCK_OR_ID"):
        leaders[1].request_force(leaders[1].observe(clock(None,0,False)),request_id=tid("force"),user_requested=True)
