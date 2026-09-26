from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from tb4.core.schemas import canonical_json_text

from .backend import DriveBackend, ObjectMetadata
from .errors import BackendOutcome
from .park_map import ParkMap, ParkMapError
from .tree_audit import (
    TreeAuditor,
    TreeAuditReport,
    TreeIssue,
    TreeIssueKind,
)


class TreeRepairError(RuntimeError):
    pass


class TreeRepairBlocked(TreeRepairError):
    pass


class RepairOutcome(StrEnum):
    CLEAN = "CLEAN"
    REPAIRED = "REPAIRED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class TreeRepairReport:
    outcome: RepairOutcome
    park_map: ParkMap
    passes: int
    created_refs: tuple[str, ...] = ()
    adopted_refs: tuple[str, ...] = ()
    restored_refs: tuple[str, ...] = ()
    quarantined_ids: tuple[str, ...] = ()
    remaining_issues: tuple[TreeIssue, ...] = ()
    message: str | None = None

    @property
    def success(self) -> bool:
        return self.outcome in {RepairOutcome.CLEAN, RepairOutcome.REPAIRED}


_SAFE_RECREATE_POLICIES = frozenset(
    {
        "create_from_canonical_template",
        "create_from_embedded_canonical_spec",
        "create_folder_only",
        "create_if_parent_is_verified",
        "create_empty_initial_if_missing",
        "create_initial_if_unambiguously_missing",
    }
)


