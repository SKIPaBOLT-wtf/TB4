from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tb4.drive.bootstrap import BootstrapConflict, BootstrapError, bootstrap_tree
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.drive.park_map import GLOBAL_REFERENCES


ROOT = Path(__file__).resolve().parents[2]


def _names(backend: InMemoryDriveBackend, parent_id: str) -> list[str]:
    result = backend.list_children(parent_id)
    assert result.ok and result.value is not None
    return [item.name for item in result.value]


def test_fresh_root_bootstrap_builds_one_static_canonical_tree() -> None:
    backend = InMemoryDriveBackend()
    report = bootstrap_tree(backend, root_id=backend.root_id)

    assert report.root_id == backend.root_id
    assert set(report.park_map.entries) == GLOBAL_REFERENCES
    assert report.park_map.devices == {}

    root_names = set(_names(backend, backend.root_id))
    assert {
        "START_HERE",
        "PARK_MAP",
        "GENESIS",
        "SETTINGS",
        "DOG_HOUSE",
        "BALL_PARK",
        "STRAY_YARD",
        "DOG_POUND",
    } <= root_names

    dog_house = report.park_map.lookup("DOG_HOUSE")
    assert set(_names(backend, dog_house)) == {
        "DOG_TAG",
        "DOG_PULSE",
        "DOG_SNOOZE",
        "DOG_SHIT_CLEAN",
    }

    genesis = report.park_map.lookup("GENESIS")
    assert _names(backend, genesis) == ["GENESIS_INFO"]

    map_body = backend.read_text(report.park_map.lookup("PARK_MAP"))
    assert map_body.ok and map_body.value is not None
    assert json.loads(map_body.value.text) == report.park_map.to_dict()


def test_interrupted_safe_bootstrap_resumes_without_duplicate_children() -> None:
    backend = InMemoryDriveBackend()

    dog_house = backend.create_folder(backend.root_id, "DOG_HOUSE")
    assert dog_house.ok and dog_house.value is not None
    pulse = backend.create_text(
        dog_house.value.metadata.object_id,
        "DOG_PULSE",
        "{}\n",
    )
    assert pulse.ok

    report = bootstrap_tree(backend, root_id=backend.root_id)
    assert report.park_map.lookup("DOG_HOUSE") == dog_house.value.metadata.object_id
    assert _names(backend, backend.root_id).count("DOG_HOUSE") == 1
    assert _names(backend, dog_house.value.metadata.object_id).count("DOG_PULSE") == 1


def test_second_bootstrap_creates_no_duplicate_objects_and_no_redundant_map_write() -> None:
    backend = InMemoryDriveBackend()
    first = bootstrap_tree(backend, root_id=backend.root_id)
    first_ids = dict(first.park_map.entries)

    backend.reset_operation_counts()
    second = bootstrap_tree(backend, root_id=backend.root_id)

    assert second.park_map.entries == first_ids
    assert second.created_count == 0
    assert backend.operation_counts.get("create_folder", 0) == 0
    assert backend.operation_counts.get("create_text", 0) == 0
    assert backend.operation_counts.get("replace_text", 0) == 0


def test_missing_explicit_root_is_rejected_before_any_creation() -> None:
    backend = InMemoryDriveBackend()
    backend.reset_operation_counts()

    with pytest.raises(BootstrapError, match="explicit existing root_id"):
        bootstrap_tree(backend, root_id=None)

    assert backend.operation_counts.get("create_folder", 0) == 0
    assert backend.operation_counts.get("create_text", 0) == 0


def test_unreachable_or_nonfolder_root_is_rejected_without_new_root() -> None:
    backend = InMemoryDriveBackend()

    with pytest.raises(BootstrapError, match="not reachable"):
        bootstrap_tree(backend, root_id="missing-root")

    file_result = backend.create_text(backend.root_id, "NOT_A_ROOT", "{}")
    assert file_result.ok and file_result.value is not None
    backend.reset_operation_counts()
    with pytest.raises(BootstrapError, match="does not identify a folder"):
        bootstrap_tree(backend, root_id=file_result.value.metadata.object_id)
    assert backend.operation_counts.get("create_folder", 0) == 0


def test_duplicate_canonical_child_fails_closed() -> None:
    backend = InMemoryDriveBackend()
    assert backend.create_folder(backend.root_id, "DOG_HOUSE").ok
    assert backend.create_folder(backend.root_id, "DOG_HOUSE").ok

    with pytest.raises(BootstrapConflict, match="ambiguous child"):
        bootstrap_tree(backend, root_id=backend.root_id)


def test_ambiguous_create_is_reconciled_by_exact_name_once() -> None:
    backend = InMemoryDriveBackend()
    backend.inject_outcome("create_folder", outcome=__import__(
        "tb4.drive.errors", fromlist=["BackendOutcome"]
    ).BackendOutcome.AMBIGUOUS)

    report = bootstrap_tree(backend, root_id=backend.root_id)
    assert report.park_map.lookup("GENESIS")
    assert len(_names(backend, backend.root_id)) == len(set(_names(backend, backend.root_id)))


def test_bootstrap_does_not_invent_watchdog_identity() -> None:
    backend = InMemoryDriveBackend()
    report = bootstrap_tree(backend, root_id=backend.root_id)
    dog_tag = backend.read_text(report.park_map.lookup("DOG_HOUSE.DOG_TAG"))
    assert dog_tag.ok and dog_tag.value is not None
    assert dog_tag.value.text == "{}\n"


def test_genesis_records_public_protocol_metadata_only() -> None:
    backend = InMemoryDriveBackend()
    report = bootstrap_tree(backend, root_id=backend.root_id)
    genesis_id = report.park_map.lookup("GENESIS")
    children = backend.list_children(genesis_id)
    assert children.ok and children.value is not None
    info_id = next(item.object_id for item in children.value if item.name == "GENESIS_INFO")
    info = backend.read_text(info_id)
    assert info.ok and info.value is not None
    body = json.loads(info.value.text)
    assert body == {
        "protocol_major": 1,
        "root_repair_policy": "never_auto_recreate",
        "schema_version": 1,
        "tree_blueprint": "protocol/tree-blueprint.yaml",
    }


def test_demo_cli_requires_explicit_root_and_can_bootstrap_memory_backend() -> None:
    missing = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "bootstrap_drive.py"), "--demo-memory"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert missing.returncode != 0

    success = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "bootstrap_drive.py"),
            "--demo-memory",
            "--root-id",
            "mem-000001",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert success.returncode == 0, success.stdout + success.stderr
    body = json.loads(success.stdout)
    assert body["root_id"] == "mem-000001"
