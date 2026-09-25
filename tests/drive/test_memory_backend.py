from __future__ import annotations

from tb4.drive.backend import DriveBackend
from tb4.drive.errors import BackendOutcome
from tb4.drive.memory_backend import InMemoryDriveBackend


def _file(backend: InMemoryDriveBackend, name: str = "FETCH_BALL_READY") -> str:
    result = backend.create_text(backend.root_id, name, "body")
    assert result.ok
    assert result.value is not None
    return result.value.metadata.object_id


def test_memory_backend_implements_drive_contract() -> None:
    backend = InMemoryDriveBackend()
    assert isinstance(backend, DriveBackend)
    assert backend.capabilities.stable_object_ids
    assert backend.capabilities.exact_metadata_read


def test_stable_id_survives_rename_and_move() -> None:
    backend = InMemoryDriveBackend()
    object_id = _file(backend)
    folder = backend.create_folder(backend.root_id, "PLAYGROUND")
    assert folder.ok and folder.value is not None

    renamed = backend.rename(object_id, "FETCH_BALL_TOSS")
    assert renamed.ok
    moved = backend.move(object_id, folder.value.metadata.object_id)
    assert moved.ok

    metadata = backend.get_metadata(object_id)
    assert metadata.ok and metadata.value is not None
    assert metadata.value.object_id == object_id
    assert metadata.value.name == "FETCH_BALL_TOSS"
    assert metadata.value.parent_ids == (folder.value.metadata.object_id,)


def test_exact_body_read_and_replace_preserve_id() -> None:
    backend = InMemoryDriveBackend()
    object_id = _file(backend)

    before = backend.read_text(object_id)
    assert before.ok and before.value is not None
    token = before.value.metadata.version_token

    replaced = backend.replace_text(
        object_id,
        "new body",
        expected_version_token=token,
    )
    assert replaced.ok

    after = backend.read_text(object_id)
    assert after.ok and after.value is not None
    assert after.value.metadata.object_id == object_id
    assert after.value.text == "new body"
    assert after.value.metadata.version_token != token


def test_version_mismatch_is_explicit_conflict_and_does_not_apply() -> None:
    backend = InMemoryDriveBackend()
    object_id = _file(backend)

    result = backend.rename(
        object_id,
        "FETCH_BALL_TOSS",
        expected_version_token="v999",
    )
    assert result.outcome is BackendOutcome.CONFLICT

    metadata = backend.get_metadata(object_id)
    assert metadata.ok and metadata.value is not None
    assert metadata.value.name == "FETCH_BALL_READY"


def test_delayed_metadata_visibility_is_deterministic() -> None:
    backend = InMemoryDriveBackend()
    object_id = _file(backend)

    backend.delay_next_mutation_visibility(reads=2)
    assert backend.rename(object_id, "FETCH_BALL_TOSS").ok

    first = backend.get_metadata(object_id)
    second = backend.get_metadata(object_id)
    third = backend.get_metadata(object_id)
    assert first.value is not None and first.value.name == "FETCH_BALL_READY"
    assert second.value is not None and second.value.name == "FETCH_BALL_READY"
    assert third.value is not None and third.value.name == "FETCH_BALL_TOSS"


def test_delayed_body_visibility_is_deterministic() -> None:
    backend = InMemoryDriveBackend()
    object_id = _file(backend)

    backend.delay_next_mutation_visibility(reads=1)
    assert backend.replace_text(object_id, "new body").ok

    first = backend.read_text(object_id)
    second = backend.read_text(object_id)
    assert first.value is not None and first.value.text == "body"
    assert second.value is not None and second.value.text == "new body"


def test_ambiguous_rename_can_apply_but_returns_no_false_success() -> None:
    backend = InMemoryDriveBackend()
    object_id = _file(backend)
    backend.inject_outcome("rename", BackendOutcome.AMBIGUOUS)

    result = backend.rename(object_id, "FETCH_BALL_TOSS")
    assert result.outcome is BackendOutcome.AMBIGUOUS
    assert result.value is None

    observed = backend.get_metadata(object_id)
    assert observed.ok and observed.value is not None
    assert observed.value.name == "FETCH_BALL_TOSS"


def test_transient_rename_failure_does_not_apply_mutation() -> None:
    backend = InMemoryDriveBackend()
    object_id = _file(backend)
    backend.inject_outcome("rename", BackendOutcome.TRANSIENT_ERROR)

    result = backend.rename(object_id, "FETCH_BALL_TOSS")
    assert result.outcome is BackendOutcome.TRANSIENT_ERROR

    observed = backend.get_metadata(object_id)
    assert observed.ok and observed.value is not None
    assert observed.value.name == "FETCH_BALL_READY"


def test_permission_and_not_found_are_normalized() -> None:
    backend = InMemoryDriveBackend()
    backend.inject_outcome("get_metadata", BackendOutcome.PERMISSION_DENIED)
    denied = backend.get_metadata("anything")
    assert denied.outcome is BackendOutcome.PERMISSION_DENIED

    missing = backend.get_metadata("missing-id")
    assert missing.outcome is BackendOutcome.NOT_FOUND


def test_maintenance_listing_returns_children_without_path_identity() -> None:
    backend = InMemoryDriveBackend()
    first = _file(backend, "A")
    second = _file(backend, "B")

    result = backend.list_children(backend.root_id)
    assert result.ok and result.value is not None
    ids = {item.object_id for item in result.value}
    assert {first, second} <= ids


def test_operation_counters_are_explicit_and_resettable() -> None:
    backend = InMemoryDriveBackend()
    object_id = _file(backend)
    backend.get_metadata(object_id)
    backend.get_metadata(object_id)
    backend.read_text(object_id)
    backend.list_children(backend.root_id)

    counts = backend.operation_counts
    assert counts["create_text"] == 1
    assert counts["get_metadata"] == 2
    assert counts["read_text"] == 1
    assert counts["list_children"] == 1

    backend.reset_operation_counts()
    assert backend.operation_counts == {}


def test_failure_injection_is_exact_count_not_random() -> None:
    backend = InMemoryDriveBackend()
    object_id = _file(backend)
    backend.inject_outcome("get_metadata", BackendOutcome.TRANSIENT_ERROR, times=2)

    assert backend.get_metadata(object_id).outcome is BackendOutcome.TRANSIENT_ERROR
    assert backend.get_metadata(object_id).outcome is BackendOutcome.TRANSIENT_ERROR
    assert backend.get_metadata(object_id).outcome is BackendOutcome.SUCCESS


def test_ambiguous_create_may_create_object_and_requires_reconciliation() -> None:
    backend = InMemoryDriveBackend()
    backend.inject_outcome("create_text", BackendOutcome.AMBIGUOUS)

    result = backend.create_text(backend.root_id, "MAYBE_CREATED", "body")
    assert result.outcome is BackendOutcome.AMBIGUOUS

    listed = backend.list_children(backend.root_id)
    assert listed.ok and listed.value is not None
    assert any(item.name == "MAYBE_CREATED" for item in listed.value)
