from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

from .protocol_names import LogicalObject, Role


class TransitionDisposition(StrEnum):
    LEGAL = "LEGAL"
    IDEMPOTENT = "IDEMPOTENT"
    ILLEGAL = "ILLEGAL"


@dataclass(frozen=True, slots=True)
class TransitionDecision:
    disposition: TransitionDisposition
    logical_object: str
    current: str
    target: str
    actor: str
    reason: str

    @property
    def allowed(self) -> bool:
        return self.disposition is not TransitionDisposition.ILLEGAL


@dataclass(frozen=True, slots=True)
class Machine:
    states: frozenset[str]
    terminal_states: frozenset[str]
    body_writers: Mapping[str, frozenset[str]]
    edges: Mapping[tuple[str, str], frozenset[str]]


class StateMachineRegistry:
    def __init__(self, machines: Mapping[str, Machine]) -> None:
        self._machines = MappingProxyType(dict(machines))

    @classmethod
    def from_yaml(cls, path: Path) -> "StateMachineRegistry":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        machines: dict[str, Machine] = {}

        for object_name, definition in data["state_machines"].items():
            state_defs = definition["states"]
            edge_actors: dict[tuple[str, str], set[str]] = {}
            for edge in definition["transitions"]:
                key = (edge["from"], edge["to"])
                edge_actors.setdefault(key, set()).add(edge["actor"])

            machines[object_name] = Machine(
                states=frozenset(state_defs),
                terminal_states=frozenset(
                    state
                    for state, state_def in state_defs.items()
                    if state_def.get("terminal", False)
                ),
                body_writers=MappingProxyType(
                    {
                        state: frozenset(state_def.get("body_writers", []))
                        for state, state_def in state_defs.items()
                    }
                ),
                edges=MappingProxyType(
                    {key: frozenset(actors) for key, actors in edge_actors.items()}
                ),
            )
        return cls(machines)

    def machine(self, logical_object: LogicalObject | str) -> Machine | None:
        name = (
            logical_object.value
            if isinstance(logical_object, LogicalObject)
            else str(logical_object)
        )
        return self._machines.get(name)

    def validate_transition(
        self,
        logical_object: LogicalObject | str,
        current: str,
        target: str,
        actor: Role | str,
    ) -> TransitionDecision:
        object_name = (
            logical_object.value
            if isinstance(logical_object, LogicalObject)
            else str(logical_object)
        )
        actor_name = actor.value if isinstance(actor, Role) else str(actor)
        current = str(current).upper()
        target = str(target).upper()

        machine = self._machines.get(object_name)
        if machine is None:
            return TransitionDecision(
                TransitionDisposition.ILLEGAL,
                object_name,
                current,
                target,
                actor_name,
                "unknown or non-stateful logical object",
            )

        if current not in machine.states:
            return TransitionDecision(
                TransitionDisposition.ILLEGAL,
                object_name,
                current,
                target,
                actor_name,
                f"unknown current state {current!r}",
            )

        if target not in machine.states:
            return TransitionDecision(
                TransitionDisposition.ILLEGAL,
                object_name,
                current,
                target,
                actor_name,
                f"unknown target state {target!r}",
            )

        if actor_name not in {item.value for item in Role}:
            return TransitionDecision(
                TransitionDisposition.ILLEGAL,
                object_name,
                current,
                target,
                actor_name,
                f"unknown actor {actor_name!r}",
            )

        if current == target:
            return TransitionDecision(
                TransitionDisposition.IDEMPOTENT,
                object_name,
                current,
                target,
                actor_name,
                "object is already in the requested target state",
            )

        actors = machine.edges.get((current, target))
        if actors is None:
            return TransitionDecision(
                TransitionDisposition.ILLEGAL,
                object_name,
                current,
                target,
                actor_name,
                "transition edge is not canonical",
            )

        if actor_name not in actors:
            return TransitionDecision(
                TransitionDisposition.ILLEGAL,
                object_name,
                current,
                target,
                actor_name,
                f"actor does not own transition; allowed actors: {sorted(actors)}",
            )

        return TransitionDecision(
            TransitionDisposition.LEGAL,
            object_name,
            current,
            target,
            actor_name,
            "canonical transition",
        )

    def can_write_body(
        self,
        logical_object: LogicalObject | str,
        state: str,
        actor: Role | str,
    ) -> bool:
        machine = self.machine(logical_object)
        if machine is None:
            return False
        state_name = str(state).upper()
        actor_name = actor.value if isinstance(actor, Role) else str(actor)
        writers = machine.body_writers.get(state_name)
        if writers is None:
            return False
        return actor_name in writers

    def is_terminal(self, logical_object: LogicalObject | str, state: str) -> bool:
        machine = self.machine(logical_object)
        if machine is None:
            raise ValueError(f"unknown or non-stateful logical object {logical_object!s}")
        normalized = str(state).upper()
        if normalized not in machine.states:
            raise ValueError(f"unknown state {normalized!r}")
        return normalized in machine.terminal_states


def canonical_state_machine_path() -> Path:
    return Path(__file__).resolve().parents[3] / "protocol" / "state-machines.yaml"


@lru_cache(maxsize=8)
def load_state_machines(path: str | Path | None = None) -> StateMachineRegistry:
    resolved = canonical_state_machine_path() if path is None else Path(path).resolve()
    return StateMachineRegistry.from_yaml(resolved)


def validate_transition(
    object_root: LogicalObject | str,
    current: str,
    target: str,
    actor: Role | str,
    *,
    registry: StateMachineRegistry | None = None,
) -> TransitionDecision:
    active_registry = registry if registry is not None else load_state_machines()
    return active_registry.validate_transition(object_root, current, target, actor)


def is_terminal(
    object_root: LogicalObject | str,
    state: str,
    *,
    registry: StateMachineRegistry | None = None,
) -> bool:
    active_registry = registry if registry is not None else load_state_machines()
    return active_registry.is_terminal(object_root, state)
