from __future__ import annotations

import json
from dataclasses import dataclass

from tb4.core.retry import RetryPolicy
from tb4.drive.delete_keeper import DeleteKeeper, DeleteOutcome
from tb4.drive.errors import BackendOutcome
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.watchdog.retention import (
    BoneyardKeeper,
    RetentionPolicy,
    TerminalSummary,
)


@dataclass
class FakeClock:
    epoch_value: int = 1_000
    monotonic_value: float = 100.0
    safe: bool = True

    def epoch(self):
        return self.epoch_value

    def monotonic(self):
        return self.monotonic_value

    def sleep(self, seconds):
        self.monotonic_value += seconds


def make_keeper(*, now=1000, safe=True, boneyard_s=100, toy_s=100, max_deletes=256):
    backend = InMemoryDriveBackend()
    boneyard = backend.create_folder(backend.root_id, "BONEYARD")
    toy_box = backend.create_folder(backend.root_id, "TOY_BOX")
    assert boneyard.ok and boneyard.value
    assert toy_box.ok and toy_box.value

    clock = FakeClock(now, 100.0, safe)
    policy = RetryPolicy((0.01, 0.02, 0.04), 3)
    delete_keeper = DeleteKeeper(backend, policy, clock.monotonic, clock.sleep)
    keeper = BoneyardKeeper(
        backend=backend,
        delete_keeper=delete_keeper,
        boneyard_folder_id=boneyard.value.metadata.object_id,
        toy_box_folder_id=toy_box.value.metadata.object_id,
        policy=RetentionPolicy(boneyard_s, toy_s, max_deletes),
        epoch_now=clock.epoch,
        clock_safe=lambda: clock.safe,
    )
    backend.reset_operation_counts()
    return backend, clock, keeper, boneyard.value.metadata.object_id, toy_box.value.metadata.object_id


def summary(operation_id: str, *, finished_at: int, state="DONE", artifacts=()):
    return TerminalSummary(
        device_id="target-a",
        operation_id=operation_id,
        generation=1,
        terminal_state=state,
        finished_at=finished_at,
        reason_code="EXIT_ZERO" if state == "DONE" else "TEST_REASON",
        exit_code=0 if state == "DONE" else 1,
        result_artifact_ids=tuple(artifacts),
    )


def create_artifact(backend, toy_box_id, *, expires_at, created_at=100, token="a"):
    content = backend.create_text(
        toy_box_id,
        f"result-content-{created_at}-{token}",
        '{"stdout":"big result","stderr":""}',
    )
    descriptor = backend.create_text(
        toy_box_id,
        f"result-descriptor-{created_at}-{token}",
        "{}",
    )
    assert content.ok and content.value and descriptor.ok and descriptor.value
    descriptor_id = descriptor.value.metadata.object_id
    body = {
        "schema_version": 1,
        "protocol_major": 1,
        "artifact_id": descriptor_id,
        "kind": "RESULT_TEXT",
        "content_object_id": content.value.metadata.object_id,
        "size_bytes": len('{"stdout":"big result","stderr":""}'.encode()),
        "sha256": "a" * 64,
        "interpreter_hint": None,
        "safe_suffix": ".json",
        "created_at": created_at,
        "expires_at": expires_at,
        "complete": True,
    }
    write = backend.replace_text(
        descriptor_id,
        json.dumps(body, sort_keys=True, separators=(",", ":")),
        expected_version_token=descriptor.value.metadata.version_token,
    )
    assert write.ok
    return descriptor_id, content.value.metadata.object_id


def test_terminal_summary_name_and_body_are_idempotent():
    backend, clock, keeper, _, _ = make_keeper(now=500)
    terminal = summary("job-alpha", finished_at=450)

    first = keeper.record_terminal_summary(terminal)
    clock.epoch_value = 510
    second = keeper.record_terminal_summary(terminal)

    assert first.object_id == second.object_id
    assert first.name == second.name
    assert first.name.startswith("BALL_450_1_")
    children = backend.list_children(keeper.boneyard_folder_id)
    assert children.ok and len(children.value) == 1


def test_old_boneyard_record_is_deleted_and_young_record_is_kept():
    backend, _, keeper, _, _ = make_keeper(now=1000, boneyard_s=100)
    old = keeper.record_terminal_summary(summary("job-old", finished_at=800))
    young = keeper.record_terminal_summary(summary("job-young", finished_at=950))

    report = keeper.sweep()

    assert old.object_id in report.deleted_ids
    assert backend.get_metadata(old.object_id).outcome is BackendOutcome.NOT_FOUND
    assert backend.get_metadata(young.object_id).ok
    assert report.deleted == 1


def test_boneyard_boundary_expiry_is_deleted():
    backend, _, keeper, _, _ = make_keeper(now=1000, boneyard_s=100)
    boundary = keeper.record_terminal_summary(summary("job-boundary", finished_at=900))

    report = keeper.sweep()

    assert boundary.object_id in report.deleted_ids
    assert backend.get_metadata(boundary.object_id).outcome is BackendOutcome.NOT_FOUND


