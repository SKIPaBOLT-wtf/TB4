from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Callable, Collection, Mapping

from tb4.core.schemas import (
    SchemaStore,
    SchemaValidationError,
    canonical_json_text,
    load_schema_store,
)
from tb4.drive.backend import DriveBackend, ObjectMetadata
from tb4.drive.delete_keeper import DeleteKeeper
from tb4.drive.errors import BackendOutcome


class RetentionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    boneyard_retention_s: int
    toy_box_retention_s: int
    max_deletes_per_sweep: int = 256

    def __post_init__(self) -> None:
        if self.boneyard_retention_s <= 0:
            raise ValueError("boneyard_retention_s must be positive")
        if self.toy_box_retention_s <= 0:
            raise ValueError("toy_box_retention_s must be positive")
        if self.max_deletes_per_sweep <= 0:
            raise ValueError("max_deletes_per_sweep must be positive")


@dataclass(frozen=True, slots=True)
class TerminalSummary:
    device_id: str
    operation_id: str
    generation: int
    terminal_state: str
    finished_at: int
    reason_code: str | None = None
    exit_code: int | None = None
    result_artifact_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.generation <= 0:
            raise ValueError("generation must be positive")
        if self.finished_at <= 0:
            raise ValueError("finished_at must be positive")
        if self.terminal_state not in {
            "DONE",
            "PARTIAL",
            "FAILED",
            "CANCELLED",
            "GONE",
        }:
            raise ValueError("terminal_state is not a canonical FETCH_BALL terminal state")


