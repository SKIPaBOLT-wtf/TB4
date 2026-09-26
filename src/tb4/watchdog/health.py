from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from tb4.core.protocol_names import LogicalObject, Role
from tb4.drive.backend import DriveBackend
from tb4.drive.body_keeper import BodyKeeper, BodyWriteOutcome
from tb4.drive.errors import BackendOutcome
from tb4.drive.state_walker import StateWalkOutcome, StateWalker


class FaultScope(StrEnum):
    TARGET_LOCAL = "TARGET_LOCAL"
    TRANSPORT_RECOVERABLE = "TRANSPORT_RECOVERABLE"
    PROTOCOL_BLOCKING = "PROTOCOL_BLOCKING"
    GLOBAL_BLOCKING = "GLOBAL_BLOCKING"

    @property
    def blocks_watchdog(self) -> bool:
        return self in {
            FaultScope.PROTOCOL_BLOCKING,
            FaultScope.GLOBAL_BLOCKING,
        }


class WorkKind(StrEnum):
    NORMAL_CONTROL = "NORMAL_CONTROL"
    DIAGNOSTIC_READ = "DIAGNOSTIC_READ"
    REPAIR = "REPAIR"


class HealthOutcome(StrEnum):
    NONBLOCKING = "NONBLOCKING"
    BLOCKING_SET = "BLOCKING_SET"
    BLOCKING_REFRESHED = "BLOCKING_REFRESHED"
    STILL_BLOCKING = "STILL_BLOCKING"
    CLEANED = "CLEANED"
    STATE_CONFLICT = "STATE_CONFLICT"
    UNCONFIRMED = "UNCONFIRMED"
    FAILURE = "FAILURE"


@dataclass(frozen=True, slots=True)
class FaultSignal:
    code: str
    description: str
    scope: FaultScope
    invariant_key: str

    def __post_init__(self) -> None:
        if not self.code or self.code.upper() != self.code:
            raise ValueError("fault code must be non-empty uppercase text")
        if not self.description:
            raise ValueError("fault description is required")
        if not self.invariant_key:
            raise ValueError("invariant_key is required")


@dataclass(frozen=True, slots=True)
class HealthReport:
    outcome: HealthOutcome
    scope: FaultScope | None = None
    fault_code: str | None = None
    message: str | None = None

    @property
    def success(self) -> bool:
        return self.outcome in {
            HealthOutcome.NONBLOCKING,
            HealthOutcome.BLOCKING_SET,
            HealthOutcome.BLOCKING_REFRESHED,
            HealthOutcome.STILL_BLOCKING,
            HealthOutcome.CLEANED,
        }


_FAULT_SCOPE_BY_CODE: dict[str, FaultScope] = {
    # Ordinary target/job faults must never become global DOG_SHIT.
    "WOL_FAILED": FaultScope.TARGET_LOCAL,
    "SSH_BOOTSTRAP_FAILED": FaultScope.TARGET_LOCAL,
    "TARGET_OFFLINE": FaultScope.TARGET_LOCAL,
    "FETCH_BALL_FAILED": FaultScope.TARGET_LOCAL,
    "FETCH_BALL_PARTIAL": FaultScope.TARGET_LOCAL,
    "FETCH_BALL_GONE": FaultScope.TARGET_LOCAL,
    "WAKE_BONE_FAILED": FaultScope.TARGET_LOCAL,

    # Bounded transport trouble remains recoverable until its own transaction
    # policy is exhausted and a stronger invariant failure is reported.
    "DRIVE_TRANSIENT": FaultScope.TRANSPORT_RECOVERABLE,
    "DRIVE_RATE_LIMITED": FaultScope.TRANSPORT_RECOVERABLE,
    "DRIVE_AMBIGUOUS_PENDING_RECONCILIATION": FaultScope.TRANSPORT_RECOVERABLE,

    # Canonical protocol ambiguity blocks normal work but still permits repair.
    "PARK_MAP_AMBIGUOUS": FaultScope.PROTOCOL_BLOCKING,
    "CANONICAL_TREE_AMBIGUOUS": FaultScope.PROTOCOL_BLOCKING,
    "STATE_MUTATION_UNCONFIRMED": FaultScope.PROTOCOL_BLOCKING,

    # These make WATCHDOG unable to trust the global control plane.
    "DRIVE_ROOT_UNREACHABLE": FaultScope.GLOBAL_BLOCKING,
    "DRIVE_AUTH_UNAVAILABLE": FaultScope.GLOBAL_BLOCKING,
    "CLOCK_UNSAFE_FOR_TTL": FaultScope.GLOBAL_BLOCKING,
}


