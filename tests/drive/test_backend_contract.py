from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import pytest

from tb4.drive.backend import (
    CreatedObject,
    DriveBackend,
    DriveCapabilities,
    MutationReceipt,
    ObjectMetadata,
    TextObject,
)
from tb4.drive.errors import BackendOutcome, BackendResult


class ContractBackend:
    """Minimal structural implementation used only to prove Protocol shape."""

    capabilities = DriveCapabilities(
        stable_object_ids=True,
        exact_metadata_read=True,
        exact_text_read=True,
        atomic_rename_request=True,
        atomic_move_request=True,
        create_text=True,
        change_feed=False,
        permanent_delete=True,
    )

    def get_metadata(self, object_id: str) -> BackendResult[ObjectMetadata]:
        return BackendResult.failure(BackendOutcome.NOT_FOUND)

    def read_text(self, object_id: str) -> BackendResult[TextObject]:
        return BackendResult.failure(BackendOutcome.NOT_FOUND)

    def replace_text(
        self,
        object_id: str,
        text: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        return BackendResult.failure(BackendOutcome.NOT_FOUND)

    def rename(
        self,
        object_id: str,
        new_name: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        return BackendResult.failure(BackendOutcome.NOT_FOUND)

    def move(
        self,
        object_id: str,
        new_parent_id: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        return BackendResult.failure(BackendOutcome.NOT_FOUND)

    def delete(
        self,
        object_id: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        return BackendResult.failure(BackendOutcome.NOT_FOUND)

    def create_folder(
        self,
        parent_id: str,
        name: str,
    ) -> BackendResult[CreatedObject]:
        return BackendResult.failure(BackendOutcome.PERMISSION_DENIED)

    def create_text(
        self,
        parent_id: str,
        name: str,
        text: str,
    ) -> BackendResult[CreatedObject]:
        return BackendResult.failure(BackendOutcome.PERMISSION_DENIED)

    def list_children(
        self,
        parent_id: str,
    ) -> BackendResult[Sequence[ObjectMetadata]]:
        return BackendResult.success(())


def test_drive_backend_is_runtime_checkable_structural_contract() -> None:
    backend = ContractBackend()
    assert isinstance(backend, DriveBackend)


def test_exact_object_operations_are_first_class_contract_methods() -> None:
    required = {
        "get_metadata",
        "read_text",
        "replace_text",
        "rename",
        "move",
        "create_folder",
        "create_text",
        "delete",
        "list_children",
    }
    assert required <= set(DriveBackend.__dict__)


def test_list_children_is_explicitly_maintenance_only() -> None:
    doc = DriveBackend.list_children.__doc__
    assert doc is not None
    assert "Maintenance/discovery" in doc
    assert "known state lookup" in doc


def test_backend_outcomes_cover_required_normalized_failures() -> None:
    assert {item.value for item in BackendOutcome} == {
        "SUCCESS",
        "NOT_FOUND",
        "PERMISSION_DENIED",
        "CONFLICT",
        "TRANSIENT_ERROR",
        "AMBIGUOUS",
    }


@pytest.mark.parametrize(
    "outcome",
    [
        BackendOutcome.NOT_FOUND,
        BackendOutcome.PERMISSION_DENIED,
        BackendOutcome.CONFLICT,
        BackendOutcome.TRANSIENT_ERROR,
        BackendOutcome.AMBIGUOUS,
    ],
)
def test_failure_results_carry_no_success_value(outcome: BackendOutcome) -> None:
    result: BackendResult[str] = BackendResult.failure(
        outcome,
        message="normalized",
        provider_code="provider-code",
    )
    assert not result.ok
    assert result.value is None
    assert result.message == "normalized"
    assert result.provider_code == "provider-code"


def test_ambiguous_outcome_is_distinguishable_from_ordinary_failure() -> None:
    ambiguous: BackendResult[str] = BackendResult.failure(BackendOutcome.AMBIGUOUS)
    transient: BackendResult[str] = BackendResult.failure(BackendOutcome.TRANSIENT_ERROR)
    assert ambiguous.ambiguous
    assert not transient.ambiguous


def test_success_requires_value_and_failure_forbids_value() -> None:
    metadata = ObjectMetadata(
        object_id="stable-id",
        name="FETCH_BALL_READY",
        parent_ids=("playground-id",),
        is_folder=False,
        version_token="v1",
    )
    result = BackendResult.success(metadata)
    assert result.ok
    assert result.value == metadata

    with pytest.raises(ValueError):
        BackendResult(BackendOutcome.SUCCESS)

    with pytest.raises(ValueError):
        BackendResult(BackendOutcome.NOT_FOUND, value=metadata)


def test_capabilities_make_provider_differences_explicit() -> None:
    caps = ContractBackend.capabilities
    assert caps.stable_object_ids
    assert caps.exact_metadata_read
    assert caps.exact_text_read
    assert caps.maintenance_listing
    assert caps.permanent_delete
    assert not caps.change_feed


def test_metadata_keeps_stable_id_separate_from_mutable_name() -> None:
    metadata = ObjectMetadata(
        object_id="stable-id",
        name="FETCH_BALL_CHEW",
        parent_ids=("playground-id",),
        is_folder=False,
        version_token="v7",
        size_bytes=123,
        modified_epoch_s=1_700_000_000,
    )
    assert metadata.object_id == "stable-id"
    assert metadata.name == "FETCH_BALL_CHEW"


def test_mutation_receipt_reports_requested_effect_without_claiming_confirmation() -> None:
    receipt = MutationReceipt(
        object_id="stable-id",
        requested_name="FETCH_BALL_TOSS",
        version_token="provider-v2",
    )
    assert receipt.object_id == "stable-id"
    assert receipt.requested_name == "FETCH_BALL_TOSS"
