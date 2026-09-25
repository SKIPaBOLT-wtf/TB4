from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Any

from .models import Generation, ObjectStateRef, OperationId
from .protocol_names import LogicalObject


class FenceDisposition(StrEnum):
    VALID = "VALID"
    STALE = "STALE"
    MISMATCH = "MISMATCH"


@dataclass(frozen=True, slots=True)
class FenceToken:
    object_id: str
    operation_id: OperationId
    generation: Generation
    expected_state: ObjectStateRef

    def __post_init__(self) -> None:
        if not isinstance(self.object_id, str):
            raise TypeError("object_id must be a string")
        if not 1 <= len(self.object_id) <= 256:
            raise ValueError("object_id length must be between 1 and 256")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "FenceToken":
        required = {"object_id", "operation_id", "generation", "logical_object", "expected_state"}
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(f"missing fence component(s): {', '.join(missing)}")
        return cls(
            object_id=str(data["object_id"]),
            operation_id=OperationId(str(data["operation_id"])),
            generation=Generation(data["generation"]),
            expected_state=ObjectStateRef(
                LogicalObject(str(data["logical_object"])),
                str(data["expected_state"]),
            ),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "object_id": self.object_id,
            "operation_id": self.operation_id.value,
            "generation": self.generation.value,
            "logical_object": self.expected_state.logical_object.value,
            "expected_state": self.expected_state.state,
        }


@dataclass(frozen=True, slots=True)
class FenceDecision:
    disposition: FenceDisposition
    reason: str

    @property
    def allowed(self) -> bool:
        return self.disposition is FenceDisposition.VALID


class FenceViolation(RuntimeError):
    def __init__(self, decision: FenceDecision) -> None:
        super().__init__(decision.reason)
        self.decision = decision


def compare_fence(expected: FenceToken, observed: FenceToken) -> FenceDecision:
    if expected.object_id != observed.object_id:
        return FenceDecision(FenceDisposition.MISMATCH, "stable object ID mismatch")

    if observed.generation.value > expected.generation.value:
        return FenceDecision(
            FenceDisposition.STALE,
            "observed channel generation is newer than worker generation",
        )

    if observed.generation.value < expected.generation.value:
        return FenceDecision(
            FenceDisposition.MISMATCH,
            "observed channel generation is older than expected ownership token",
        )

    if expected.operation_id != observed.operation_id:
        return FenceDecision(FenceDisposition.MISMATCH, "operation ID mismatch")

    if expected.expected_state != observed.expected_state:
        return FenceDecision(FenceDisposition.MISMATCH, "expected state mismatch")

    return FenceDecision(FenceDisposition.VALID, "fence matches current ownership")


def assert_fence(expected: FenceToken, observed: FenceToken) -> None:
    decision = compare_fence(expected, observed)
    if not decision.allowed:
        raise FenceViolation(decision)


def validate_generation_advance(current: Generation, candidate: Generation) -> bool:
    """A reused channel must move strictly forward; equality is not a new generation."""

    return candidate.value > current.value
