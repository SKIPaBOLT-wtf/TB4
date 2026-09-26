from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from tb4.core.retry import (
    ProbeDisposition,
    RetryPolicy,
    RetryStopReason,
    confirm_with_backoff,
)
from tb4.core.schemas import SchemaStore, canonical_json_text, load_schema_store
from tb4.drive.backend import DriveBackend
from tb4.drive.errors import BackendOutcome


class HeartbeatOutcome(StrEnum):
    PUBLISHED = "PUBLISHED"
    NOT_DUE = "NOT_DUE"
    CLOCK_ANOMALY = "CLOCK_ANOMALY"
    FAILURE = "FAILURE"
    UNCONFIRMED = "UNCONFIRMED"


@dataclass(frozen=True, slots=True)
class HeartbeatReport:
    outcome: HeartbeatOutcome
    sequence: int
    emitted_at: int | None = None
    message: str | None = None
    confirmation_probes: int = 0


@dataclass(slots=True)
class HeartbeatPublisher:
    backend: DriveBackend
    dog_pulse_object_id: str
    device_id: str
    instance_id: str
    idle_interval_s: float
    active_interval_s: float
    retry_policy: RetryPolicy
    monotonic_now: Callable[[], float]
    epoch_now: Callable[[], int]
    sleeper: Callable[[float], None]
    schema_store: SchemaStore | None = None
    sequence: int = 0
    last_attempt_monotonic_s: float | None = None
    last_emitted_epoch_s: int | None = None

    def __post_init__(self) -> None:
        if self.idle_interval_s <= 0 or self.active_interval_s <= 0:
            raise ValueError("heartbeat intervals must be positive")
        if self.active_interval_s > self.idle_interval_s:
            raise ValueError("active heartbeat interval must not exceed idle interval")
        if not self.dog_pulse_object_id:
            raise ValueError("dog_pulse_object_id is required")
        if not self.device_id:
            raise ValueError("device_id is required")
        if len(self.instance_id) < 8:
            raise ValueError("instance_id must be at least 8 characters")

    def tick(
        self,
        *,
        active: bool,
        claimed_generation: int | None = None,
        claimed_operation_id: str | None = None,
    ) -> HeartbeatReport:
        if (claimed_generation is None) != (claimed_operation_id is None):
            raise ValueError(
                "claimed_generation and claimed_operation_id must be set together"
            )

        monotonic = self.monotonic_now()
        interval = self.active_interval_s if active else self.idle_interval_s
        if (
            self.last_attempt_monotonic_s is not None
            and monotonic - self.last_attempt_monotonic_s < interval
        ):
            return HeartbeatReport(HeartbeatOutcome.NOT_DUE, self.sequence)

        # Record the attempt before any remote I/O. A failing provider therefore
        # cannot turn a tight caller loop into a cloud-write busy loop.
        self.last_attempt_monotonic_s = monotonic

        emitted_at = int(self.epoch_now())
        if emitted_at <= 0:
            return HeartbeatReport(
                HeartbeatOutcome.CLOCK_ANOMALY,
                self.sequence,
                emitted_at=emitted_at,
                message="epoch clock must be positive",
            )
        if (
            self.last_emitted_epoch_s is not None
            and emitted_at < self.last_emitted_epoch_s
        ):
            return HeartbeatReport(
                HeartbeatOutcome.CLOCK_ANOMALY,
                self.sequence,
                emitted_at=emitted_at,
                message="epoch clock moved backwards",
            )

        candidate_sequence = self.sequence + 1
        body = {
            "schema_version": 1,
            "protocol_major": 1,
            "device_id": self.device_id,
            "emitted_at": emitted_at,
            "sequence": candidate_sequence,
            "instance_id": self.instance_id,
            "claimed_generation": claimed_generation,
            "claimed_operation_id": claimed_operation_id,
        }

        store = self.schema_store if self.schema_store is not None else load_schema_store()
        store.validate("dog-pulse.schema.json", body)
        body_text = canonical_json_text(body)
        body_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()

        metadata = self.backend.get_metadata(self.dog_pulse_object_id)
        if not metadata.ok or metadata.value is None:
            return HeartbeatReport(
                HeartbeatOutcome.FAILURE,
                self.sequence,
                emitted_at=emitted_at,
                message=metadata.message or metadata.outcome.value,
            )
        if metadata.value.is_folder:
            return HeartbeatReport(
                HeartbeatOutcome.FAILURE,
                self.sequence,
                emitted_at=emitted_at,
                message="DOG_PULSE object is a folder",
            )

        write = self.backend.replace_text(
            self.dog_pulse_object_id,
            body_text,
            expected_version_token=metadata.value.version_token,
        )
        if write.outcome not in {BackendOutcome.SUCCESS, BackendOutcome.AMBIGUOUS}:
            return HeartbeatReport(
                HeartbeatOutcome.FAILURE,
                self.sequence,
                emitted_at=emitted_at,
                message=write.message or write.outcome.value,
            )

        read_failure: list[str] = []

        def probe() -> ProbeDisposition:
            remote = self.backend.read_text(self.dog_pulse_object_id)
            if not remote.ok or remote.value is None:
                if remote.outcome is BackendOutcome.TRANSIENT_ERROR:
                    return ProbeDisposition.NOT_VISIBLE
                read_failure[:] = [remote.message or remote.outcome.value]
                return ProbeDisposition.AMBIGUOUS
            try:
                parsed = json.loads(remote.value.text)
                store.validate("dog-pulse.schema.json", parsed)
            except Exception:
                return ProbeDisposition.NOT_VISIBLE
            remote_hash = hashlib.sha256(
                remote.value.text.encode("utf-8")
            ).hexdigest()
            if remote_hash != body_hash:
                return ProbeDisposition.NOT_VISIBLE
            return ProbeDisposition.CONFIRMED

        confirmation = confirm_with_backoff(
            probe,
            policy=self.retry_policy,
            monotonic_now=self.monotonic_now,
            sleeper=self.sleeper,
        )
        if confirmation.reason is not RetryStopReason.CONFIRMED:
            return HeartbeatReport(
                HeartbeatOutcome.UNCONFIRMED,
                self.sequence,
                emitted_at=emitted_at,
                message=(
                    read_failure[-1]
                    if read_failure
                    else f"heartbeat readback not confirmed: {confirmation.reason.value}"
                ),
                confirmation_probes=confirmation.probe_count,
            )

        self.sequence = candidate_sequence
        self.last_emitted_epoch_s = emitted_at
        return HeartbeatReport(
            HeartbeatOutcome.PUBLISHED,
            self.sequence,
            emitted_at=emitted_at,
            confirmation_probes=confirmation.probe_count,
        )
