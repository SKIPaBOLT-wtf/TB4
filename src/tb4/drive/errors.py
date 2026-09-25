from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar


T = TypeVar("T")


class BackendOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TRANSIENT_ERROR = "TRANSIENT_ERROR"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class BackendResult(Generic[T]):
    outcome: BackendOutcome
    value: T | None = None
    message: str | None = None
    provider_code: str | None = None

    def __post_init__(self) -> None:
        if self.outcome is BackendOutcome.SUCCESS and self.value is None:
            raise ValueError("successful backend result requires a value")
        if self.outcome is not BackendOutcome.SUCCESS and self.value is not None:
            raise ValueError("failed/ambiguous backend result must not carry a value")

    @property
    def ok(self) -> bool:
        return self.outcome is BackendOutcome.SUCCESS

    @property
    def ambiguous(self) -> bool:
        return self.outcome is BackendOutcome.AMBIGUOUS

    @classmethod
    def success(cls, value: T) -> "BackendResult[T]":
        return cls(BackendOutcome.SUCCESS, value=value)

    @classmethod
    def failure(
        cls,
        outcome: BackendOutcome,
        *,
        message: str | None = None,
        provider_code: str | None = None,
    ) -> "BackendResult[T]":
        if outcome is BackendOutcome.SUCCESS:
            raise ValueError("use BackendResult.success for successful results")
        return cls(
            outcome,
            message=message,
            provider_code=provider_code,
        )
