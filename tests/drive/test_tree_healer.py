from __future__ import annotations

import json

from tb4.core.schemas import canonical_json_text
from tb4.drive.bootstrap import bootstrap_tree
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.drive.tree_audit import TreeAuditor, TreeIssueKind
from tb4.drive.tree_healer import RepairOutcome, TreeHealer


def _persist_map(backend: InMemoryDriveBackend, park_map) -> None:
    map_id = park_map.lookup("PARK_MAP")
    meta = backend.get_metadata(map_id)
    assert meta.ok and meta.value is not None
    write = backend.replace_text(
        map_id,
        canonical_json_text(park_map.to_dict()),
        expected_version_token=meta.value.version_token,
    )
    assert write.ok


def _child_names(backend: InMemoryDriveBackend, parent_id: str) -> list[str]:
    listed = backend.list_children(parent_id)
    assert listed.ok and listed.value is not None
    return [item.name for item in listed.value]


def test_fresh_bootstrap_audits_clean() -> None:
    backend = InMemoryDriveBackend()
    report = bootstrap_tree(backend, root_id=backend.root_id)

    audit = TreeAuditor(backend).audit(
        root_id=backend.root_id,
        park_map=report.park_map,
    )

    assert audit.clean
    assert audit.scanned_parent_count >= 2


def test_unknown_control_child_is_quarantined_with_provenance() -> None:
    backend = InMemoryDriveBackend()
    boot = bootstrap_tree(backend, root_id=backend.root_id)
    dog_house = boot.park_map.lookup("DOG_HOUSE")
    mystery = backend.create_text(dog_house, "MYSTERY_STICK", "woof")
    assert mystery.ok and mystery.value is not None

    repaired = TreeHealer(backend).repair(
        root_id=backend.root_id,
        park_map=boot.park_map,
    )

    assert repaired.outcome is RepairOutcome.REPAIRED
    mystery_id = mystery.value.metadata.object_id
    assert mystery_id in repaired.quarantined_ids

    dog_pound = repaired.park_map.lookup("DOG_POUND")
    moved = backend.get_metadata(mystery_id)
    assert moved.ok and moved.value is not None
    assert moved.value.parent_ids == (dog_pound,)

    notes = [
        item
        for item in backend.list_children(dog_pound).value or ()
        if item.name.startswith("QUARANTINE_")
    ]
    assert len(notes) == 1
    note = backend.read_text(notes[0].object_id)
    assert note.ok and note.value is not None
    body = json.loads(note.value.text)
    assert body["object_id"] == mystery_id
    assert body["original_name"] == "MYSTERY_STICK"
    assert body["reason"] == "UNKNOWN_CHILD"


def test_duplicate_canonical_child_preserves_park_map_object() -> None:
    backend = InMemoryDriveBackend()
    boot = bootstrap_tree(backend, root_id=backend.root_id)
    dog_house = boot.park_map.lookup("DOG_HOUSE")
    canonical = boot.park_map.lookup("DOG_HOUSE.DOG_PULSE")
    duplicate = backend.create_text(dog_house, "DOG_PULSE", "{}\n")
    assert duplicate.ok and duplicate.value is not None

    repaired = TreeHealer(backend).repair(
        root_id=backend.root_id,
        park_map=boot.park_map,
    )

    assert repaired.outcome is RepairOutcome.REPAIRED
    assert repaired.park_map.lookup("DOG_HOUSE.DOG_PULSE") == canonical
    assert duplicate.value.metadata.object_id in repaired.quarantined_ids
    canonical_meta = backend.get_metadata(canonical)
    assert canonical_meta.ok and canonical_meta.value is not None
    assert canonical_meta.value.parent_ids == (dog_house,)


def test_wrong_parent_restores_same_canonical_id() -> None:
    backend = InMemoryDriveBackend()
    boot = bootstrap_tree(backend, root_id=backend.root_id)
    pulse = boot.park_map.lookup("DOG_HOUSE.DOG_PULSE")
    dog_pound = boot.park_map.lookup("DOG_POUND")
    moved = backend.move(pulse, dog_pound)
    assert moved.ok

    repaired = TreeHealer(backend).repair(
        root_id=backend.root_id,
        park_map=boot.park_map,
    )

    assert repaired.outcome is RepairOutcome.REPAIRED
    assert repaired.park_map.lookup("DOG_HOUSE.DOG_PULSE") == pulse
    assert "DOG_HOUSE.DOG_PULSE" in repaired.restored_refs
    meta = backend.get_metadata(pulse)
    assert meta.ok and meta.value is not None
    assert meta.value.parent_ids == (boot.park_map.lookup("DOG_HOUSE"),)


