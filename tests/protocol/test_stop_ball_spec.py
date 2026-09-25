from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "protocol" / "state-machines.yaml"


def _machine() -> dict:
    with SPEC.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)["state_machines"]["STOP_BALL"]


def _edges() -> set[tuple[str, str, str]]:
    return {
        (edge["from"], edge["to"], edge["actor"])
        for edge in _machine()["transitions"]
    }


def test_stop_ball_has_safe_staging_states() -> None:
    assert set(_machine()["states"]) == {
        "READY",
        "LOADING",
        "REQUESTED",
        "RETURNING",
        "ACKNOWLEDGED",
        "RECYCLING",
    }


def test_request_is_published_only_after_loading() -> None:
    edges = _edges()
    assert ("READY", "LOADING", "COACH") in edges
    assert ("LOADING", "REQUESTED", "COACH") in edges
    assert _machine()["states"]["LOADING"]["body_writers"] == ["COACH"]
    assert _machine()["states"]["REQUESTED"]["body_writers"] == []


def test_ack_is_published_only_after_returning() -> None:
    edges = _edges()
    assert ("REQUESTED", "RETURNING", "FETCHER") in edges
    assert ("RETURNING", "ACKNOWLEDGED", "FETCHER") in edges
    assert _machine()["states"]["RETURNING"]["body_writers"] == ["FETCHER"]


def test_cancel_match_requires_exact_fence_fields() -> None:
    required = set(_machine()["match_rules"]["required"])
    assert required == {"fetch_ball_object_id", "job_id", "generation"}
    assert _machine()["match_rules"]["stale_or_mismatched_request"] == "do_not_cancel"


def test_execution_result_remains_on_fetch_ball() -> None:
    assert _machine()["match_rules"]["cancellation_result_lives_on"] == "FETCH_BALL"


def test_obsolete_unclaimed_request_can_recycle_without_racing_fetcher() -> None:
    edges = _edges()
    assert ("REQUESTED", "RECYCLING", "COACH") in edges
    assert ("REQUESTED", "RETURNING", "FETCHER") in edges
