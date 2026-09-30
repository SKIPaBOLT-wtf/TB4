from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest

from tb4.timing_contract import (OWNER, MAX_SEQUENCE, ActivityClock, ClockSet,
    TimingError, TimingProfile, claim_budget, effective_profile, modes as timing_modes,
    quota_budget, validate_deadlines)


def activity(age=0):
    clock = ActivityClock(0,10000,new_installation=True)
    clock.sample(age,10000+age)
    return clock


def modes(profile, clock, *, watchdog_activity=None, **holds):
    # Most boundary fixtures deliberately give both roles the same age. The
    # production interface requires separate role clocks even when co-located.
    return timing_modes(profile,clock if watchdog_activity is None else watchdog_activity,clock,**holds)


def test_other_targets_new_work_refreshes_watchdog_but_not_this_fetcher():
    watchdog, fetcher = activity(4000), activity(1500)
    assert watchdog.accepted(9)
    state = timing_modes(TimingProfile(),watchdog,fetcher)
    assert state["network_s"] == 60 and state["fetcher_mode"] == "SLOW"
    assert state["watchdog_activity_sequence"] == 9 and state["activity_sequence"] == 0
    assert fetcher.age_s == 1500


def test_export_preserves_exact_owner_intervals_and_marks_draft():
    data = json.loads((Path(__file__).resolve().parents[2] / "protocol/drafts/r2-timing-profile.json").read_text(encoding="utf-8"))
    assert data["compatibility_status"] == "UNRELEASED"
    assert data["owner_intervals"] == OWNER
    assert data["default_profile"] == asdict(TimingProfile())
    assert TimingProfile.parse(data["default_profile"]) == TimingProfile()


@pytest.mark.parametrize("name", list(OWNER))
def test_owner_intervals_cannot_be_shortened_even_to_fit_quota(name):
    with pytest.raises(TimingError,match="OWNER_CADENCE"):
        replace(TimingProfile(),**{name:OWNER[name]-1})


@pytest.mark.parametrize("key,value,code", [
    ("inbox_s",0,"PROFILE_RANGE"),("control_s",True,"PROFILE_RANGE"),
    ("fetcher_heartbeat_s",1.0,"PROFILE_RANGE"),("local_supervision_s",float("nan"),"PROFILE_RANGE"),
    ("local_supervision_s",2,"PROFILE_RANGE"),("idle_policy",[],"IDLE_POLICY"),
    ("idle_policy","SUSPEND","IDLE_POLICY"),("launcher_kind",[],"LAUNCHER_KIND"),
    ("launcher_kind","SSH","LAUNCHER_BOUND"),("launcher_bound_s",30,"LAUNCHER_BOUND"),
    ("lease_stale_s",90,"LEASE_TOO_SHORT"),("fetcher_fresh_s",180,"FRESHNESS_TOO_SHORT"),
    ("publication_wait_s",60,"PUBLICATION_TOO_SHORT")])
def test_impossible_or_malformed_profile_fails_closed(key,value,code):
    with pytest.raises(TimingError,match=code):
        TimingProfile.parse({**asdict(TimingProfile()),key:value})


def test_closed_profile_rejects_old_or_extra_fields():
    for data in ({}, {**asdict(TimingProfile()),"poll_interval_s":1}):
        with pytest.raises(TimingError,match="PROFILE_SHAPE"):
            TimingProfile.parse(data)


@pytest.mark.parametrize("age,network,fetcher,poll", [
    (0,60,"ACTIVE",20),(1199.99,60,"ACTIVE",20),(1200,60,"SLOW",1200),
    (3599.99,60,"SLOW",1200),(3600,600,"SLOW",1200)])
def test_owner_inactivity_boundaries_are_exact_and_independent(age,network,fetcher,poll):
    state = modes(TimingProfile(),activity(age))
    assert (state["network_s"],state["fetcher_mode"],state["fetcher_poll_s"]) == (network,fetcher,poll)


