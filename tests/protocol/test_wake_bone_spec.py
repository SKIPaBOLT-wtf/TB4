from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "protocol" / "state-machines.yaml"


def _machine() -> dict:
    with SPEC.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)["state_machines"]["WAKE_BONE"]


def _edges() -> set[tuple[str, str, str]]:
    return {
        (edge["from"], edge["to"], edge["actor"])
        for edge in _machine()["transitions"]
    }


def test_wake_bone_states_are_canonical() -> None:
    assert set(_machine()["states"]) == {
        "READY", "LOADING", "TOSS", "CHEW", "DONE", "FAILED", "RECYCLING"
    }


def test_watchdog_claims_toss_and_owns_chew() -> None:
    assert ("TOSS", "CHEW", "WATCHDOG") in _edges()
    assert _machine()["states"]["CHEW"]["body_writers"] == ["WATCHDOG"]


def test_expired_toss_has_non_action_terminal_path() -> None:
    assert ("TOSS", "FAILED", "WATCHDOG") in _edges()
    rules = _machine()["action_rules"]["before_wol_or_ssh"]
    assert "request_not_expired" in rules


def test_success_requires_fresh_fetcher_pulse() -> None:
    assert _machine()["action_rules"]["success_requires"] == [
        "fresh_target_dog_pulse"
    ]


def test_wake_failure_scope_is_target_local() -> None:
    assert _machine()["action_rules"]["failure_scope"] == "target_local"


def test_coach_recycles_both_terminal_states() -> None:
    edges = _edges()
    assert ("DONE", "RECYCLING", "COACH") in edges
    assert ("FAILED", "RECYCLING", "COACH") in edges
    assert ("RECYCLING", "READY", "COACH") in edges