def classify_fault_code(code: str) -> FaultScope:
    """Classify only canonical fault codes.

    Unknown codes are rejected instead of being guessed into a severity. This
    prevents an ordinary new target error from accidentally becoming DOG_SHIT,
    and prevents a new control-plane invariant failure from being under-scoped.
    """

    normalized = code.strip().upper()
    try:
        return _FAULT_SCOPE_BY_CODE[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown WATCHDOG fault code {normalized!r}") from exc


@dataclass(slots=True)
class WatchdogHealth:
    backend: DriveBackend
    state_walker: StateWalker
    body_keeper: BodyKeeper
    dog_shit_object_id: str
    epoch_now: Callable[[], int]

    def can_accept(self, work_kind: WorkKind) -> bool:
        """Fail closed when DOG_SHIT state cannot be read reliably."""

        metadata = self.backend.get_metadata(self.dog_shit_object_id)
        if not metadata.ok or metadata.value is None:
            return False

        name = metadata.value.name
        if name == "DOG_SHIT_CLEAN":
            return True
        if name in {"DOG_SHIT_BLOCKING", "DOG_SHIT_REVIEWED"}:
            return work_kind in {WorkKind.DIAGNOSTIC_READ, WorkKind.REPAIR}
        return False

    def report(self, signal: FaultSignal) -> HealthReport:
        """Publish a blocking fault only when its scope warrants DOG_SHIT."""

        if not signal.scope.blocks_watchdog:
            return HealthReport(
                HealthOutcome.NONBLOCKING,
                scope=signal.scope,
                fault_code=signal.code,
                message="fault is scoped below WATCHDOG global blocking",
            )

        metadata = self.backend.get_metadata(self.dog_shit_object_id)
        if not metadata.ok or metadata.value is None:
            return self._backend_failure(
                metadata.outcome,
                signal,
                metadata.message or "cannot read DOG_SHIT metadata",
            )

        current_name = metadata.value.name
        prior = (
            self._read_fault_body()
            if current_name in {"DOG_SHIT_BLOCKING", "DOG_SHIT_REVIEWED"}
            else None
        )

        if current_name == "DOG_SHIT_CLEAN":
            walked = self.state_walker.walk(
                object_id=self.dog_shit_object_id,
                logical_object=LogicalObject.WATCHDOG_FAULT,
                expected_state="CLEAN",
                target_state="BLOCKING",
                actor=Role.WATCHDOG,
            )
            if not walked.success:
                return self._walk_failure(walked.outcome, signal, walked.message)
            refreshed = False
        elif current_name == "DOG_SHIT_BLOCKING":
            refreshed = True
        elif current_name == "DOG_SHIT_REVIEWED":
            walked = self.state_walker.walk(
                object_id=self.dog_shit_object_id,
                logical_object=LogicalObject.WATCHDOG_FAULT,
                expected_state="REVIEWED",
                target_state="BLOCKING",
                actor=Role.WATCHDOG,
            )
            if not walked.success:
                return self._walk_failure(walked.outcome, signal, walked.message)
            refreshed = True
        else:
            return HealthReport(
                HealthOutcome.STATE_CONFLICT,
                scope=signal.scope,
                fault_code=signal.code,
                message=f"unexpected DOG_SHIT filename {current_name!r}",
            )

        body = self._blocking_body(signal, prior=prior)
        write = self.body_keeper.replace_verified(
            object_id=self.dog_shit_object_id,
            logical_object=LogicalObject.WATCHDOG_FAULT,
            state="BLOCKING",
            actor=Role.WATCHDOG,
            schema_name="watchdog-fault.schema.json",
            body=body,
        )
        if not write.success:
            return self._body_failure(write.outcome, signal, write.message)

        return HealthReport(
            HealthOutcome.BLOCKING_REFRESHED if refreshed else HealthOutcome.BLOCKING_SET,
            scope=signal.scope,
            fault_code=signal.code,
            message="current WATCHDOG blocking fault stored and verified",
        )

    def revalidate_reviewed(
        self,
        invariant_ok: Callable[[], bool],
    ) -> HealthReport:
        """Resolve REVIEWED only after the underlying invariant is checked again."""

        metadata = self.backend.get_metadata(self.dog_shit_object_id)
        if not metadata.ok or metadata.value is None:
            return HealthReport(
                HealthOutcome.UNCONFIRMED
                if metadata.outcome is BackendOutcome.AMBIGUOUS
                else HealthOutcome.FAILURE,
                message=metadata.message or "cannot read DOG_SHIT metadata",
            )

        if metadata.value.name != "DOG_SHIT_REVIEWED":
            return HealthReport(
                HealthOutcome.STATE_CONFLICT,
                message=f"expected DOG_SHIT_REVIEWED, observed {metadata.value.name!r}",
            )

        current = self._read_fault_body()
        if current is None:
            return HealthReport(
                HealthOutcome.FAILURE,
                message="DOG_SHIT body is unreadable or invalid JSON",
            )

        if not invariant_ok():
            signal = FaultSignal(
                code=str(current["fault_code"]),
                description=str(current["description"]),
                scope=FaultScope(str(current["scope"])),
                invariant_key=str(current["invariant_key"]),
            )
            walked = self.state_walker.walk(
                object_id=self.dog_shit_object_id,
                logical_object=LogicalObject.WATCHDOG_FAULT,
                expected_state="REVIEWED",
                target_state="BLOCKING",
                actor=Role.WATCHDOG,
            )
            if not walked.success:
                return self._walk_failure(walked.outcome, signal, walked.message)

            write = self.body_keeper.replace_verified(
                object_id=self.dog_shit_object_id,
                logical_object=LogicalObject.WATCHDOG_FAULT,
                state="BLOCKING",
                actor=Role.WATCHDOG,
                schema_name="watchdog-fault.schema.json",
                body=self._blocking_body(signal, prior=current),
            )
            if not write.success:
                return self._body_failure(write.outcome, signal, write.message)

            return HealthReport(
                HealthOutcome.STILL_BLOCKING,
                scope=signal.scope,
                fault_code=signal.code,
                message="reviewed fault remains blocking because invariant still fails",
            )

        walked = self.state_walker.walk(
            object_id=self.dog_shit_object_id,
            logical_object=LogicalObject.WATCHDOG_FAULT,
            expected_state="REVIEWED",
            target_state="CLEAN",
            actor=Role.WATCHDOG,
        )
        if not walked.success:
            return self._walk_failure(walked.outcome, None, walked.message)

        now = int(self.epoch_now())
        clean_body = {
            "schema_version": 1,
            "protocol_major": 1,
            "reported_at": now,
            "source": "WATCHDOG",
            "scope": "NONE",
            "fault_code": None,
            "description": None,
            "invariant_key": None,
            "first_seen_at": 0,
            "last_seen_at": 0,
            "occurrence_count": 0,
        }
        write = self.body_keeper.replace_verified(
            object_id=self.dog_shit_object_id,
            logical_object=LogicalObject.WATCHDOG_FAULT,
            state="CLEAN",
            actor=Role.WATCHDOG,
            schema_name="watchdog-fault.schema.json",
            body=clean_body,
        )
        if not write.success:
            return self._body_failure(write.outcome, None, write.message)

        return HealthReport(
            HealthOutcome.CLEANED,
            message="review acknowledged and underlying invariant revalidated",
        )

    def _blocking_body(
        self,
        signal: FaultSignal,
        *,
        prior: dict[str, object] | None = None,
    ) -> dict[str, object]:
        now = int(self.epoch_now())
        same_fault = (
            prior is not None
            and prior.get("fault_code") == signal.code
            and prior.get("invariant_key") == signal.invariant_key
        )
        first_seen = (
            int(prior["first_seen_at"])
            if same_fault and isinstance(prior.get("first_seen_at"), int)
            else now
        )
        count = (
            int(prior["occurrence_count"]) + 1
            if same_fault and isinstance(prior.get("occurrence_count"), int)
            else 1
        )
        return {
            "schema_version": 1,
            "protocol_major": 1,
            "reported_at": now,
            "source": "WATCHDOG",
            "scope": signal.scope.value,
            "fault_code": signal.code,
            "description": signal.description[:512],
            "invariant_key": signal.invariant_key,
            "first_seen_at": first_seen,
            "last_seen_at": now,
            "occurrence_count": count,
        }

    def _read_fault_body(self) -> dict[str, object] | None:
        result = self.backend.read_text(self.dog_shit_object_id)
        if not result.ok or result.value is None:
            return None
        try:
            body = json.loads(result.value.text)
        except json.JSONDecodeError:
            return None
        return body if isinstance(body, dict) else None

    @staticmethod
    def _walk_failure(
        outcome: StateWalkOutcome,
        signal: FaultSignal | None,
        message: str | None,
    ) -> HealthReport:
        mapped = (
            HealthOutcome.UNCONFIRMED
            if outcome is StateWalkOutcome.UNCONFIRMED
            else HealthOutcome.STATE_CONFLICT
            if outcome in {
                StateWalkOutcome.STATE_CONFLICT,
                StateWalkOutcome.STALE_FENCE,
            }
            else HealthOutcome.FAILURE
        )
        return HealthReport(
            mapped,
            scope=None if signal is None else signal.scope,
            fault_code=None if signal is None else signal.code,
            message=message,
        )

    @staticmethod
    def _body_failure(
        outcome: BodyWriteOutcome,
        signal: FaultSignal | None,
        message: str | None,
    ) -> HealthReport:
        mapped = (
            HealthOutcome.UNCONFIRMED
            if outcome is BodyWriteOutcome.UNCONFIRMED
            else HealthOutcome.STATE_CONFLICT
            if outcome in {
                BodyWriteOutcome.STATE_CONFLICT,
                BodyWriteOutcome.STALE_FENCE,
            }
            else HealthOutcome.FAILURE
        )
        return HealthReport(
            mapped,
            scope=None if signal is None else signal.scope,
            fault_code=None if signal is None else signal.code,
            message=message,
        )

    @staticmethod
    def _backend_failure(
        outcome: BackendOutcome,
        signal: FaultSignal,
        message: str,
    ) -> HealthReport:
        return HealthReport(
            HealthOutcome.UNCONFIRMED
            if outcome is BackendOutcome.AMBIGUOUS
            else HealthOutcome.FAILURE,
            scope=signal.scope,
            fault_code=signal.code,
            message=message,
        )