@pytest.mark.parametrize("hold", ["pending","executing","publication","unread","unknown"])
@pytest.mark.parametrize("policy", ["SLOW","EXIT"])
def test_unfinished_work_holds_fetcher_without_resetting_activity_or_network_clock(hold,policy):
    clock = activity(4000); profile = replace(TimingProfile(),idle_policy=policy)
    state = modes(profile,clock,**{hold:True})
    assert state["fetcher_mode"] == "BUSY" and state["fetcher_poll_s"] == 20
    assert state["network_s"] == 600 and clock.age_s == 4000
    released = modes(profile,clock)
    assert released["fetcher_mode"] == ("SLOW" if policy == "SLOW" else "EXITED")


def test_only_new_scoped_acceptance_refreshes_activity_and_sequence_survives_restart():
    clock = activity(1100)
    assert clock.accepted(4)
    clock.sample(1500,11500)
    assert clock.age_s == 400
    assert not clock.accepted(4) and not clock.accepted(3)
    before = clock.checkpoint()
    for _ in range(5):
        modes(TimingProfile(),clock); clock.checkpoint()
    assert clock.checkpoint() == before
    restored = ActivityClock(0,12000,saved=before,elapsed_wall_trusted=True)
    assert restored.age_s == 900 and restored.sequence == 4
    assert not restored.accepted(4)
    assert restored.accepted(5) and restored.age_s == 0


def test_gui_restart_and_missing_or_uncertain_persistence_do_not_reset_idle():
    saved = activity(1500).checkpoint()
    restarted = ActivityClock(0,11600,saved=saved,elapsed_wall_trusted=True)
    assert restarted.age_s == 1600 and modes(TimingProfile(),restarted)["fetcher_mode"] == "SLOW"
    uncertain = ActivityClock(0,9000,saved=saved)
    assert uncertain.age_s == 1500 and not uncertain.known
    assert modes(replace(TimingProfile(),idle_policy="EXIT"),uncertain)["fetcher_mode"] == "HOLD_CLOCK"
    with pytest.raises(TimingError,match="ACTIVITY_RECOVERY_REQUIRED"):
        ActivityClock(0,12000)
    with pytest.raises(TimingError,match="ACTIVITY_RECOVERY_REQUIRED"):
        ActivityClock(0,12000,saved=saved,new_installation=True)


@pytest.mark.parametrize("field,value", [("age_s",-1),("sequence",True),("sequence",MAX_SEQUENCE+1),
    ("checkpoint_utc",float("inf")),("clock_known",1),("extra",True)])
def test_invalid_persisted_activity_is_not_treated_as_new_install(field,value):
    saved = activity().checkpoint(); saved[field] = value
    with pytest.raises(TimingError,match="ACTIVITY_IMAGE"):
        ActivityClock(0,10000,saved=saved)


def test_monotonic_sleep_and_verified_paused_clock_sleep_age_once_without_burst():
    includes_sleep = activity()
    includes_sleep.sample(1300,11300)
    assert includes_sleep.age_s == 1300 and includes_sleep.known
    paused = activity()
    paused.sample(1,11300,elapsed_wall_trusted=True)
    assert paused.age_s == 1300 and paused.known
    clocks = ClockSet(TimingProfile())
    due = clocks.due(1300)
    assert "lease" in due and "fetcher_poll" in due
    for name in due:
        clocks.completed(name,1300)
    assert clocks.due(1300) == ()
    assert clocks.due_at["lease"] == 1320


def test_unverified_wall_jump_backward_jump_and_cumulative_skew_hold_idle_transition():
    for utc in (9000,12000):
        clock = activity(); clock.sample(1,utc)
        assert clock.age_s == 1 and not clock.known
        assert modes(TimingProfile(),clock)["fetcher_mode"] == "HOLD_CLOCK"
    clock = activity()
    clock.sample(1,10006); assert clock.known
    clock.sample(2,10012); assert clock.known
    clock.sample(3,10018); assert not clock.known
    clock.sample(4,10019,elapsed_wall_trusted=True); assert clock.known
    assert clock.age_s == 4


