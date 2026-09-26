from __future__ import annotations

from tb4.drive.bootstrap import bootstrap_tree
from tb4.drive.device_registration import (
    DeviceProfile,
    DeviceRegistrar,
    DeviceRegistrationConflict,
    RegistrationOutcome,
)
from tb4.drive.memory_backend import InMemoryDriveBackend


def profile() -> DeviceProfile:
    return DeviceProfile(
        device_id="device-001",
        device_key="target-a",
        hostname="example-host",
        os_family="LINUX",
        wake_on_lan=True,
        ssh_bootstrap=True,
    )


def test_fresh_device_registration_creates_one_complete_tree() -> None:
    backend = InMemoryDriveBackend()
    base = bootstrap_tree(backend, root_id=backend.root_id).park_map

    report = DeviceRegistrar(backend).register(base, profile())

    assert report.outcome is RegistrationOutcome.CREATED
    assert report.created_count == 12
    assert report.reused_count == 0
    assert report.park_map.device_key("device-001") == "target-a"

    fetch_id = report.park_map.lookup_device("device-001", "PLAYGROUND.FETCH_BALL")
    stop_id = report.park_map.lookup_device("device-001", "PLAYGROUND.STOP_BALL")
    wake_id = report.park_map.lookup_device("device-001", "KENNEL.WAKE_BONE")

    assert backend.get_metadata(fetch_id).value.name == "FETCH_BALL_READY"
    assert backend.get_metadata(stop_id).value.name == "STOP_BALL_READY"
    assert backend.get_metadata(wake_id).value.name == "WAKE_BONE_READY"


def test_interrupted_registration_reuses_existing_objects() -> None:
    backend = InMemoryDriveBackend()
    base = bootstrap_tree(backend, root_id=backend.root_id).park_map
    ball_park = base.lookup("BALL_PARK")

    root = backend.create_folder(ball_park, "target-a")
    assert root.ok and root.value is not None
    dog_tag = backend.create_text(
        root.value.metadata.object_id,
        "DOG_TAG",
        "{}\n",
    )
    assert dog_tag.ok

    # DOG_TAG content from an interrupted pre-profile write is not silently
    # trusted. Remove it to model interruption before body creation rather than
    # a conflicting established identity.
    assert backend.delete(dog_tag.value.metadata.object_id).ok

    report = DeviceRegistrar(backend).register(base, profile())

    assert report.outcome is RegistrationOutcome.RESUMED
    assert report.reused_count >= 1

    children = backend.list_children(ball_park)
    assert children.ok and children.value is not None
    assert [item.name for item in children.value].count("target-a") == 1


def test_second_identical_registration_is_idempotent() -> None:
    backend = InMemoryDriveBackend()
    base = bootstrap_tree(backend, root_id=backend.root_id).park_map
    first = DeviceRegistrar(backend).register(base, profile())

    backend.reset_operation_counts()
    second = DeviceRegistrar(backend).register(first.park_map, profile())

    assert second.outcome is RegistrationOutcome.ALREADY_REGISTERED
    assert second.park_map == first.park_map
    assert backend.operation_counts.get("create_folder", 0) == 0
    assert backend.operation_counts.get("create_text", 0) == 0
    assert backend.operation_counts.get("replace_text", 0) == 0


def test_existing_registration_rejects_identity_or_capability_drift() -> None:
    backend = InMemoryDriveBackend()
    base = bootstrap_tree(backend, root_id=backend.root_id).park_map
    first = DeviceRegistrar(backend).register(base, profile())

    changed = DeviceProfile(
        device_id="device-001",
        device_key="target-a",
        hostname="different-host",
        os_family="LINUX",
        wake_on_lan=True,
        ssh_bootstrap=True,
    )

    try:
        DeviceRegistrar(backend).register(first.park_map, changed)
    except DeviceRegistrationConflict as exc:
        assert "DOG_TAG" in str(exc)
    else:
        raise AssertionError("identity drift must not be silently rewritten")


def test_duplicate_device_folder_fails_closed() -> None:
    backend = InMemoryDriveBackend()
    base = bootstrap_tree(backend, root_id=backend.root_id).park_map
    ball_park = base.lookup("BALL_PARK")
    assert backend.create_folder(ball_park, "target-a").ok
    assert backend.create_folder(ball_park, "target-a").ok

    try:
        DeviceRegistrar(backend).register(base, profile())
    except DeviceRegistrationConflict as exc:
        assert "ambiguous registration object" in str(exc)
    else:
        raise AssertionError("duplicate device roots must fail closed")
