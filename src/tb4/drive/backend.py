from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable

from .errors import BackendResult


@dataclass(frozen=True, slots=True)
class DriveCapabilities:
    stable_object_ids: bool
    exact_metadata_read: bool
    exact_text_read: bool
    atomic_rename_request: bool
    atomic_move_request: bool
    create_text: bool
    change_feed: bool
    maintenance_listing: bool = True
    permanent_delete: bool = False


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    object_id: str
    name: str
    parent_ids: tuple[str, ...]
    is_folder: bool
    version_token: str | None = None
    size_bytes: int | None = None
    modified_epoch_s: int | None = None


@dataclass(frozen=True, slots=True)
class TextObject:
    metadata: ObjectMetadata
    text: str


@dataclass(frozen=True, slots=True)
class MutationReceipt:
    object_id: str
    requested_name: str | None = None
    requested_parent_id: str | None = None
    version_token: str | None = None


@dataclass(frozen=True, slots=True)
class CreatedObject:
    metadata: ObjectMetadata


@runtime_checkable
class DriveBackend(Protocol):
    """Provider-neutral TB4 storage boundary.

    Exact object operations are the normal control path. list_children is
    maintenance/discovery only and must not become normal state lookup.
    Implementations normalize provider errors into BackendResult outcomes.
    """

    @property
    def capabilities(self) -> DriveCapabilities:
        ...

    def get_metadata(self, object_id: str) -> BackendResult[ObjectMetadata]:
        ...

    def read_text(self, object_id: str) -> BackendResult[TextObject]:
        ...

    def replace_text(
        self,
        object_id: str,
        text: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        ...

    def rename(
        self,
        object_id: str,
        new_name: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        ...

    def move(
        self,
        object_id: str,
        new_parent_id: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        ...

    def create_folder(
        self,
        parent_id: str,
        name: str,
    ) -> BackendResult[CreatedObject]:
        ...

    def create_text(
        self,
        parent_id: str,
        name: str,
        text: str,
    ) -> BackendResult[CreatedObject]:
        ...

    def delete(
        self,
        object_id: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        """Maintenance-only permanent deletion.

        Runtime control state must never use deletion as a state transition.
        Callers must prove the object belongs to a canonical retention root.
        """

        ...

    def list_children(
        self,
        parent_id: str,
    ) -> BackendResult[Sequence[ObjectMetadata]]:
        """Maintenance/discovery operation; never required for known state lookup."""
        ...
