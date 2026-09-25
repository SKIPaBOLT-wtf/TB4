from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "protocol" / "state-machines.yaml"


def _machine() -> dict:
    with SPEC.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data["state_machines"]["FETCH_BALL"]


def _edges(machine: dict) -> set[tuple[str, str, str]]:
    return {
        (item["from"], item["to"], item["actor"])
        for item in machine["transitions"]
    }


def test_fetch_ball_has_expected_canonical_states() -> None:
    states = set(_machine()["states"])
    assert states == {
        "READY",
        "LOADING",
        "TOSS",
        "CHEW",
        "RETURNING",
        "DONE",
        "PARTIAL",
        "FAILED",
        "CANCELLED",
        "GONE",
        "RECYCLING",
    }


def test_happy_path_edges_are_explicit() -> None:
    edges = _edges(_machine())
    expected = {
        ("READY", "LOADING", "COACH"),
        ("LOADING", "TOSS", "COACH"),
        ("TOSS", "CHEW", "FETCHER"),
        ("CHEW", "RETURNING", "FETCHER"),
        ("RETURNING", "DONE", "FETCHER"),
        ("DONE", "RECYCLING", "COACH"),
        ("RECYCLING", "READY", "COACH"),
    }
    assert expected <= edges


def test_terminal_states_are_exact() -> None:
    machine = _machine()
    terminal = {
        state
        for state, definition in machine["states"].items()
        if definition["terminal"]
    }
    assert terminal == {"DONE", "PARTIAL", "FAILED", "CANCELLED", "GONE"}


def test_body_writer_ownership_is_explicit() -> None:
    states = _machine()["states"]
    assert states["LOADING"]["body_writers"] == ["COACH"]
    assert states["CHEW"]["body_writers"] == ["FETCHER"]
    assert set(states["RETURNING"]["body_writers"]) == {"FETCHER", "WATCHDOG"}
    assert states["RECYCLING"]["body_writers"] == ["COACH"]


def test_all_transition_states_exist_and_actors_are_known() -> None:
    machine = _machine()
    states = set(machine["states"])
    actors = {"COACH", "WATCHDOG", "FETCHER", "RUNNER"}
    for transition in machine["transitions"]:
        assert transition["from"] in states
        assert transition["to"] in states
        assert transition["actor"] in actors
        assert transition["reason"]


def test_every_state_is_reachable_from_ready() -> None:
    machine = _machine()
    graph: dict[str, set[str]] = defaultdict(set)
    for transition in machine["transitions"]:
        graph[transition["from"]].add(transition["to"])

    seen = {"READY"}
    queue = deque(["READY"])
    while queue:
        current = queue.popleft()
        for target in graph[current]:
            if target not in seen:
                seen.add(target)
                queue.append(target)

    assert seen == set(machine["states"])


def test_all_terminal_states_have_recycling_exit() -> None:
    machine = _machine()
    edges = _edges(machine)
    for state, definition in machine["states"].items():
        if definition["terminal"]:
            assert (state, "RECYCLING", "COACH") in edges


def test_gone_and_partial_require_effect_review_before_replay() -> None:
    rules = _machine()["replay_rules"]
    assert rules["PARTIAL"] == "inspect_effects_before_any_retry"
    assert rules["GONE"] == "inspect_effects_before_any_retry"