def test_missing_index_id_adopts_one_unambiguous_existing_candidate() -> None:
    backend = InMemoryDriveBackend()
    boot = bootstrap_tree(backend, root_id=backend.root_id)
    pulse = boot.park_map.lookup("DOG_HOUSE.DOG_PULSE")

    stale_map = boot.park_map.replace_reference(
        "DOG_HOUSE.DOG_PULSE",
        "missing-pulse-id",
        expected_old_object_id=pulse,
    )
    _persist_map(backend, stale_map)

    repaired = TreeHealer(backend).repair(
        root_id=backend.root_id,
        park_map=stale_map,
    )

    assert repaired.outcome is RepairOutcome.REPAIRED
    assert repaired.park_map.lookup("DOG_HOUSE.DOG_PULSE") == pulse
    assert "DOG_HOUSE.DOG_PULSE" in repaired.adopted_refs


def test_safely_reconstructable_missing_object_gets_new_id() -> None:
    backend = InMemoryDriveBackend()
    boot = bootstrap_tree(backend, root_id=backend.root_id)
    original = boot.park_map.lookup("START_HERE")

    renamed = backend.rename(original, "LOST_START_HERE")
    assert renamed.ok
    stale_map = boot.park_map.replace_reference(
        "START_HERE",
        "missing-start-id",
        expected_old_object_id=original,
    )
    _persist_map(backend, stale_map)

    repaired = TreeHealer(backend).repair(
        root_id=backend.root_id,
        park_map=stale_map,
    )

    assert repaired.outcome is RepairOutcome.REPAIRED
    replacement = repaired.park_map.lookup("START_HERE")
    assert replacement != original
    assert "START_HERE" in repaired.created_refs
    assert _child_names(backend, backend.root_id).count("START_HERE") == 1


def test_invalid_stateful_name_blocks_instead_of_guessing_initial_state() -> None:
    backend = InMemoryDriveBackend()
    boot = bootstrap_tree(backend, root_id=backend.root_id)
    mode = boot.park_map.lookup("DOG_HOUSE.WATCHDOG_MODE")
    assert backend.rename(mode, "DOG_CONFUSED").ok

    repaired = TreeHealer(backend).repair(
        root_id=backend.root_id,
        park_map=boot.park_map,
    )

    assert repaired.outcome is RepairOutcome.BLOCKED
    assert "state cannot be guessed" in (repaired.message or "")
    meta = backend.get_metadata(mode)
    assert meta.ok and meta.value is not None
    assert meta.value.name == "DOG_CONFUSED"


def test_park_map_identity_ambiguity_blocks_repair() -> None:
    backend = InMemoryDriveBackend()
    boot = bootstrap_tree(backend, root_id=backend.root_id)
    real_map_id = boot.park_map.lookup("PARK_MAP")
    broken = boot.park_map.replace_reference(
        "PARK_MAP",
        "missing-map-id",
        expected_old_object_id=real_map_id,
    )

    audit = TreeAuditor(backend).audit(
        root_id=backend.root_id,
        park_map=broken,
    )
    assert any(
        issue.kind is TreeIssueKind.CANONICAL_ID_MISSING
        and issue.logical_ref == "PARK_MAP"
        for issue in audit.issues
    )

    repaired = TreeHealer(backend).repair(
        root_id=backend.root_id,
        park_map=broken,
    )
    assert repaired.outcome is RepairOutcome.BLOCKED
    assert repaired.park_map.lookup("PARK_MAP") == "missing-map-id"


def test_root_mismatch_blocks_without_creating_anything() -> None:
    backend = InMemoryDriveBackend()
    boot = bootstrap_tree(backend, root_id=backend.root_id)
    another_root = backend.create_folder(backend.root_id, "OTHER_ROOT")
    assert another_root.ok and another_root.value is not None

    backend.reset_operation_counts()
    repaired = TreeHealer(backend).repair(
        root_id=another_root.value.metadata.object_id,
        park_map=boot.park_map,
    )

    assert repaired.outcome is RepairOutcome.BLOCKED
    assert backend.operation_counts.get("create_folder", 0) == 0
    assert backend.operation_counts.get("create_text", 0) == 0
