"""Historical cause remains unknown; these are controlled current-source paths."""
import pytest

from tools.experiments.result_publication import SCENARIOS, main, run_scenario


def events(result, event): return [row for row in result["trace"] if row["event"] == event]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_schedule_is_bounded_and_executes_once_without_real_process(scenario):
    value = run_scenario(scenario)
    assert value["scope"] == "SYNTHETIC_ONLY_NO_PROCESS_OR_NETWORK"
    assert value["execution_calls"] == 1 and len(value["trace"]) < 256
    assert value["recorded_exit_code"] == 0 and value["recorded_result_hash_valid"]
    assert value["body_result"] == "DONE"
    assert value["synthetic_elapsed_s"] < 1


@pytest.mark.parametrize("scenario", ["baseline", "lost-reply", "stale-result-media", "http-429"])
def test_ordinary_success_and_reconcilable_transport_cases_are_controls(scenario):
    value = run_scenario(scenario)
    assert value["pipeline_outcome"] == "RETURNED" and value["final_state"] == "FETCH_BALL_DONE"
    assert value["original_result_unchanged"]
    assert value["terminal_wire_calls"] == (2 if scenario == "http-429" else 1)
    if scenario == "lost-reply":
        assert events(value,"normalized_terminal")[0]["outcome"] == "AMBIGUOUS"
    if scenario == "stale-result-media":
        # Initial claimed/chew/result writes only; delayed reads never replay the write.
        assert value["body_writes"] == run_scenario("baseline")["body_writes"]
        assert len(events(value,"media")) > len(events(run_scenario("baseline"),"media"))


@pytest.mark.parametrize("scenario", ["benign-version", "stale-precheck"])
def test_nonownership_version_conflict_strands_same_verified_done_result(scenario):
    value = run_scenario(scenario)
    assert value["pipeline_outcome"] == "PUBLICATION_ERROR"
    assert value["final_state"] == "FETCH_BALL_RETURNING" and value["final_generation"] == 7
    assert value["original_result_unchanged"] and value["terminal_wire_calls"] == 0
    assert value["terminal_attempts"] == 1
    assert events(value,"normalized_terminal") == [{"event":"normalized_terminal","outcome":"CONFLICT"}]
    assert events(value,"terminal_report")[0]["probes"] == 0
    attempted = events(value,"terminal_attempt")[0]["expected_version"]
    latest = events(value,"metadata")[-1]["version"]
    assert attempted != latest


def test_real_generation_change_before_fence_is_distinct_and_stops_publication():
    value = run_scenario("foreign-before-fence")
    assert value["pipeline_outcome"] == "STALE"
    assert value["final_generation"] == 8 and value["terminal_attempts"] == 0
    assert not value["original_result_unchanged"]
    assert events(value,"terminal_report")[0]["outcome"] == "STALE_FENCE"


def test_precheck_is_not_atomic_and_new_generation_can_be_renamed_after_it():
    value = run_scenario("foreign-after-precheck")
    assert value["pipeline_outcome"] == "RETURNED"
    assert value["final_generation"] == 8 and value["final_state"] == "FETCH_BALL_DONE"
    assert not value["original_result_unchanged"]
    fields = events(value,"terminal_wire")[0]["fields"]
    assert fields == ["body","fields","fileId","supportsAllDrives"]
    assert value["terminal_wire_calls"] == 1


@pytest.mark.parametrize("scenario,normalized,report", [
    ("http-409","CONFLICT","STATE_CONFLICT"), ("http-412","AMBIGUOUS","UNCONFIRMED")])
def test_provider_status_normalization_is_not_proof_of_logical_owner_conflict(scenario,normalized,report):
    value = run_scenario(scenario)
    assert value["pipeline_outcome"] == "PUBLICATION_ERROR"
    assert value["final_state"] == "FETCH_BALL_RETURNING" and value["original_result_unchanged"]
    assert events(value,"normalized_terminal")[0]["outcome"] == normalized
    assert events(value,"terminal_report")[0]["outcome"] == report
    assert value["terminal_wire_calls"] == 1


def test_successful_rename_with_later_benign_version_is_unconfirmed_not_replayed():
    value = run_scenario("post-apply-version-drift")
    assert value["pipeline_outcome"] == "PUBLICATION_ERROR"
    assert value["final_state"] == "FETCH_BALL_DONE" and value["original_result_unchanged"]
    assert events(value,"terminal_report")[0]["outcome"] == "UNCONFIRMED"
    assert value["terminal_wire_calls"] == 1 and events(value,"terminal_report")[0]["probes"] > 1


def test_legacy_benign_metadata_counterexample_requires_selected_r2_authority():
    # RP-015 ports the required invariant to tests/drive/test_docs_authority.py.
    # Keep the legacy counterexample; it is not a qualified R2 fallback backend.
    value = run_scenario("benign-version")
    assert value["original_result_unchanged"] and value["execution_calls"] == 1
    assert value["pipeline_outcome"] == "PUBLICATION_ERROR"


@pytest.mark.parametrize("argument", ["--root", "--token", "--endpoint", "--replay"])
def test_diagnostic_cannot_be_pointed_at_real_deployment(argument):
    with pytest.raises(SystemExit) as caught: main([argument,"synthetic"])
    assert caught.value.code == 2