def test_monotonic_regression_and_boolean_trust_flag_are_rejected_without_mutation():
    clock = activity(10); before = deepcopy(clock.__dict__)
    with pytest.raises(TimingError,match="MONOTONIC_REVERSED"):
        clock.sample(9,10011)
    with pytest.raises(TimingError,match="CLOCK_SAMPLE"):
        clock.sample(11,10011,elapsed_wall_trusted="yes")
    assert clock.__dict__ == before


def test_slow_poll_never_slows_lease_inbox_heartbeat_or_local_supervision():
    profile = TimingProfile(); clocks = ClockSet(profile)
    original = {k:clocks.due_at[k] for k in ("lease","inbox","watchdog_heartbeat","fetcher_heartbeat","standby")}
    clocks.set_modes(modes(profile,activity(1200)),0)
    for key,value in original.items(): assert clocks.due_at[key] == value
    clocks.completed("fetcher_poll",20)
    assert clocks.due_at["fetcher_poll"] == 1220
    clocks.completed("lease",20); assert clocks.due_at["lease"] == 40
    clocks.set_modes(modes(profile,activity(1200),executing=True),21)
    assert clocks.due_at["fetcher_poll"] == 41
    assert clocks.due_at["supervision"] == 21.25 and clocks.due_at["control"] == 26


def test_exited_fetcher_cannot_publish_heartbeat_but_watchdog_clocks_keep_running():
    profile = replace(TimingProfile(),idle_policy="EXIT"); clocks = ClockSet(profile)
    clocks.set_modes(modes(profile,activity(1200)),0)
    for key in ("fetcher_poll","fetcher_heartbeat","control","supervision"):
        assert clocks.due_at[key] is None
        with pytest.raises(TimingError,match="CLOCK_NAME"):
            clocks.completed(key,1)
    assert clocks.due_at["lease"] == 20 and clocks.due_at["inbox"] == 5


@pytest.mark.parametrize("mode,minimum", [("ACTIVE",86),("BUSY",86),("SLOW",1266)])
def test_claim_budget_includes_poll_ingress_visibility_queue_and_skew(mode,minimum):
    profile = TimingProfile()
    assert claim_budget(profile,fetcher_mode=mode) == minimum
    args = dict(fetcher_mode=mode,claim_ttl_s=minimum,run_limit_s=1,publication_wait_s=120)
    assert validate_deadlines(profile,**args)["run_limit_s"] == 1
    with pytest.raises(TimingError,match="CLAIM_TOO_SHORT"):
        validate_deadlines(profile,**{**args,"claim_ttl_s":minimum-1})


def test_old_120_second_claim_ttl_cannot_promise_delivery_to_slow_fetcher():
    with pytest.raises(TimingError,match="CLAIM_TOO_SHORT"):
        validate_deadlines(TimingProfile(),fetcher_mode="SLOW",claim_ttl_s=120,run_limit_s=300,publication_wait_s=120)


@pytest.mark.parametrize("kind", ["SSH","OS_SERVICE","EXTERNAL"])
def test_only_fresh_commissioned_launcher_can_shorten_slow_or_exited_wait(kind):
    profile = replace(TimingProfile(),idle_policy="EXIT",launcher_kind=kind,launcher_bound_s=90)
    assert claim_budget(profile,fetcher_mode="SLOW",route_fresh=True) == 176
    assert claim_budget(profile,fetcher_mode="SLOW",route_fresh=False) == 1266
    assert claim_budget(profile,fetcher_mode="EXITED",route_fresh=True) == 176
    with pytest.raises(TimingError,match="MANUAL_START_REQUIRED"):
        claim_budget(profile,fetcher_mode="EXITED",route_fresh=False)


