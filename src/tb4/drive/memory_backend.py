from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, replace
from typing import Deque, Sequence

from .backend import (
    CreatedObject,
    DriveBackend,
    DriveCapabilities,
    MutationReceipt,
    ObjectMetadata,
    TextObject,
)
from .errors import BackendOutcome, BackendResult


@dataclass(slots=True)
class _MemoryObject:
    object_id: str
    name: str
    parent_id: str | None
    is_folder: bool
    text: str
    version: int
    modified_epoch_s: int


@dataclass(slots=True)
class _VisibilityLag:
    snapshot: _MemoryObject
    remaining_reads: int


class InMemoryDriveBackend:
    """Deterministic DriveBackend test double with stable opaque identities."""

    capabilities = DriveCapabilities(
        stable_object_ids=True,
        exact_metadata_read=True,
        exact_text_read=True,
        atomic_rename_request=True,
        atomic_move_request=True,
        create_text=True,
        change_feed=False,
        maintenance_listing=True,
        permanent_delete=True,
        atomic_version_precondition=True,
    )

    def __init__(self) -> None:
        self._id_counter = 0
        self._version_counter = 0
        self._objects: dict[str, _MemoryObject] = {}
        self._failure_queues: dict[str, Deque[BackendOutcome]] = defaultdict(deque)
        self._operation_counts: dict[str, int] = defaultdict(int)
        self._next_visibility_delay_reads = 0
        self._visibility_lag: dict[str, _VisibilityLag] = {}

        root = self._new_object(
            name="ROOT",
            parent_id=None,
            is_folder=True,
            text="",
        )
        self._root_id = root.object_id

    @property
    def root_id(self) -> str:
        return self._root_id

    @property
    def operation_counts(self) -> dict[str, int]:
        return dict(self._operation_counts)

    def reset_operation_counts(self) -> None:
        self._operation_counts.clear()

    def inject_outcome(
        self,
        operation: str,
        outcome: BackendOutcome,
        *,
        times: int = 1,
    ) -> None:
        if times <= 0:
            raise ValueError("times must be positive")
        if outcome is BackendOutcome.SUCCESS:
            raise ValueError("SUCCESS does not need failure injection")
        self._failure_queues[operation].extend(outcome for _ in range(times))

    def delay_next_mutation_visibility(self, *, reads: int) -> None:
        if reads <= 0:
            raise ValueError("reads must be positive")
        self._next_visibility_delay_reads = reads

    def get_metadata(self, object_id: str) -> BackendResult[ObjectMetadata]:
        self._count("get_metadata")
        injected = self._consume_injected("get_metadata")
        if injected is not None:
            return BackendResult.failure(injected, message="injected get_metadata outcome")

        obj = self._visible_object(object_id)
        if obj is None:
            return BackendResult.failure(BackendOutcome.NOT_FOUND)
        return BackendResult.success(self._metadata(obj))

    def read_text(self, object_id: str) -> BackendResult[TextObject]:
        self._count("read_text")
        injected = self._consume_injected("read_text")
        if injected is not None:
            return BackendResult.failure(injected, message="injected read_text outcome")

        obj = self._visible_object(object_id)
        if obj is None:
            return BackendResult.failure(BackendOutcome.NOT_FOUND)
        if obj.is_folder:
            return BackendResult.failure(
                BackendOutcome.CONFLICT,
                message="folder cannot be read as text",
            )
        return BackendResult.success(TextObject(self._metadata(obj), obj.text))

    def replace_text(
        self,
        object_id: str,
        text: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        self._count("replace_text")
        return self._mutate_existing(
            "replace_text",
            object_id,
            expected_version_token,
            lambda obj: setattr(obj, "text", text),
        )

    def rename(
        self,
        object_id: str,
        new_name: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        self._count("rename")
        if not new_name:
            return BackendResult.failure(BackendOutcome.CONFLICT, message="name must not be empty")

        return self._mutate_existing(
            "rename",
            object_id,
            expected_version_token,
            lambda obj: setattr(obj, "name", new_name),
            requested_name=new_name,
        )

    def move(
        self,
        object_id: str,
        new_parent_id: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        self._count("move")
        parent = self._objects.get(new_parent_id)
        if parent is None:
            return BackendResult.failure(BackendOutcome.NOT_FOUND, message="parent not found")
        if not parent.is_folder:
            return BackendResult.failure(BackendOutcome.CONFLICT, message="parent is not a folder")
        if object_id == self._root_id:
            return BackendResult.failure(BackendOutcome.CONFLICT, message="root cannot be moved")

        return self._mutate_existing(
            "move",
            object_id,
            expected_version_token,
            lambda obj: setattr(obj, "parent_id", new_parent_id),
            requested_parent_id=new_parent_id,
        )

    def delete(
        self,
        object_id: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        self._count("delete")
        injected = self._consume_injected("delete")
        if injected is not None and injected is not BackendOutcome.AMBIGUOUS:
            return BackendResult.failure(injected, message="injected delete outcome")

        obj = self._objects.get(object_id)
        if obj is None:
            return BackendResult.failure(BackendOutcome.NOT_FOUND)
        if object_id == self._root_id:
            return BackendResult.failure(BackendOutcome.CONFLICT, message="root cannot be deleted")
        if (
            expected_version_token is not None
            and expected_version_token != self._version_token(obj)
        ):
            return BackendResult.failure(
                BackendOutcome.CONFLICT,
                message="expected version token does not match current object",
            )
        if obj.is_folder and any(
            candidate.parent_id == object_id for candidate in self._objects.values()
        ):
            return BackendResult.failure(
                BackendOutcome.CONFLICT,
                message="non-empty folder cannot be deleted",
            )

        snapshot = replace(obj)
        del self._objects[object_id]
        if self._next_visibility_delay_reads > 0:
            self._visibility_lag[object_id] = _VisibilityLag(
                snapshot=snapshot,
                remaining_reads=self._next_visibility_delay_reads,
            )
            self._next_visibility_delay_reads = 0

        if injected is BackendOutcome.AMBIGUOUS:
            return BackendResult.failure(
                BackendOutcome.AMBIGUOUS,
                message="injected ambiguous delete; object may be gone",
            )
        return BackendResult.success(MutationReceipt(object_id=object_id))

    def create_folder(
        self,
        parent_id: str,
        name: str,
    ) -> BackendResult[CreatedObject]:
        self._count("create_folder")
        return self._create("create_folder", parent_id, name, is_folder=True, text="")

    def create_text(
        self,
        parent_id: str,
        name: str,
        text: str,
    ) -> BackendResult[CreatedObject]:
        self._count("create_text")
        return self._create("create_text", parent_id, name, is_folder=False, text=text)

    def list_children(
        self,
        parent_id: str,
    ) -> BackendResult[Sequence[ObjectMetadata]]:
        self._count("list_children")
        injected = self._consume_injected("list_children")
        if injected is not None:
            return BackendResult.failure(injected, message="injected list_children outcome")

        parent = self._objects.get(parent_id)
        if parent is None:
            return BackendResult.failure(BackendOutcome.NOT_FOUND)
        if not parent.is_folder:
            return BackendResult.failure(BackendOutcome.CONFLICT, message="parent is not a folder")

        children = tuple(
            self._metadata(obj)
            for obj in sorted(self._objects.values(), key=lambda item: item.object_id)
            if obj.parent_id == parent_id
        )
        return BackendResult.success(children)

    def _create(
        self,
        operation: str,
        parent_id: str,
        name: str,
        *,
        is_folder: bool,
        text: str,
    ) -> BackendResult[CreatedObject]:
        injected = self._consume_injected(operation)
        if injected is not None and injected is not BackendOutcome.AMBIGUOUS:
            return BackendResult.failure(injected, message=f"injected {operation} outcome")

        parent = self._objects.get(parent_id)
        if parent is None:
            return BackendResult.failure(BackendOutcome.NOT_FOUND, message="parent not found")
        if not parent.is_folder:
            return BackendResult.failure(BackendOutcome.CONFLICT, message="parent is not a folder")
        if not name:
            return BackendResult.failure(BackendOutcome.CONFLICT, message="name must not be empty")

        obj = self._new_object(
            name=name,
            parent_id=parent_id,
            is_folder=is_folder,
            text=text,
        )
        if injected is BackendOutcome.AMBIGUOUS:
            return BackendResult.failure(
                BackendOutcome.AMBIGUOUS,
                message=f"injected ambiguous {operation}; object may exist",
            )
        return BackendResult.success(CreatedObject(self._metadata(obj)))

    def _mutate_existing(
        self,
        operation: str,
        object_id: str,
        expected_version_token: str | None,
        mutation,
        *,
        requested_name: str | None = None,
        requested_parent_id: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        injected = self._consume_injected(operation)
        if injected is not None and injected is not BackendOutcome.AMBIGUOUS:
            return BackendResult.failure(injected, message=f"injected {operation} outcome")

        obj = self._objects.get(object_id)
        if obj is None:
            return BackendResult.failure(BackendOutcome.NOT_FOUND)

        if (
            expected_version_token is not None
            and expected_version_token != self._version_token(obj)
        ):
            return BackendResult.failure(
                BackendOutcome.CONFLICT,
                message="expected version token does not match current object",
            )

        snapshot = replace(obj)
        mutation(obj)
        self._touch(obj)
        self._install_visibility_lag(object_id, snapshot)

        if injected is BackendOutcome.AMBIGUOUS:
            return BackendResult.failure(
                BackendOutcome.AMBIGUOUS,
                message=f"injected ambiguous {operation}; mutation may have applied",
            )

        return BackendResult.success(
            MutationReceipt(
                object_id=object_id,
                requested_name=requested_name,
                requested_parent_id=requested_parent_id,
                version_token=self._version_token(obj),
            )
        )

    def _new_object(
        self,
        *,
        name: str,
        parent_id: str | None,
        is_folder: bool,
        text: str,
    ) -> _MemoryObject:
        self._id_counter += 1
        self._version_counter += 1
        obj = _MemoryObject(
            object_id=f"mem-{self._id_counter:06d}",
            name=name,
            parent_id=parent_id,
            is_folder=is_folder,
            text=text,
            version=1,
            modified_epoch_s=self._version_counter,
        )
        self._objects[obj.object_id] = obj
        return obj

    def _touch(self, obj: _MemoryObject) -> None:
        obj.version += 1
        self._version_counter += 1
        obj.modified_epoch_s = self._version_counter

    def _install_visibility_lag(self, object_id: str, snapshot: _MemoryObject) -> None:
        if self._next_visibility_delay_reads <= 0:
            return
        self._visibility_lag[object_id] = _VisibilityLag(
            snapshot=snapshot,
            remaining_reads=self._next_visibility_delay_reads,
        )
        self._next_visibility_delay_reads = 0

    def _visible_object(self, object_id: str) -> _MemoryObject | None:
        lag = self._visibility_lag.get(object_id)
        if lag is not None and lag.remaining_reads > 0:
            lag.remaining_reads -= 1
            snapshot = lag.snapshot
            if lag.remaining_reads == 0:
                del self._visibility_lag[object_id]
            return snapshot
        return self._objects.get(object_id)

    def _metadata(self, obj: _MemoryObject) -> ObjectMetadata:
        return ObjectMetadata(
            object_id=obj.object_id,
            name=obj.name,
            parent_ids=() if obj.parent_id is None else (obj.parent_id,),
            is_folder=obj.is_folder,
            version_token=self._version_token(obj),
            size_bytes=None if obj.is_folder else len(obj.text.encode("utf-8")),
            modified_epoch_s=obj.modified_epoch_s,
        )

    @staticmethod
    def _version_token(obj: _MemoryObject) -> str:
        return f"v{obj.version}"

    def _consume_injected(self, operation: str) -> BackendOutcome | None:
        queue = self._failure_queues.get(operation)
        if not queue:
            return None
        outcome = queue.popleft()
        if not queue:
            self._failure_queues.pop(operation, None)
        return outcome

    def _count(self, operation: str) -> None:
        self._operation_counts[operation] += 1