@dataclass(slots=True)
class TreeHealer:
    backend: DriveBackend
    auditor: TreeAuditor | None = None
    max_passes: int = 4

    def repair(self, *, root_id: str, park_map: ParkMap) -> TreeRepairReport:
        auditor = self.auditor if self.auditor is not None else TreeAuditor(self.backend)
        current_map = park_map
        created: list[str] = []
        adopted: list[str] = []
        restored: list[str] = []
        quarantined: list[str] = []
        changed = False

        for pass_number in range(1, self.max_passes + 1):
            audit = auditor.audit(root_id=root_id, park_map=current_map)
            if audit.clean:
                return TreeRepairReport(
                    RepairOutcome.REPAIRED if changed else RepairOutcome.CLEAN,
                    current_map,
                    pass_number,
                    tuple(created),
                    tuple(adopted),
                    tuple(restored),
                    tuple(quarantined),
                )

            blocking = self._immediate_blocking_issue(audit)
            if blocking is not None:
                return self._blocked(
                    current_map,
                    pass_number,
                    audit,
                    created,
                    adopted,
                    restored,
                    quarantined,
                    f"blocking tree ambiguity: {blocking.kind.value}: {blocking.message or ''}",
                )

            progress = False
            handled_quarantine_ids: set[str] = set()

            # Quarantine noncanonical extras first. Canonical IDs are never moved
            # merely because another object has the same name.
            for issue in audit.issues:
                if issue.kind is TreeIssueKind.DUPLICATE_CANONICAL:
                    for object_id in issue.candidate_ids:
                        if object_id in handled_quarantine_ids:
                            continue
                        self._quarantine(
                            current_map,
                            object_id,
                            reason="DUPLICATE_CANONICAL",
                            logical_ref=issue.logical_ref,
                        )
                        handled_quarantine_ids.add(object_id)
                        quarantined.append(object_id)
                        progress = changed = True
                elif issue.kind is TreeIssueKind.UNKNOWN_CHILD and issue.object_id:
                    if issue.object_id in handled_quarantine_ids:
                        continue
                    self._quarantine(
                        current_map,
                        issue.object_id,
                        reason="UNKNOWN_CHILD",
                        logical_ref=None,
                    )
                    handled_quarantine_ids.add(issue.object_id)
                    quarantined.append(issue.object_id)
                    progress = changed = True

            # Restore a canonical stable ID that merely drifted to the wrong parent.
            for issue in audit.issues:
                if (
                    issue.kind is TreeIssueKind.CANONICAL_WRONG_PARENT
                    and issue.object_id
                    and issue.expected_parent_id
                ):
                    self._move_verified(issue.object_id, issue.expected_parent_id)
                    if issue.logical_ref:
                        restored.append(issue.logical_ref)
                    progress = changed = True

            # Repair missing/wrong-kind/name-invalid canonical references.
            for issue in audit.issues:
                if issue.kind not in {
                    TreeIssueKind.CANONICAL_ID_MISSING,
                    TreeIssueKind.CANONICAL_WRONG_KIND,
                    TreeIssueKind.CANONICAL_NAME_INVALID,
                }:
                    continue
                if not issue.logical_ref or issue.logical_ref == "PARK_MAP":
                    continue

                # If exactly one valid candidate exists, adopt it rather than
                # inventing a replacement. This preserves the unambiguous data.
                valid_candidates = self._valid_candidates(issue)
                if len(valid_candidates) > 1:
                    return self._blocked(
                        current_map,
                        pass_number,
                        audit,
                        created,
                        adopted,
                        restored,
                        quarantined,
                        f"multiple valid candidates for {issue.logical_ref}",
                    )

                old_id = current_map.lookup(issue.logical_ref)
                if len(valid_candidates) == 1:
                    replacement = valid_candidates[0]
                    if replacement.object_id != old_id:
                        next_map = current_map.replace_reference(
                            issue.logical_ref,
                            replacement.object_id,
                            expected_old_object_id=old_id,
                        )
                        self._persist_park_map(current_map, next_map)
                        current_map = next_map
                        adopted.append(issue.logical_ref)
                        progress = changed = True
                        if self._object_reachable(old_id):
                            self._quarantine(
                                current_map,
                                old_id,
                                reason="REPLACED_CORRUPT_CANONICAL",
                                logical_ref=issue.logical_ref,
                            )
                            quarantined.append(old_id)
                    continue

                # Static non-stateful objects may safely recover a bad name while
                # preserving the stable ID. A stateful name cannot be guessed.
                if (
                    issue.kind is TreeIssueKind.CANONICAL_NAME_INVALID
                    and not issue.stateful
                    and issue.object_id
                    and issue.initial_name
                ):
                    self._rename_verified(issue.object_id, issue.initial_name)
                    restored.append(issue.logical_ref)
                    progress = changed = True
                    continue

                if issue.repair_policy not in _SAFE_RECREATE_POLICIES:
                    return self._blocked(
                        current_map,
                        pass_number,
                        audit,
                        created,
                        adopted,
                        restored,
                        quarantined,
                        f"{issue.logical_ref} policy {issue.repair_policy!r} forbids automatic reconstruction",
                    )
                if not issue.expected_parent_id or issue.initial_name is None:
                    return self._blocked(
                        current_map,
                        pass_number,
                        audit,
                        created,
                        adopted,
                        restored,
                        quarantined,
                        f"insufficient reconstruction metadata for {issue.logical_ref}",
                    )

                replacement = self._create_verified(issue)
                next_map = current_map.replace_reference(
                    issue.logical_ref,
                    replacement.object_id,
                    expected_old_object_id=old_id,
                )
                self._persist_park_map(current_map, next_map)
                current_map = next_map
                created.append(issue.logical_ref)
                progress = changed = True

                if old_id != replacement.object_id and self._object_reachable(old_id):
                    self._quarantine(
                        current_map,
                        old_id,
                        reason="REPLACED_CORRUPT_CANONICAL",
                        logical_ref=issue.logical_ref,
                    )
                    quarantined.append(old_id)

            if not progress:
                return self._blocked(
                    current_map,
                    pass_number,
                    audit,
                    created,
                    adopted,
                    restored,
                    quarantined,
                    "audit found issues but no safe repair action was available",
                )

        final_audit = auditor.audit(root_id=root_id, park_map=current_map)
        return self._blocked(
            current_map,
            self.max_passes,
            final_audit,
            created,
            adopted,
            restored,
            quarantined,
            "tree did not converge within repair pass limit",
        )

    @staticmethod
    def _immediate_blocking_issue(audit: TreeAuditReport) -> TreeIssue | None:
        for issue in audit.issues:
            if issue.kind in {
                TreeIssueKind.ROOT_UNREACHABLE,
                TreeIssueKind.ROOT_WRONG_KIND,
                TreeIssueKind.PARK_MAP_CONFLICT,
            }:
                return issue
            if issue.logical_ref == "PARK_MAP" and issue.kind in {
                TreeIssueKind.CANONICAL_ID_MISSING,
                TreeIssueKind.CANONICAL_WRONG_PARENT,
                TreeIssueKind.CANONICAL_WRONG_KIND,
                TreeIssueKind.CANONICAL_NAME_INVALID,
            }:
                return issue
        return None

    def _valid_candidates(self, issue: TreeIssue) -> tuple[ObjectMetadata, ...]:
        valid: list[ObjectMetadata] = []
        for object_id in issue.candidate_ids:
            result = self.backend.get_metadata(object_id)
            if not result.ok or result.value is None:
                continue
            meta = result.value
            if meta.parent_ids != (issue.expected_parent_id,):
                continue
            if meta.is_folder != issue.expected_is_folder:
                continue
            if meta.name not in issue.allowed_names:
                continue
            valid.append(meta)
        return tuple(valid)

    def _create_verified(self, issue: TreeIssue) -> ObjectMetadata:
        assert issue.expected_parent_id is not None
        assert issue.initial_name is not None
        if issue.expected_is_folder:
            result = self.backend.create_folder(issue.expected_parent_id, issue.initial_name)
        else:
            result = self.backend.create_text(
                issue.expected_parent_id,
                issue.initial_name,
                self._initial_text(issue.logical_ref or ""),
            )

        if result.ok and result.value is not None:
            object_id = result.value.metadata.object_id
        elif result.outcome is BackendOutcome.AMBIGUOUS:
            candidates = self._children_named(issue.expected_parent_id, issue.initial_name)
            candidates = tuple(
                item for item in candidates if item.is_folder == issue.expected_is_folder
            )
            if len(candidates) != 1:
                raise TreeRepairBlocked(
                    f"ambiguous create for {issue.logical_ref} did not reconcile uniquely"
                )
            object_id = candidates[0].object_id
        else:
            raise TreeRepairBlocked(
                f"create failed for {issue.logical_ref}: {result.outcome.value}"
            )

        observed = self.backend.get_metadata(object_id)
        if not observed.ok or observed.value is None:
            raise TreeRepairBlocked(f"created {issue.logical_ref} cannot be read back")
        meta = observed.value
        if (
            meta.parent_ids != (issue.expected_parent_id,)
            or meta.is_folder != issue.expected_is_folder
            or meta.name != issue.initial_name
        ):
            raise TreeRepairBlocked(f"created {issue.logical_ref} failed verification")
        return meta

    def _persist_park_map(self, old_map: ParkMap, new_map: ParkMap) -> None:
        map_id = old_map.lookup("PARK_MAP")
        metadata = self.backend.get_metadata(map_id)
        if not metadata.ok or metadata.value is None:
            raise TreeRepairBlocked("PARK_MAP metadata unavailable during update")
        body = canonical_json_text(new_map.to_dict())
        result = self.backend.replace_text(
            map_id,
            body,
            expected_version_token=metadata.value.version_token,
        )
        if result.outcome not in {BackendOutcome.SUCCESS, BackendOutcome.AMBIGUOUS}:
            raise TreeRepairBlocked(f"PARK_MAP update failed: {result.outcome.value}")

        readback = self.backend.read_text(map_id)
        if not readback.ok or readback.value is None:
            raise TreeRepairBlocked("PARK_MAP update could not be read back")
        try:
            observed = ParkMap.from_dict(json.loads(readback.value.text))
        except (ValueError, json.JSONDecodeError) as exc:
            raise TreeRepairBlocked(f"PARK_MAP readback invalid: {exc}") from exc
        if observed != new_map:
            raise TreeRepairBlocked("PARK_MAP update is unconfirmed")

    def _move_verified(self, object_id: str, parent_id: str) -> None:
        metadata = self.backend.get_metadata(object_id)
        if not metadata.ok or metadata.value is None:
            raise TreeRepairBlocked(f"cannot read object {object_id} before move")
        if metadata.value.parent_ids == (parent_id,):
            return
        result = self.backend.move(
            object_id,
            parent_id,
            expected_version_token=metadata.value.version_token,
        )
        if result.outcome not in {BackendOutcome.SUCCESS, BackendOutcome.AMBIGUOUS}:
            raise TreeRepairBlocked(f"move failed for {object_id}: {result.outcome.value}")
        observed = self.backend.get_metadata(object_id)
        if not observed.ok or observed.value is None or observed.value.parent_ids != (parent_id,):
            raise TreeRepairBlocked(f"move for {object_id} is unconfirmed")

    def _rename_verified(self, object_id: str, name: str) -> None:
        metadata = self.backend.get_metadata(object_id)
        if not metadata.ok or metadata.value is None:
            raise TreeRepairBlocked(f"cannot read object {object_id} before rename")
        if metadata.value.name == name:
            return
        result = self.backend.rename(
            object_id,
            name,
            expected_version_token=metadata.value.version_token,
        )
        if result.outcome not in {BackendOutcome.SUCCESS, BackendOutcome.AMBIGUOUS}:
            raise TreeRepairBlocked(f"rename failed for {object_id}: {result.outcome.value}")
        observed = self.backend.get_metadata(object_id)
        if not observed.ok or observed.value is None or observed.value.name != name:
            raise TreeRepairBlocked(f"rename for {object_id} is unconfirmed")

    def _quarantine(
        self,
        park_map: ParkMap,
        object_id: str,
        *,
        reason: str,
        logical_ref: str | None,
    ) -> None:
        dog_pound_id = park_map.lookup("DOG_POUND")
        source = self.backend.get_metadata(object_id)
        if not source.ok or source.value is None:
            return
        original = source.value
        if original.parent_ids == (dog_pound_id,):
            return

        self._move_verified(object_id, dog_pound_id)

        note_name = "QUARANTINE_" + hashlib.sha256(object_id.encode("utf-8")).hexdigest()[:16] + ".json"
        note_body = canonical_json_text(
            {
                "schema_version": 1,
                "object_id": object_id,
                "original_name": original.name,
                "original_parent_ids": list(original.parent_ids),
                "reason": reason,
                "logical_ref": logical_ref,
            }
        )
        existing = self._children_named(dog_pound_id, note_name)
        if len(existing) > 1:
            raise TreeRepairBlocked(f"duplicate quarantine note {note_name}")
        if len(existing) == 1:
            read = self.backend.read_text(existing[0].object_id)
            if not read.ok or read.value is None or read.value.text != note_body:
                raise TreeRepairBlocked(f"quarantine note conflict for {object_id}")
            return

        created = self.backend.create_text(dog_pound_id, note_name, note_body)
        if created.outcome is BackendOutcome.AMBIGUOUS:
            existing = self._children_named(dog_pound_id, note_name)
            if len(existing) == 1:
                read = self.backend.read_text(existing[0].object_id)
                if read.ok and read.value is not None and read.value.text == note_body:
                    return
        if not created.ok:
            raise TreeRepairBlocked(f"failed to persist quarantine provenance for {object_id}")

    def _children_named(self, parent_id: str, name: str) -> tuple[ObjectMetadata, ...]:
        listed = self.backend.list_children(parent_id)
        if not listed.ok or listed.value is None:
            raise TreeRepairBlocked(f"cannot enumerate parent {parent_id}")
        return tuple(item for item in listed.value if item.name == name)

    def _object_reachable(self, object_id: str) -> bool:
        return self.backend.get_metadata(object_id).ok

    @staticmethod
    def _initial_text(logical_ref: str) -> str:
        if logical_ref == "START_HERE":
            return (
                "TB4 persistent control tree. Read the public repository "
                "docs/START_HERE.md for protocol documentation.\n"
            )
        return "{}\n"

    @staticmethod
    def _blocked(
        park_map: ParkMap,
        passes: int,
        audit: TreeAuditReport,
        created: Iterable[str],
        adopted: Iterable[str],
        restored: Iterable[str],
        quarantined: Iterable[str],
        message: str,
    ) -> TreeRepairReport:
        return TreeRepairReport(
            RepairOutcome.BLOCKED,
            park_map,
            passes,
            tuple(created),
            tuple(adopted),
            tuple(restored),
            tuple(quarantined),
            audit.issues,
            message,
        )