@dataclass(frozen=True, slots=True)
class SummaryRecord:
    object_id: str
    name: str
    body: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class SweepReport:
    scanned_boneyard: int
    scanned_toy_box: int
    deleted: int
    preserved: int
    malformed_preserved: int
    failures: int
    clock_blocked: bool
    delete_limit_reached: bool
    deleted_ids: tuple[str, ...] = ()
    failed_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class BoneyardKeeper:
    """Bounded terminal-history and TOY_BOX retention helper.

    BONEYARD and TOY_BOX are explicitly outside the live control path. This
    helper is constructed with their exact canonical folder IDs and never
    follows arbitrary paths supplied by remote objects.

    Live control references are supplied as exact descriptor IDs by the caller.
    Unexpired BONEYARD records add their own artifact references to the
    protected set so historical evidence remains self-consistent until expiry.
    """

    backend: DriveBackend
    delete_keeper: DeleteKeeper
    boneyard_folder_id: str
    toy_box_folder_id: str
    policy: RetentionPolicy
    epoch_now: Callable[[], int]
    clock_safe: Callable[[], bool]
    schema_store: SchemaStore | None = None

    def record_terminal_summary(self, summary: TerminalSummary) -> SummaryRecord:
        store = self.schema_store if self.schema_store is not None else load_schema_store()
        recorded_at = int(self.epoch_now())
        body: dict[str, object] = {
            "schema_version": 1,
            "protocol_major": 1,
            "device_id": summary.device_id,
            "operation_id": summary.operation_id,
            "generation": summary.generation,
            "terminal_state": summary.terminal_state,
            "finished_at": summary.finished_at,
            "recorded_at": recorded_at,
            "expires_at": summary.finished_at + self.policy.boneyard_retention_s,
            "reason_code": summary.reason_code,
            "exit_code": summary.exit_code,
            "result_artifact_ids": list(summary.result_artifact_ids),
        }
        store.validate("boneyard-record.schema.json", body)
        text = canonical_json_text(body)

        token = hashlib.sha256(summary.operation_id.encode("utf-8")).hexdigest()[:16]
        name = (
            f"BALL_{summary.finished_at}_{summary.generation}_"
            f"{token}_{summary.terminal_state}.json"
        )

        listed = self.backend.list_children(self.boneyard_folder_id)
        if not listed.ok or listed.value is None:
            raise RetentionError(
                f"cannot inspect BONEYARD before summary create: {listed.outcome.value}"
            )
        matches = [item for item in listed.value if item.name == name]
        if len(matches) > 1:
            raise RetentionError(f"duplicate BONEYARD summary name {name!r}")
        if len(matches) == 1:
            existing = self.backend.read_text(matches[0].object_id)
            if not existing.ok or existing.value is None:
                raise RetentionError("existing BONEYARD summary cannot be read")
            if existing.value.text != text:
                raise RetentionError("existing BONEYARD summary conflicts with canonical body")
            return SummaryRecord(matches[0].object_id, name, body)

        created = self.backend.create_text(self.boneyard_folder_id, name, text)
        if created.outcome is BackendOutcome.AMBIGUOUS:
            listed = self.backend.list_children(self.boneyard_folder_id)
            if not listed.ok or listed.value is None:
                raise RetentionError("ambiguous summary create could not be reconciled")
            matches = [item for item in listed.value if item.name == name]
            if len(matches) != 1:
                raise RetentionError("ambiguous summary create did not reconcile uniquely")
            object_id = matches[0].object_id
        elif created.ok and created.value is not None:
            object_id = created.value.metadata.object_id
        else:
            raise RetentionError(
                f"BONEYARD summary create failed: {created.outcome.value}"
            )

        readback = self.backend.read_text(object_id)
        if not readback.ok or readback.value is None or readback.value.text != text:
            raise RetentionError("BONEYARD summary create was not remotely confirmed")
        return SummaryRecord(object_id, name, body)

    def sweep(
        self,
        *,
        protected_artifact_ids: Collection[str] = (),
    ) -> SweepReport:
        if not self.clock_safe():
            return SweepReport(0, 0, 0, 0, 0, 0, True, False)

        now = int(self.epoch_now())
        store = self.schema_store if self.schema_store is not None else load_schema_store()
        deleted_ids: list[str] = []
        failed_ids: list[str] = []
        preserved = 0
        malformed = 0
        live_history_artifacts: set[str] = set()

        boneyard_children = self._list_exact(self.boneyard_folder_id, "BONEYARD")
        for item in boneyard_children:
            if item.is_folder:
                malformed += 1
                continue
            parsed = self._validated_json(item.object_id, "boneyard-record.schema.json", store)
            if parsed is None:
                malformed += 1
                continue

            expires_at = int(parsed["expires_at"])
            if expires_at > now:
                preserved += 1
                live_history_artifacts.update(
                    str(value) for value in parsed.get("result_artifact_ids", [])
                )
                continue

            if self._delete_budget_exhausted(deleted_ids):
                preserved += 1
                continue
            report = self.delete_keeper.delete_verified(
                object_id=item.object_id,
                allowed_parent_ids=(self.boneyard_folder_id,),
            )
            if report.success:
                deleted_ids.append(item.object_id)
            else:
                failed_ids.append(item.object_id)

        toy_children = self._list_exact(self.toy_box_folder_id, "TOY_BOX")
        descriptors: dict[str, tuple[ObjectMetadata, dict[str, object]]] = {}
        content_referrers: dict[str, set[str]] = {}

        for item in toy_children:
            if item.is_folder:
                malformed += 1
                continue
            parsed = self._validated_json(item.object_id, "artifact.schema.json", store)
            if parsed is None or parsed.get("artifact_id") != item.object_id:
                continue
            descriptors[item.object_id] = (item, parsed)
            content_id = str(parsed["content_object_id"])
            content_referrers.setdefault(content_id, set()).add(item.object_id)

        protected_descriptors = set(protected_artifact_ids) | live_history_artifacts
        expired_candidates: set[str] = set()
        for descriptor_id, (_, body) in descriptors.items():
            if descriptor_id in protected_descriptors:
                preserved += 1
                continue
            if int(body["expires_at"]) > now:
                preserved += 1
                continue
            expired_candidates.add(descriptor_id)

        # Remove expired descriptors first. Content is removed only after no
        # surviving descriptor references it, preventing broken shared content.
        for descriptor_id in sorted(expired_candidates):
            if self._delete_budget_exhausted(deleted_ids):
                preserved += 1
                continue
            report = self.delete_keeper.delete_verified(
                object_id=descriptor_id,
                allowed_parent_ids=(self.toy_box_folder_id,),
            )
            if report.success:
                deleted_ids.append(descriptor_id)
            else:
                failed_ids.append(descriptor_id)

        all_toy_ids = {item.object_id for item in toy_children}
        known_content_ids = set(content_referrers)
        protected_content_ids = {
            str(descriptors[descriptor_id][1]["content_object_id"])
            for descriptor_id in protected_descriptors
            if descriptor_id in descriptors
        }

        for content_id in sorted(known_content_ids):
            if content_id in protected_content_ids:
                preserved += 1
                continue

            referrers = content_referrers[content_id]
            any_referrer_survives = any(
                self.backend.get_metadata(descriptor_id).outcome
                is not BackendOutcome.NOT_FOUND
                for descriptor_id in referrers
            )
            if any_referrer_survives:
                preserved += 1
                continue
            if content_id not in all_toy_ids:
                continue
            if self._delete_budget_exhausted(deleted_ids):
                preserved += 1
                continue
            report = self.delete_keeper.delete_verified(
                object_id=content_id,
                allowed_parent_ids=(self.toy_box_folder_id,),
            )
            if report.success:
                deleted_ids.append(content_id)
            else:
                failed_ids.append(content_id)

        # Failed uploads can leave content with no descriptor. Clean only names
        # that TB4 itself reserves for artifact content, and only after provider
        # metadata proves they are older than the configured retention window.
        orphan_cutoff = now - self.policy.toy_box_retention_s
        descriptor_ids = set(descriptors)
        for item in toy_children:
            if item.object_id in descriptor_ids or item.object_id in known_content_ids:
                continue
            if not self._known_content_name(item.name):
                if self._looks_like_descriptor_name(item.name):
                    malformed += 1
                continue
            if item.modified_epoch_s is None or item.modified_epoch_s > orphan_cutoff:
                preserved += 1
                continue
            if self._delete_budget_exhausted(deleted_ids):
                preserved += 1
                continue
            report = self.delete_keeper.delete_verified(
                object_id=item.object_id,
                allowed_parent_ids=(self.toy_box_folder_id,),
            )
            if report.success:
                deleted_ids.append(item.object_id)
            else:
                failed_ids.append(item.object_id)

        return SweepReport(
            scanned_boneyard=len(boneyard_children),
            scanned_toy_box=len(toy_children),
            deleted=len(deleted_ids),
            preserved=preserved,
            malformed_preserved=malformed,
            failures=len(failed_ids),
            clock_blocked=False,
            delete_limit_reached=self._delete_budget_exhausted(deleted_ids),
            deleted_ids=tuple(deleted_ids),
            failed_ids=tuple(failed_ids),
        )

    def _list_exact(self, folder_id: str, label: str) -> tuple[ObjectMetadata, ...]:
        result = self.backend.list_children(folder_id)
        if not result.ok or result.value is None:
            raise RetentionError(f"cannot enumerate canonical {label}: {result.outcome.value}")
        return tuple(result.value)

    def _validated_json(
        self,
        object_id: str,
        schema_name: str,
        store: SchemaStore,
    ) -> dict[str, object] | None:
        result = self.backend.read_text(object_id)
        if not result.ok or result.value is None:
            return None
        try:
            body = json.loads(result.value.text)
            if not isinstance(body, dict):
                return None
            store.validate(schema_name, body)
        except (json.JSONDecodeError, SchemaValidationError):
            return None
        return body

    def _delete_budget_exhausted(self, deleted_ids: Collection[str]) -> bool:
        return len(deleted_ids) >= self.policy.max_deletes_per_sweep

    @staticmethod
    def _known_content_name(name: str) -> bool:
        return name.startswith(
            ("result-content-", "request-content-", "artifact-content-")
        )

    @staticmethod
    def _looks_like_descriptor_name(name: str) -> bool:
        return name.startswith(
            ("result-descriptor-", "request-descriptor-", "artifact-descriptor-")
        )