def test_expired_live_referenced_artifact_is_preserved():
    backend, _, keeper, _, toy_box = make_keeper(now=1000, toy_s=100)
    descriptor_id, content_id = create_artifact(
        backend, toy_box, created_at=100, expires_at=200, token="live"
    )

    report = keeper.sweep(protected_artifact_ids={descriptor_id})

    assert backend.get_metadata(descriptor_id).ok
    assert backend.get_metadata(content_id).ok
    assert descriptor_id not in report.deleted_ids
    assert content_id not in report.deleted_ids


def test_unexpired_boneyard_reference_protects_expired_artifact():
    backend, _, keeper, _, toy_box = make_keeper(now=1000, boneyard_s=500)
    descriptor_id, content_id = create_artifact(
        backend, toy_box, created_at=100, expires_at=200, token="history"
    )
    keeper.record_terminal_summary(
        summary("job-history", finished_at=900, artifacts=(descriptor_id,))
    )

    report = keeper.sweep()

    assert backend.get_metadata(descriptor_id).ok
    assert backend.get_metadata(content_id).ok
    assert descriptor_id not in report.deleted_ids


def test_expired_unreferenced_descriptor_and_content_are_deleted():
    backend, _, keeper, _, toy_box = make_keeper(now=1000)
    descriptor_id, content_id = create_artifact(
        backend, toy_box, created_at=100, expires_at=200, token="old"
    )

    report = keeper.sweep()

    assert backend.get_metadata(descriptor_id).outcome is BackendOutcome.NOT_FOUND
    assert backend.get_metadata(content_id).outcome is BackendOutcome.NOT_FOUND
    assert descriptor_id in report.deleted_ids
    assert content_id in report.deleted_ids


def test_old_known_orphan_content_is_deleted_but_unknown_object_is_preserved():
    backend, _, keeper, _, toy_box = make_keeper(now=1000, toy_s=100)
    orphan = backend.create_text(toy_box, "result-content-100-orphan", "orphan")
    unknown = backend.create_text(toy_box, "somebody-elses-note", "keep me")
    assert orphan.ok and orphan.value and unknown.ok and unknown.value

    report = keeper.sweep()

    assert backend.get_metadata(orphan.value.metadata.object_id).outcome is BackendOutcome.NOT_FOUND
    assert backend.get_metadata(unknown.value.metadata.object_id).ok
    assert unknown.value.metadata.object_id not in report.deleted_ids


def test_delete_failure_is_isolated_and_other_history_is_still_cleaned():
    backend, _, keeper, _, _ = make_keeper(now=1000, boneyard_s=100)
    first = keeper.record_terminal_summary(summary("job-one", finished_at=800))
    second = keeper.record_terminal_summary(summary("job-two", finished_at=800))
    backend.inject_outcome("delete", BackendOutcome.PERMISSION_DENIED, times=1)

    report = keeper.sweep()

    assert report.failures == 1
    assert report.deleted == 1
    states = {
        first.object_id: backend.get_metadata(first.object_id).outcome,
        second.object_id: backend.get_metadata(second.object_id).outcome,
    }
    assert list(states.values()).count(BackendOutcome.NOT_FOUND) == 1


def test_unsafe_clock_blocks_entire_sweep():
    backend, clock, keeper, _, _ = make_keeper(now=10_000, safe=False, boneyard_s=10)
    old = keeper.record_terminal_summary(summary("job-old", finished_at=100))

    report = keeper.sweep()

    assert report.clock_blocked is True
    assert report.deleted == 0
    assert backend.get_metadata(old.object_id).ok


def test_delete_limit_bounds_damage_even_with_many_old_records():
    backend, _, keeper, _, _ = make_keeper(
        now=1000, boneyard_s=10, max_deletes=2
    )
    for index in range(5):
        keeper.record_terminal_summary(
            summary(f"job-{index}", finished_at=100)
        )

    report = keeper.sweep()

    assert report.deleted == 2
    assert report.delete_limit_reached is True


def test_delete_keeper_rejects_file_outside_explicit_retention_roots():
    backend, clock, keeper, _, _ = make_keeper()
    active = backend.create_text(backend.root_id, "FETCH_BALL_READY", "{}")
    assert active.ok and active.value

    result = keeper.delete_keeper.delete_verified(
        object_id=active.value.metadata.object_id,
        allowed_parent_ids=(keeper.boneyard_folder_id, keeper.toy_box_folder_id),
    )

    assert result.outcome is DeleteOutcome.SCOPE_CONFLICT
    assert backend.get_metadata(active.value.metadata.object_id).ok


def test_ambiguous_delete_is_reconciled_by_exact_object_id():
    backend, _, keeper, _, _ = make_keeper(now=1000, boneyard_s=10)
    old = keeper.record_terminal_summary(summary("job-ambiguous", finished_at=100))
    backend.inject_outcome("delete", BackendOutcome.AMBIGUOUS)

    report = keeper.sweep()

    assert old.object_id in report.deleted_ids
    assert backend.get_metadata(old.object_id).outcome is BackendOutcome.NOT_FOUND
