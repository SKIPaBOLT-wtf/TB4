from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Callable, Protocol, runtime_checkable

from tb4.core.retry import ProbeDisposition, RetryPolicy, RetryStopReason, confirm_with_backoff
from tb4.core.schemas import SchemaStore, canonical_json_text, load_schema_store
from tb4.drive.backend import DriveBackend
from tb4.drive.errors import BackendOutcome


class Reachability(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class ProbeKind(StrEnum):
    ICMP = "ICMP"
    TCP = "TCP"
    ARP = "ARP"
    MULTI = "MULTI"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class ProbeObservation:
    reachability: Reachability
    probe_kind: ProbeKind
    addresses: tuple[str, ...] = ()
    mac_address: str | None = None


@dataclass(frozen=True, slots=True)
class KnownDeviceTarget:
    device_id: str
    dog_sniff_object_id: str
    address_hints: tuple[str, ...] = ()
    mac_address: str | None = None


@runtime_checkable
class LocalProbe(Protocol):
    def probe(self, target: KnownDeviceTarget) -> ProbeObservation:
        ...


class SniffOutcome(StrEnum):
    PUBLISHED_CHANGE = "PUBLISHED_CHANGE"
    PUBLISHED_FRESHNESS = "PUBLISHED_FRESHNESS"
    UNCHANGED = "UNCHANGED"
    FAILURE = "FAILURE"
    UNCONFIRMED = "UNCONFIRMED"


@dataclass(frozen=True, slots=True)
class SniffReport:
    outcome: SniffOutcome
    observation: ProbeObservation
    sequence: int
    probe_error: str | None = None
    message: str | None = None
    confirmation_probes: int = 0


@dataclass(slots=True)
class _PublishedState:
    observation: ProbeObservation | None = None
    published_monotonic_s: float | None = None
    sequence: int = 0


@dataclass(slots=True)
class KnownDeviceSniffer:
    """Low-cost known-device observer with write-on-change publication.

    Local probes may run frequently. Google Drive writes occur only when the
    meaningful observation changes or the configured freshness interval
    expires. Each target is independent; one probe failure becomes UNKNOWN
    evidence for that target and never blocks other targets.
    """

    backend: DriveBackend
    local_probe: LocalProbe
    retry_policy: RetryPolicy
    freshness_s: float
    monotonic_now: Callable[[], float]
    epoch_now: Callable[[], int]
    sleeper: Callable[[float], None]
    schema_store: SchemaStore | None = None
    _state: dict[str, _PublishedState] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.freshness_s <= 0:
            raise ValueError("freshness_s must be positive")

    def probe_once(self, target: KnownDeviceTarget) -> SniffReport:
        probe_error: str | None = None
        try:
            observation = self.local_probe.probe(target)
        except Exception as exc:
            probe_error = f"{type(exc).__name__}: {exc}"
            observation = ProbeObservation(
                reachability=Reachability.UNKNOWN,
                probe_kind=ProbeKind.NONE,
                addresses=target.address_hints,
                mac_address=target.mac_address,
            )

        state = self._state.setdefault(target.device_id, _PublishedState())
        now_monotonic = self.monotonic_now()
        changed = state.observation != observation
        freshness_due = (
            state.published_monotonic_s is None
            or now_monotonic - state.published_monotonic_s >= self.freshness_s
        )

        if not changed and not freshness_due:
            return SniffReport(
                SniffOutcome.UNCHANGED,
                observation,
                state.sequence,
                probe_error=probe_error,
            )

        publication = self._publish(
            target,
            observation,
            state,
            probe_error=probe_error,
        )
        if publication.outcome in {
            SniffOutcome.PUBLISHED_CHANGE,
            SniffOutcome.PUBLISHED_FRESHNESS,
        }:
            state.observation = observation
            state.published_monotonic_s = now_monotonic
            state.sequence = publication.sequence
            if not changed:
                return SniffReport(
                    SniffOutcome.PUBLISHED_FRESHNESS,
                    observation,
                    publication.sequence,
                    probe_error=probe_error,
                    confirmation_probes=publication.confirmation_probes,
                )
        return publication

    def _publish(
        self,
        target: KnownDeviceTarget,
        observation: ProbeObservation,
        state: _PublishedState,
        *,
        probe_error: str | None,
    ) -> SniffReport:
        observed_at = int(self.epoch_now())
        if observed_at <= 0:
            return SniffReport(
                SniffOutcome.FAILURE,
                observation,
                state.sequence,
                probe_error=probe_error,
                message="epoch clock must be positive",
            )

        metadata = self.backend.get_metadata(target.dog_sniff_object_id)
        if not metadata.ok or metadata.value is None:
            return SniffReport(
                SniffOutcome.FAILURE,
                observation,
                state.sequence,
                probe_error=probe_error,
                message=metadata.message or metadata.outcome.value,
            )
        if metadata.value.is_folder:
            return SniffReport(
                SniffOutcome.FAILURE,
                observation,
                state.sequence,
                probe_error=probe_error,
                message="DOG_SNIFF object is a folder",
            )

        remote_sequence = 0
        existing = self.backend.read_text(target.dog_sniff_object_id)
        if existing.ok and existing.value is not None:
            try:
                raw = json.loads(existing.value.text)
                if isinstance(raw, dict):
                    remote_sequence = max(0, int(raw.get("sequence", 0)))
            except (ValueError, TypeError, json.JSONDecodeError):
                remote_sequence = 0

        sequence = max(state.sequence, remote_sequence) + 1
        body = {
            "schema_version": 1,
            "protocol_major": 1,
            "device_id": target.device_id,
            "sequence": sequence,
            "observed_at": observed_at,
            "published_at": observed_at,
            "reachability": observation.reachability.value,
            "probe_kind": observation.probe_kind.value,
            "addresses": list(observation.addresses),
            "mac_address": observation.mac_address,
        }

        store = self.schema_store if self.schema_store is not None else load_schema_store()
        store.validate("dog-sniff.schema.json", body)
        body_text = canonical_json_text(body)
        body_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()

        write = self.backend.replace_text(
            target.dog_sniff_object_id,
            body_text,
            expected_version_token=metadata.value.version_token,
        )
        if write.outcome not in {BackendOutcome.SUCCESS, BackendOutcome.AMBIGUOUS}:
            return SniffReport(
                SniffOutcome.FAILURE,
                observation,
                state.sequence,
                probe_error=probe_error,
                message=write.message or write.outcome.value,
            )

        def probe_remote() -> ProbeDisposition:
            remote = self.backend.read_text(target.dog_sniff_object_id)
            if not remote.ok or remote.value is None:
                if remote.outcome is BackendOutcome.TRANSIENT_ERROR:
                    return ProbeDisposition.NOT_VISIBLE
                return ProbeDisposition.AMBIGUOUS
            remote_hash = hashlib.sha256(remote.value.text.encode("utf-8")).hexdigest()
            return (
                ProbeDisposition.CONFIRMED
                if remote_hash == body_hash
                else ProbeDisposition.NOT_VISIBLE
            )

        confirmation = confirm_with_backoff(
            probe_remote,
            policy=self.retry_policy,
            monotonic_now=self.monotonic_now,
            sleeper=self.sleeper,
        )
        if confirmation.reason is not RetryStopReason.CONFIRMED:
            return SniffReport(
                SniffOutcome.UNCONFIRMED,
                observation,
                state.sequence,
                probe_error=probe_error,
                message=f"DOG_SNIFF readback not confirmed: {confirmation.reason.value}",
                confirmation_probes=confirmation.probe_count,
            )

        outcome = (
            SniffOutcome.PUBLISHED_CHANGE
            if state.observation != observation
            else SniffOutcome.PUBLISHED_FRESHNESS
        )
        return SniffReport(
            outcome,
            observation,
            sequence,
            probe_error=probe_error,
            confirmation_probes=confirmation.probe_count,
        )
