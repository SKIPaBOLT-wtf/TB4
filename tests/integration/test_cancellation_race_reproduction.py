from types import SimpleNamespace
import threading

import pytest

from tb4.fetcher.runtime import _HeartbeatExecutor
from tools.experiments.cancellation_race import SCENARIOS, main, run_scenario


PLATFORMS=("windows","posix")


@pytest.mark.parametrize("platform",PLATFORMS)
@pytest.mark.parametrize("scenario",SCENARIOS)
def test_all_schedules_keep_separate_bounded_ack_signal_exit_and_marker_evidence(scenario,platform):
    value=run_scenario(scenario,platform)
    assert value["scope"]=="SYNTHETIC_ONLY_NO_PROCESS_OR_NETWORK"
    assert value["markers"][0]=="PRE_WAIT" and len(value["trace"])<256
    assert sum(row["event"]=="started" for row in value["trace"])==1
    assert value["signal_attempts"]==sum(row["event"]=="signal_attempt" for row in value["trace"])
    assert value["finished_s"]<=3


@pytest.mark.parametrize("platform",PLATFORMS)
@pytest.mark.parametrize("scenario,code",[("late-cancel-zero",0),("late-cancel-nonzero",7)])
def test_slow_cancel_check_acknowledges_but_falsely_classifies_natural_exit(scenario,code,platform):
    value=run_scenario(scenario,platform)
    assert value["actual_exit_code"]==code and value["markers"]==["PRE_WAIT","POST_WAIT"]
    assert value["ack_code"]=="CANCEL_SIGNALLED" and value["stop_state"]=="STOP_BALL_ACKNOWLEDGED"
    assert value["signal_attempts"]==0 and value["reported_exit_code"] is None
    assert value["report_disposition"]=="CANCELLED" and value["classification"]=="CANCELLED"
    assert next(row for row in value["trace"] if row["event"]=="termination_enter")["already_exited"]


@pytest.mark.parametrize("platform",PLATFORMS)
def test_timely_cancel_control_has_actual_signal_and_no_post_wait_marker(platform):
    value=run_scenario("timely-cancel",platform)
    assert value["ack_code"]=="CANCEL_SIGNALLED" and value["signal_attempts"]==1
    assert value["markers"]==["PRE_WAIT"] and value["actual_exit_code"]==-15
    assert value["report_disposition"]=="CANCELLED" and not value["child_still_active"]
    assert value["finished_s"]==0.25
    events=[row["event"] for row in value["trace"]]
    assert events.index("provider_check_end")<events.index("signal_attempt")


@pytest.mark.parametrize("platform",PLATFORMS)
def test_provider_wait_delays_local_runtime_enforcement_even_with_independent_pulses(platform):
    value=run_scenario("runtime-blocked",platform)
    first=next(row for row in value["trace"] if row["event"]=="signal_attempt")
    assert first["at"]==2.05 and value["local_runtime_limit_s"]==1
    assert value["independent_heartbeat_model_ticks"]>=8
    assert value["report_disposition"]=="TIMED_OUT" and value["markers"]==["PRE_WAIT"]


@pytest.mark.parametrize("platform",PLATFORMS)
def test_natural_exit_during_slow_no_cancel_check_can_evade_runtime_limit(platform):
    value=run_scenario("runtime-natural-during-wait",platform)
    assert value["local_runtime_limit_s"]==1 and value["finished_s"]==2.05
    assert value["actual_exit_code"]==0 and value["reported_exit_code"]==0
    assert value["classification"]=="DONE" and value["signal_attempts"]==0
    assert value["markers"]==["PRE_WAIT","POST_WAIT"]


@pytest.mark.parametrize("platform",PLATFORMS)
def test_stale_cancel_request_does_not_signal_another_generation(platform):
    value=run_scenario("stale-cancel",platform)
    assert value["ack_code"]=="NO_MATCH" and value["signal_attempts"]==0
    assert value["report_disposition"]=="EXITED" and value["classification"]=="DONE"


@pytest.mark.parametrize("platform",PLATFORMS)
def test_already_finished_before_initial_poll_never_checks_cancel(platform):
    value=run_scenario("exit-before-first-check",platform)
    assert value["ack_code"] is None and value["signal_attempts"]==0
    assert value["classification"]=="DONE" and value["reported_exit_code"]==0
    assert not any(row["event"]=="provider_check_begin" for row in value["trace"])


@pytest.mark.parametrize("platform",PLATFORMS)
def test_exit_between_ack_and_signal_also_loses_real_exit_evidence(platform):
    value=run_scenario("exit-before-signal",platform)
    assert value["actual_exit_code"]==0 and value["signal_attempts"]==0
    assert value["markers"]==["PRE_WAIT","POST_WAIT"]
    assert value["report_disposition"]=="CANCELLED" and value["reported_exit_code"] is None


@pytest.mark.parametrize("platform",PLATFORMS)
def test_denied_termination_is_not_trustworthy_cancelled_result(platform):
    value=run_scenario("termination-fails",platform)
    assert value["report_disposition"]=="TERMINATION_FAILED"
    assert value["classification"]=="UNTRUSTWORTHY_TERMINATION" and value["child_still_active"]
    assert value["signal_attempts"]==(2 if platform=="windows" else 4)
    assert value["markers"]==["PRE_WAIT"]


@pytest.mark.parametrize("platform",PLATFORMS)
@pytest.mark.xfail(strict=True,reason="RP-044/045/046: retain natural exit during slow cancel; ACK is not interruption")
def test_required_invariant_late_cancel_preserves_natural_exit(platform):
    value=run_scenario("late-cancel-zero",platform)
    assert value["actual_exit_code"]==0 and value["signal_attempts"]==0
    assert value["report_disposition"]=="EXITED" and value["reported_exit_code"]==0


@pytest.mark.parametrize("platform",PLATFORMS)
@pytest.mark.xfail(strict=True,reason="RP-044/045: provider I/O cannot delay monotonic runtime enforcement")
def test_required_invariant_runtime_supervision_is_independent_of_provider_wait(platform):
    value=run_scenario("runtime-blocked",platform)
    first=next(row for row in value["trace"] if row["event"]=="signal_attempt")
    assert first["at"]<=value["local_runtime_limit_s"]+0.05


def test_actual_heartbeat_wrapper_runs_provider_tick_in_separate_thread():
    entered,release=threading.Event(),threading.Event()
    sentinel=object()
    observed=[]
    def tick(**kwargs):
        entered.set()
        assert release.wait(2), "bounded heartbeat fixture release missing"
    def execute(body,*,now_epoch_s,cancel_requested):
        assert entered.wait(2), "heartbeat worker did not enter fixture"
        observed.append(not release.is_set())
        release.set()
        return sentinel
    wrapper=_HeartbeatExecutor(SimpleNamespace(execute=execute),SimpleNamespace(tick=tick),threading.Event(),tick_s=0.01)
    try:
        assert wrapper.execute({"operation_id":"synthetic","generation":1},now_epoch_s=0) is sentinel
    finally: release.set()
    assert observed==[True]


@pytest.mark.parametrize("argument",["--pid","--host","--token","--replay"])
def test_diagnostic_rejects_external_process_and_deployment_arguments(argument):
    with pytest.raises(SystemExit) as caught: main([argument,"synthetic"])
    assert caught.value.code==2
