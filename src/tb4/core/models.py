from __future__ import annotations

import re
from dataclasses import dataclass

from .protocol_names import LogicalObject, state_filename


_ID_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
_DEVICE_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_REASON_RE = re.compile(r"^[A-Z0-9_]+$")


def _bounded_text(value: str, *, name: str, minimum: int, maximum: int, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not minimum <= len(value) <= maximum:
        raise ValueError(f"{name} length must be between {minimum} and {maximum}")
    if pattern.fullmatch(value) is None:
        raise ValueError(f"{name} has invalid characters")
    return value


@dataclass(frozen=True, slots=True)
class OperationId:
    value: str

    def __post_init__(self) -> None:
        _bounded_text(self.value, name="operation_id", minimum=8, maximum=128, pattern=_ID_RE)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class DeviceId:
    value: str

    def __post_init__(self) -> None:
        _bounded_text(self.value, name="device_id", minimum=1, maximum=128, pattern=_DEVICE_RE)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ArtifactId:
    value: str

    def __post_init__(self) -> None:
        _bounded_text(self.value, name="artifact_id", minimum=1, maximum=256, pattern=_ID_RE)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True, order=True)
class Generation:
    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("generation must be an integer")
        if self.value < 0:
            raise ValueError("generation must be non-negative")

    def next(self) -> "Generation":
        return Generation(self.value + 1)

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True, slots=True, order=True)
class EpochSeconds:
    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("epoch seconds must be an integer")
        if self.value < 0:
            raise ValueError("epoch seconds must be non-negative")

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True, slots=True)
class ReasonCode:
    value: str

    def __post_init__(self) -> None:
        _bounded_text(self.value, name="reason_code", minimum=1, maximum=64, pattern=_REASON_RE)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ObjectStateRef:
    logical_object: LogicalObject
    state: str

    def __post_init__(self) -> None:
        normalized = self.state.strip().upper()
        if not normalized or _REASON_RE.fullmatch(normalized) is None:
            raise ValueError("state must be a non-empty UPPER_SNAKE_CASE token")
        object.__setattr__(self, "state", normalized)

    @property
    def filename(self) -> str:
        return state_filename(self.logical_object, self.state)

    def to_dict(self) -> dict[str, str]:
        return {
            "logical_object": self.logical_object.value,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "ObjectStateRef":
        return cls(
            logical_object=LogicalObject(data["logical_object"]),
            state=data["state"],
        )