def test_no_ssh_does_not_mean_no_fetcher_but_fully_exited_needs_external_launcher():
    profile = replace(TimingProfile(),idle_policy="EXIT")
    assert claim_budget(profile,fetcher_mode="ACTIVE") == 86
    with pytest.raises(TimingError,match="MANUAL_START_REQUIRED"):
        claim_budget(profile,fetcher_mode="EXITED",route_fresh=True)
    with pytest.raises(TimingError,match="CLOCK_UNQUALIFIED"):
        claim_budget(profile,fetcher_mode="HOLD_CLOCK")


def test_publication_wait_does_not_expire_unread_result_or_reuse_execution_timer():
    profile = TimingProfile()
    args = dict(fetcher_mode="ACTIVE",claim_ttl_s=86,run_limit_s=86400,publication_wait_s=120)
    assert validate_deadlines(profile,**args)["ack_recycle_after_s"] is None
    with pytest.raises(TimingError,match="ACK_CANNOT_EXPIRE_TO_RECYCLE"):
        validate_deadlines(profile,**args,ack_recycle_after_s=3600)
    with pytest.raises(TimingError,match="PUBLICATION_TOO_SHORT"):
        validate_deadlines(profile,**{**args,"publication_wait_s":119})


def test_effective_profile_exposes_honest_next_check_route_and_clock_uncertainty():
    profile = TimingProfile(); clocks = ClockSet(profile); state = modes(profile,activity(1200))
    clocks.set_modes(state,0); clocks.completed("fetcher_poll",20)
    effective = effective_profile(profile,state,clocks,utc=10020,monotonic=20)
    assert effective["next_fetcher_check_utc"] == 11220
    assert effective["fetcher_fast_s"] == 20 and effective["fetcher_slow_s"] == 1200
    assert effective["minimum_claim_ttl_s"] == 1266 and effective["fetcher_heartbeat_s"] == 120
    clock = activity(); clock.sample(1,12000); state = modes(profile,clock)
    effective = effective_profile(profile,state,clocks,utc=12000,monotonic=20)
    assert effective["next_fetcher_check_utc"] is None
    assert effective["minimum_claim_ttl_s"] is None and effective["delivery"] == "CLOCK_UNQUALIFIED"
    profile = replace(profile,idle_policy="EXIT"); state = modes(profile,activity(1200))
    clocks.set_modes(state,20)
    effective = effective_profile(profile,state,clocks,utc=12000,monotonic=20)
    assert effective["delivery"] == "MANUAL_START_REQUIRED" and effective["next_fetcher_check_utc"] is None


def test_quota_estimate_keeps_control_headroom_and_rejects_large_unqualified_population():
    profile = TimingProfile()
    budget = quota_budget(profile,active=0,slow=0,busy=8)
    assert budget == dict(reads_per_minute=213.75,writes_per_minute=23.25,
                         read_reserve=30,write_reserve=12,qualification="AVERAGE_ESTIMATE_ONLY")
    with pytest.raises(TimingError,match="QUOTA_INFEASIBLE"):
        quota_budget(profile,active=0,slow=0,busy=64)
    assert quota_budget(profile,active=0,slow=64,busy=0)["writes_per_minute"] == 58.25
    with pytest.raises(TimingError,match="QUOTA_INFEASIBLE"):
        quota_budget(profile,active=0,slow=64,busy=0,writes_per_minute=50)
    assert asdict(profile) == asdict(TimingProfile())


@pytest.mark.parametrize("field,value", [("active",True),("active",65),("busy",-1),
    ("standbys",1.0),("retry_factor",0.5),("read_reserve",0),("writes_per_minute",float("inf"))])
def test_invalid_quota_configuration_is_not_an_admission_promise(field,value):
    args = dict(active=8,slow=0,busy=0); args[field] = value
    with pytest.raises(TimingError):
        quota_budget(TimingProfile(),**args)


def test_invalid_mode_change_does_not_mutate_periodic_clocks():
    clocks = ClockSet(TimingProfile()); before = deepcopy(clocks.__dict__)
    state = modes(TimingProfile(),activity()); state["fetcher_poll_s"] = 1
    with pytest.raises(TimingError,match="MODE"):
        clocks.set_modes(state,100)
    assert clocks.__dict__ == before
