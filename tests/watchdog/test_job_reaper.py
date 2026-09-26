from __future__ import annotations

import json

from tb4.core.protocol_names import LogicalObject, Role
from tb4.testing.simulation import SimulationHarness
from tb4.watchdog.job_reaper import JobReaper, JobReaperOutcome


def _chewing_sim() -> tuple[SimulationHarness, object]:
    sim = SimulationHarness()
    target = sim.add_target("target-a", online=True)
    sim.toss_job(target)
    sim._walk(
        target.fetch_ball_id,
        LogicalObject.FETCH_BALL,
        "TOSS",
        "CHEW",
        Role.FETCHER,
    )
    remote = sim.backend.read_text(target.fetch_ball_id)
    assert remote.ok and remote.value is not None
    body = json.loads(remote.value.text)
    body["started_at"] = sim.clock.epoch()
    write = sim.keeper.replace_verified(
        object_id=target.fetch_ball_id,
        logical_object=LogicalObject.FETCH_BALL,
        state="CHEW",
        actor=Role.FETCHER,
        schema_name="fetch-ball.schema.json",
        body=body,
    )
    assert write.success
    return sim, target


def _reaper(sim: SimulationHarness, target, *, stale=35, grace=30) -> JobReaper:
    return JobReaper(
        backend=sim.backend,
        state_walker=sim.walker,
        body_keeper=sim.keeper,
        fetch_ball_object_id=target.fetch_ball_id,
        dog_pulse_object_id=target.dog_pulse_id,
        target_device_id=target.device_id,
        stale_after_s=stale,
        gone_grace_s=grace,
        clock_skew_tolerance_s=10,
        epoch_now=sim.clock.epoch,
    )


def test_reaper_does_nothing_when_fetch_ball_is_not_chewing() -> None:
    sim = SimulationHarness()
    target = sim.add_target("target-a")
    report = _reaper(sim, target).check_once()
    assert report.outcome is JobReaperOutcome.NOT_CHEWING
    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_READY"


def test_fresh_pulse_keeps_chewing_job_owned_by_fetcher() -> None:
    sim, target = _chewing_sim()
    sim.publish_pulse(target)

    report = _reaper(sim, target).check_once()

    assert report.outcome is JobReaperOutcome.PULSE_FRESH
    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_CHEW"


def test_stale_pulse_waits_for_gone_grace() -> None:
    sim, target = _chewing_sim()
    sim.publish_pulse(target)
    sim.clock.epoch_value += 40

    report = _reaper(sim, target, stale=35, grace=30).check_once()

    assert report.outcome is JobReaperOutcome.GRACE_ACTIVE
    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_CHEW"


def test_stale_beyond_grace_terminalizes_as_unknown_effect_gone() -> None:
    sim, target = _chewing_sim()
    sim.publish_pulse(target)
    sim.clock.epoch_value += 70

    report = _reaper(sim, target, stale=35, grace=30).check_once()

    assert report.outcome is JobReaperOutcome.GONE
    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_GONE"

    remote = sim.backend.read_text(target.fetch_ball_id)
    assert remote.ok and remote.value is not None
    body = json.loads(remote.value.text)
    assert body["result_code"] == "GONE"
    assert body["reason_code"] == "FETCHER_LOST"
    assert body["effects_known"] == "UNKNOWN"
    assert body["exit_code"] is None
    assert body["result_sha256"] is not None


def test_reaper_is_idempotent_after_gone() -> None:
    sim, target = _chewing_sim()
    sim.publish_pulse(target)
    sim.clock.epoch_value += 70
    reaper = _reaper(sim, target)

    first = reaper.check_once()
    second = reaper.check_once()

    assert first.outcome is JobReaperOutcome.GONE
    assert second.outcome is JobReaperOutcome.NOT_CHEWING
    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_GONE"
