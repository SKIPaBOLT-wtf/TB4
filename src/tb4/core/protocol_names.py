from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    COACH = "COACH"
    WATCHDOG = "WATCHDOG"
    FETCHER = "FETCHER"
    RUNNER = "RUNNER"


class LogicalObject(StrEnum):
    START_HERE = "START_HERE"
    PARK_MAP = "PARK_MAP"
    DOG_TAG = "DOG_TAG"
    DOG_PULSE = "DOG_PULSE"
    DOG_SNIFF = "DOG_SNIFF"
    FETCH_BALL = "FETCH_BALL"
    WAKE_BONE = "WAKE_BONE"
    STOP_BALL = "STOP_BALL"
    WATCHDOG_MODE = "WATCHDOG_MODE"
    WATCHDOG_FAULT = "WATCHDOG_FAULT"
    TARGET_LEASH = "TARGET_LEASH"


class FetchResultCode(StrEnum):
    DONE = "DONE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    GONE = "GONE"


_SPECIAL_FILENAMES: dict[LogicalObject, dict[str, str]] = {
    LogicalObject.WATCHDOG_MODE: {
        "SNOOZE": "DOG_SNOOZE",
        "AWAKE": "DOG_AWAKE",
    },
    LogicalObject.TARGET_LEASH: {
        "CLEAR": "LEASH_CLEAR",
        "TANGLED": "LEASH_TANGLED",
    },
}


def state_filename(logical_object: LogicalObject, state: str) -> str:
    """Return a canonical active filename for one logical object state."""

    state = state.strip().upper()
    if not state:
        raise ValueError("state must not be empty")

    special = _SPECIAL_FILENAMES.get(logical_object)
    if special is not None:
        try:
            return special[state]
        except KeyError as exc:
            raise ValueError(
                f"unknown state {state!r} for {logical_object.value}"
            ) from exc

    if logical_object is LogicalObject.WATCHDOG_FAULT:
        return f"DOG_SHIT_{state}"

    if logical_object in {
        LogicalObject.FETCH_BALL,
        LogicalObject.WAKE_BONE,
        LogicalObject.STOP_BALL,
    }:
        return f"{logical_object.value}_{state}"

    raise ValueError(f"{logical_object.value} is not a stateful filename object")
