from __future__ import annotations

from tb4.fetcher.execution_models import ExecutionDisposition
from tb4.watchdog.wake_manager import WakeManagerOutcome

from tests.support.simulation import SimulationHarness, execution_report


def test_awake_target_direct_job_returns_to_ready_without_runtime_folder_scan() -> None:
    sim = SimulationHarness()
    target = sim.add_target("target-a", online=True)
    sim.publish_pulse(target)
    sim.reset_operation_counts()

    sim.toss_job(target)
    result = sim.run_job(
        target,
        execution_report(ExecutionDisposition.EXITED, exit_code=0),
    )

    assert result.terminal_state == "DONE"
    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_DONE"

    sim.recycle_job(target)

    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_READY"
    assert sim.backend.operation_counts.get("list_children", 0) == 0


def test_sleeping_target_wakes_then_runs_job() -> None:
    sim = SimulationHarness()
    target = sim.add_target("target-a", online=False)
    sim.reset_operation_counts()

    sim.toss_wake(target)
    wake = sim.run_wake(target)

    assert wake.outcome is WakeManagerOutcome.DONE
    assert sim.state(target.wake_bone_id) == "WAKE_BONE_DONE"

    sim.toss_job(target)
    result = sim.run_job(
        target,
        execution_report(ExecutionDisposition.EXITED, exit_code=0),
    )

    assert result.terminal_state == "DONE"
    assert sim.backend.operation_counts.get("list_children", 0) == 0


def test_two_targets_have_independent_fetch_balls() -> None:
    sim = SimulationHarness()
    target_a = sim.add_target("target-a")
    target_b = sim.add_target("target-b")
    sim.reset_operation_counts()

    sim.toss_job(target_a, generation=1)
    sim.toss_job(target_b, generation=1)

    assert sim.state(target_a.fetch_ball_id) == "FETCH_BALL_TOSS"
    assert sim.state(target_b.fetch_ball_id) == "FETCH_BALL_TOSS"

    first = sim.run_job(
        target_a,
        execution_report(ExecutionDisposition.EXITED, exit_code=0),
    )
    assert first.terminal_state == "DONE"
    assert sim.state(target_b.fetch_ball_id) == "FETCH_BALL_TOSS"

    second = sim.run_job(
        target_b,
        execution_report(ExecutionDisposition.EXITED, exit_code=0),
    )
    assert second.terminal_state == "DONE"
    assert target_a.fetch_ball_id != target_b.fetch_ball_id
    assert sim.backend.operation_counts.get("list_children", 0) == 0


def test_partial_result_survives_integrated_pipeline() -> None:
    sim = SimulationHarness()
    target = sim.add_target("target-a")
    sim.reset_operation_counts()

    sim.toss_job(target)
    result = sim.run_job(
        target,
        execution_report(
            ExecutionDisposition.EXITED,
            exit_code=7,
            effects=("created output directory",),
        ),
    )

    assert result.terminal_state == "PARTIAL"
    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_PARTIAL"
    assert sim.backend.operation_counts.get("list_children", 0) == 0


def test_cancelled_execution_returns_cancelled_terminal() -> None:
    sim = SimulationHarness()
    target = sim.add_target("target-a")
    sim.reset_operation_counts()

    sim.toss_job(target)
    result = sim.run_job(
        target,
        execution_report(ExecutionDisposition.CANCELLED),
    )

    assert result.terminal_state == "CANCELLED"
    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_CANCELLED"
    assert sim.backend.operation_counts.get("list_children", 0) == 0


def test_target_loss_can_be_terminalized_as_gone_without_fabricating_result() -> None:
    sim = SimulationHarness()
    target = sim.add_target("target-a")
    sim.reset_operation_counts()

    sim.toss_job(target)
    sim.mark_job_gone(target)

    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_GONE"
    remote = sim.backend.read_text(target.fetch_ball_id)
    assert remote.ok and remote.value is not None
    assert '"result_code":"GONE"' in remote.value.text
    assert '"effects_known":"UNKNOWN"' in remote.value.text
    assert sim.backend.operation_counts.get("list_children", 0) == 0
