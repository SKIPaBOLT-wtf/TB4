from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tb4.core.protocol_names import LogicalObject, Role
from tb4.core.state_machine import (
    TransitionDisposition,
    is_terminal,
    load_state_machines,
    validate_transition,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "protocol" / "state-machines.yaml"


def _spec() -> dict:
    return yaml.safe_load(SPEC.read_text(encoding="utf-8"))["state_machines"]


def test_loader_is_cached_for_same_canonical_path() -> None:
    load_state_machines.cache_clear()
    first = load_state_machines(SPEC)
    second = load_state_machines(SPEC)
    assert first is second


def test_every_canonical_transition_edge_is_legal_for_its_actor() -> None:
    for object_name, machine in _spec().items():
        for edge in machine["transitions"]:
            decision = validate_transition(
                object_name,
                edge["from"],
                edge["to"],
                edge["actor"],
            )
            assert decision.disposition is TransitionDisposition.LEGAL, (
                object_name,
                edge,
                decision,
            )


def test_every_canonical_transition_rejects_wrong_known_actor() -> None:
    roles = {role.value for role in Role}
    for object_name, machine in _spec().items():
        for edge in machine["transitions"]:
            wrong_actor = next(actor for actor in roles if actor != edge["actor"])
            decision = validate_transition(
                object_name,
                edge["from"],
                edge["to"],
                wrong_actor,
            )
            assert decision.disposition is TransitionDisposition.ILLEGAL


def test_every_known_same_state_request_is_idempotent() -> None:
    for object_name, machine in _spec().items():
        for state in machine["states"]:
            decision = validate_transition(object_name, state, state, Role.COACH)
            assert decision.disposition is TransitionDisposition.IDEMPOTENT
            assert decision.allowed


def test_non_edges_are_illegal() -> None:
    for object_name, machine in _spec().items():
        edges = {
            (edge["from"], edge["to"])
            for edge in machine["transitions"]
        }
        states = list(machine["states"])
        for current in states:
            for target in states:
                if current == target or (current, target) in edges:
                    continue
                decision = validate_transition(
                    object_name, current, target, Role.COACH
                )
                assert decision.disposition is TransitionDisposition.ILLEGAL


def test_cross_object_state_is_rejected() -> None:
    decision = validate_transition(
        LogicalObject.WAKE_BONE,
        "READY",
        "PARTIAL",
        Role.WATCHDOG,
    )
    assert decision.disposition is TransitionDisposition.ILLEGAL
    assert "unknown target state" in decision.reason


def test_unknown_actor_is_rejected() -> None:
    decision = validate_transition(
        LogicalObject.FETCH_BALL,
        "READY",
        "LOADING",
        "MYSTERY_DOG",
    )
    assert decision.disposition is TransitionDisposition.ILLEGAL
    assert "unknown actor" in decision.reason


def test_fixed_object_has_no_transition_machine() -> None:
    decision = validate_transition(
        LogicalObject.DOG_TAG,
        "READY",
        "LOADING",
        Role.COACH,
    )
    assert decision.disposition is TransitionDisposition.ILLEGAL
    assert "non-stateful" in decision.reason


def test_terminal_queries_match_canonical_spec_exactly() -> None:
    for object_name, machine in _spec().items():
        for state, definition in machine["states"].items():
            assert is_terminal(object_name, state) is bool(definition["terminal"])


def test_terminal_query_rejects_unknown_state_and_fixed_object() -> None:
    with pytest.raises(ValueError):
        is_terminal(LogicalObject.FETCH_BALL, "LOST_SOCK")
    with pytest.raises(ValueError):
        is_terminal(LogicalObject.DOG_TAG, "READY")
