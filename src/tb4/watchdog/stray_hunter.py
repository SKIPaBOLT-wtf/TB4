from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Callable, Protocol, Sequence, runtime_checkable

from tb4.core.retry import ProbeDisposition, RetryPolicy, RetryStopReason, confirm_with_backoff
from tb4.core.schemas import SchemaStore, canonical_json_text, load_schema_store
from tb4.drive.backend import DriveBackend, ObjectMetadata
from tb4.drive.errors import BackendOutcome


@dataclass(frozen=True, slots=True)
class DiscoveredDevice:
    addresses: tuple[str, ...] = ()
    mac_address: str | None = None
    stable_hardware_id: str | None = None
    discovery_token: str | None = None
    discovery_kind: str = "LAN_SCAN"


@runtime_checkable
class DiscoveryBackend(Protocol):
    def scan(self) -> Sequence[DiscoveredDevice]:
        ...


class StrayOutcome(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    UNCHANGED = "UNCHANGED"
    UNRESOLVED = "UNRESOLVED"
    FAILURE = "FAILURE"
    UNCONFIRMED = "UNCONFIRMED"


@dataclass(frozen=True, slots=True)
class StrayResult:
    outcome: StrayOutcome
    stray_key: str | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class DiscoveryReport:
    results: tuple[StrayResult, ...]
    backend_error: str | None = None

    @property
    def writes(self) -> int:
        return sum(
            result.outcome in {StrayOutcome.CREATED, StrayOutcome.UPDATED}
            for result in self.results
        )


@dataclass(slots=True)
class _CachedStray:
    folder_id: str
    card_id: str


@dataclass(slots=True)
class StrayHunter:
    """Maintenance-only LAN discovery publisher.

    A scan may enumerate STRAY_YARD because discovery is explicitly outside the
    normal control path. Unknown devices remain observation-only and are never
    registered in BALL_PARK or granted execution capabilities by this helper.
    """

    backend: DriveBackend
    discovery: DiscoveryBackend
    stray_yard_folder_id: str
    retry_policy: RetryPolicy
    epoch_now: Callable[[], int]
    monotonic_now: Callable[[], float]
    sleeper: Callable[[float], None]
    schema_store: SchemaStore | None = None
    _cache: dict[str, _CachedStray] = field(default_factory=dict)

    def scan_once(self) -> DiscoveryReport:
        try:
            devices = tuple(self.discovery.scan())
        except Exception as exc:
            return DiscoveryReport(
                (),
                backend_error=f"{type(exc).__name__}: {exc}",
            )

        yard = self.backend.list_children(self.stray_yard_folder_id)
        if not yard.ok or yard.value is None:
            return DiscoveryReport(
                (),
                backend_error=yard.message or yard.outcome.value,
            )

        folders_by_name: dict[str, list[ObjectMetadata]] = {}
        for child in yard.value:
            if child.is_folder:
                folders_by_name.setdefault(child.name, []).append(child)

        results: list[StrayResult] = []
        for device in devices:
            identity = self._identity(device)
            if identity is None:
                results.append(
                    StrayResult(
                        StrayOutcome.UNRESOLVED,
                        message="discovery has no deterministic identity source",
                    )
                )
                continue

            identity_kind, source = identity
            fingerprint = hashlib.sha256(source.encode("utf-8")).hexdigest()
            stray_key = f"stray-{fingerprint[:12]}"
            matching = folders_by_name.get(stray_key, [])

            if len(matching) > 1:
                results.append(
                    StrayResult(
                        StrayOutcome.FAILURE,
                        stray_key,
                        "duplicate deterministic stray folders require audit/quarantine",
                    )
                )
                continue

            if not matching:
                result = self._create_stray(
                    device,
                    stray_key=stray_key,
                    identity_kind=identity_kind,
                    fingerprint=fingerprint,
                )
                results.append(result)
                if result.outcome is StrayOutcome.CREATED:
                    created = self._cache.get(stray_key)
                    if created is not None:
                        folders_by_name[stray_key] = [
                            ObjectMetadata(
                                object_id=created.folder_id,
                                name=stray_key,
                                parent_ids=(self.stray_yard_folder_id,),
                                is_folder=True,
                            )
                        ]
                continue

            folder_id = matching[0].object_id
            result = self._update_existing(
                device,
                stray_key=stray_key,
                folder_id=folder_id,
                identity_kind=identity_kind,
                fingerprint=fingerprint,
            )
            results.append(result)

        return DiscoveryReport(tuple(results))

    def _create_stray(
        self,
        device: DiscoveredDevice,
        *,
        stray_key: str,
        identity_kind: str,
        fingerprint: str,
    ) -> StrayResult:
        folder = self.backend.create_folder(self.stray_yard_folder_id, stray_key)
        if not folder.ok or folder.value is None:
            return StrayResult(
                StrayOutcome.FAILURE,
                stray_key,
                folder.message or folder.outcome.value,
            )

        now = int(self.epoch_now())
        if now <= 0:
            return StrayResult(StrayOutcome.FAILURE, stray_key, "epoch clock must be positive")

        body = self._body(
            device,
            stray_key=stray_key,
            identity_kind=identity_kind,
            fingerprint=fingerprint,
            first_seen=now,
            last_seen=now,
        )
        text = canonical_json_text(body)
        card = self.backend.create_text(folder.value.metadata.object_id, "STRAY_CARD", text)
        if not card.ok or card.value is None:
            return StrayResult(
                StrayOutcome.FAILURE,
                stray_key,
                card.message or card.outcome.value,
            )

        self._cache[stray_key] = _CachedStray(
            folder.value.metadata.object_id,
            card.value.metadata.object_id,
        )
        return StrayResult(StrayOutcome.CREATED, stray_key)

    def _update_existing(
        self,
        device: DiscoveredDevice,
        *,
        stray_key: str,
        folder_id: str,
        identity_kind: str,
        fingerprint: str,
    ) -> StrayResult:
        cached = self._cache.get(stray_key)
        card_id: str | None = cached.card_id if cached and cached.folder_id == folder_id else None

        if card_id is None:
            children = self.backend.list_children(folder_id)
            if not children.ok or children.value is None:
                return StrayResult(
                    StrayOutcome.FAILURE,
                    stray_key,
                    children.message or children.outcome.value,
                )
            cards = [child for child in children.value if child.name == "STRAY_CARD"]
            if len(cards) > 1:
                return StrayResult(
                    StrayOutcome.FAILURE,
                    stray_key,
                    "duplicate STRAY_CARD objects require audit/quarantine",
                )
            if not cards:
                now = int(self.epoch_now())
                body = self._body(
                    device,
                    stray_key=stray_key,
                    identity_kind=identity_kind,
                    fingerprint=fingerprint,
                    first_seen=now,
                    last_seen=now,
                )
                created = self.backend.create_text(
                    folder_id,
                    "STRAY_CARD",
                    canonical_json_text(body),
                )
                if not created.ok or created.value is None:
                    return StrayResult(
                        StrayOutcome.FAILURE,
                        stray_key,
                        created.message or created.outcome.value,
                    )
                self._cache[stray_key] = _CachedStray(folder_id, created.value.metadata.object_id)
                return StrayResult(StrayOutcome.UPDATED, stray_key)
            card_id = cards[0].object_id
            self._cache[stray_key] = _CachedStray(folder_id, card_id)

        remote = self.backend.read_text(card_id)
        if not remote.ok or remote.value is None:
            return StrayResult(
                StrayOutcome.FAILURE,
                stray_key,
                remote.message or remote.outcome.value,
            )
        try:
            current = json.loads(remote.value.text)
            if not isinstance(current, dict):
                raise ValueError("STRAY_CARD body is not an object")
            self._store().validate("stray-card.schema.json", current)
        except Exception as exc:
            return StrayResult(
                StrayOutcome.FAILURE,
                stray_key,
                f"invalid STRAY_CARD: {exc}",
            )

        candidate_core = {
            "identity_kind": identity_kind,
            "identity_fingerprint": fingerprint,
            "addresses": sorted(set(device.addresses)),
            "mac_address": device.mac_address,
            "discovery_kind": device.discovery_kind,
        }
        current_core = {
            key: current[key]
            for key in candidate_core
        }
        if current_core == candidate_core:
            return StrayResult(StrayOutcome.UNCHANGED, stray_key)

        now = int(self.epoch_now())
        candidate = self._body(
            device,
            stray_key=stray_key,
            identity_kind=identity_kind,
            fingerprint=fingerprint,
            first_seen=int(current["first_seen"]),
            last_seen=now,
        )
        body_text = canonical_json_text(candidate)
        body_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()

        metadata = self.backend.get_metadata(card_id)
        if not metadata.ok or metadata.value is None:
            return StrayResult(
                StrayOutcome.FAILURE,
                stray_key,
                metadata.message or metadata.outcome.value,
            )
        write = self.backend.replace_text(
            card_id,
            body_text,
            expected_version_token=metadata.value.version_token,
        )
        if write.outcome not in {BackendOutcome.SUCCESS, BackendOutcome.AMBIGUOUS}:
            return StrayResult(
                StrayOutcome.FAILURE,
                stray_key,
                write.message or write.outcome.value,
            )

        def probe_remote() -> ProbeDisposition:
            observed = self.backend.read_text(card_id)
            if not observed.ok or observed.value is None:
                if observed.outcome is BackendOutcome.TRANSIENT_ERROR:
                    return ProbeDisposition.NOT_VISIBLE
                return ProbeDisposition.AMBIGUOUS
            observed_hash = hashlib.sha256(
                observed.value.text.encode("utf-8")
            ).hexdigest()
            return (
                ProbeDisposition.CONFIRMED
                if observed_hash == body_hash
                else ProbeDisposition.NOT_VISIBLE
            )

        confirmation = confirm_with_backoff(
            probe_remote,
            policy=self.retry_policy,
            monotonic_now=self.monotonic_now,
            sleeper=self.sleeper,
        )
        if confirmation.reason is not RetryStopReason.CONFIRMED:
            return StrayResult(
                StrayOutcome.UNCONFIRMED,
                stray_key,
                f"STRAY_CARD update not confirmed: {confirmation.reason.value}",
            )

        return StrayResult(StrayOutcome.UPDATED, stray_key)

    def _body(
        self,
        device: DiscoveredDevice,
        *,
        stray_key: str,
        identity_kind: str,
        fingerprint: str,
        first_seen: int,
        last_seen: int,
    ) -> dict:
        body = {
            "schema_version": 1,
            "protocol_major": 1,
            "stray_key": stray_key,
            "identity_kind": identity_kind,
            "identity_fingerprint": fingerprint,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "addresses": sorted(set(device.addresses)),
            "mac_address": device.mac_address,
            "discovery_kind": device.discovery_kind,
        }
        self._store().validate("stray-card.schema.json", body)
        return body

    def _store(self) -> SchemaStore:
        return self.schema_store if self.schema_store is not None else load_schema_store()

    @staticmethod
    def _identity(device: DiscoveredDevice) -> tuple[str, str] | None:
        if device.stable_hardware_id:
            return "HARDWARE", f"hardware:{device.stable_hardware_id.strip().lower()}"
        if device.mac_address:
            normalized = "".join(
                char for char in device.mac_address.lower() if char.isalnum()
            )
            if normalized:
                return "MAC", f"mac:{normalized}"
        if device.discovery_token:
            return "TOKEN", f"token:{device.discovery_token.strip().lower()}"
        addresses = tuple(sorted(set(device.addresses)))
        if addresses:
            return "ADDRESS_SET", "addresses:" + "|".join(addresses)
        return None
