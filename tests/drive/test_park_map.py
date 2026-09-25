from __future__ import annotations

import json
from pathlib import Path

import pytest

from tb4.core.models import DeviceId
from tb4.core.schemas import load_schema_store
from tb4.drive.park_map import (
    DEVICE_REFERENCE_SUFFIXES,
    DuplicateParkObjectId,
    MissingParkReference,
    ParkMap,
    ParkMapConflict,
    ParkMapError,
    ParkMapVersionError,
    DeviceRegistration,
)


ROOT = Path(__file__).resolve().parents[2]


def _entries(device_id: str = "device-001") -> dict[str, str]:
    entries = {
        "START_HERE": "id-start",
        "PARK_MAP": "id-map",
        "GENESIS": "id-genesis",
        "SETTINGS": "id-settings",
        "DOG_HOUSE": "id-dog-house",
        "DOG_HOUSE.DOG_TAG": "id-watchdog-tag",
        "DOG_HOUSE.DOG_PULSE": "id-watchdog-pulse",
        "DOG_HOUSE.WATCHDOG_MODE": "id-watchdog-mode",
        "DOG_HOUSE.WATCHDOG_FAULT": "id-watchdog-fault",
        "BALL_PARK": "id-ball-park",
        "STRAY_YARD": "id-stray-yard",
        "DOG_POUND": "id-dog-pound",
    }
    for index, suffix in enumerate(sorted(DEVICE_REFERENCE_SUFFIXES), start=1):
        entries[f"DEVICE.{device_id}.{suffix}"] = f"id-device-{index:02d}"
    return entries


def _mapping(device_id: str = "device-001", device_key: str = "target-a") -> dict:
    return {
        "schema_version": 1,
        "protocol_major": 1,
        "map_generation": 4,
        "root_id": "id-root",
        "devices": {
            device_id: {
                "device_key": device_key,
            }
        },
        "entries": _entries(device_id),
    }


def _park_map() -> ParkMap:
    return ParkMap.from_dict(_mapping())


def test_schema_accepts_canonical_map() -> None:
    load_schema_store().validate("park-map.schema.json", _mapping())


def test_round_trip_is_deterministic() -> None:
    mapping = _mapping()
    park_map = ParkMap.from_dict(mapping)
    assert ParkMap.from_dict(park_map.to_dict()) == park_map
    assert park_map.to_dict()["entries"] == dict(sorted(mapping["entries"].items()))


def test_exact_lookup_uses_logical_reference() -> None:
    park_map = _park_map()
    assert park_map.lookup("DOG_HOUSE.DOG_PULSE") == "id-watchdog-pulse"
    assert (
        park_map.lookup_device(DeviceId("device-001"), "PLAYGROUND.FETCH_BALL")
        == _entries()["DEVICE.device-001.PLAYGROUND.FETCH_BALL"]
    )


def test_missing_entry_fails_closed() -> None:
    mapping = _mapping()
    del mapping["entries"]["DEVICE.device-001.PLAYGROUND.FETCH_BALL"]
    with pytest.raises(MissingParkReference):
        ParkMap.from_dict(mapping)


def test_unknown_lookup_does_not_fallback_or_scan() -> None:
    park_map = _park_map()
    with pytest.raises(MissingParkReference):
        park_map.lookup("DEVICE.device-001.PLAYGROUND.MAYBE_BALL")
    with pytest.raises(ParkMapError):
        ParkMap.device_ref("device-001", "PLAYGROUND.MAYBE_BALL")


def test_duplicate_object_id_is_rejected() -> None:
    mapping = _mapping()
    mapping["entries"]["DOG_POUND"] = mapping["entries"]["BALL_PARK"]
    with pytest.raises(DuplicateParkObjectId):
        ParkMap.from_dict(mapping)


def test_root_id_cannot_be_reused_by_entry() -> None:
    mapping = _mapping()
    mapping["entries"]["DOG_POUND"] = mapping["root_id"]
    with pytest.raises(DuplicateParkObjectId):
        ParkMap.from_dict(mapping)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", 2),
        ("protocol_major", 2),
    ],
)
def test_schema_or_protocol_version_mismatch_is_rejected(field: str, value: int) -> None:
    mapping = _mapping()
    mapping[field] = value
    with pytest.raises(ParkMapVersionError):
        ParkMap.from_dict(mapping)


def test_replacing_one_reconstructable_child_updates_only_that_reference() -> None:
    park_map = _park_map()
    ref = "DEVICE.device-001.PLAYGROUND.FETCH_BALL"
    old_id = park_map.lookup(ref)

    updated = park_map.replace_reference(
        ref,
        "id-replacement-fetch-ball",
        expected_old_object_id=old_id,
    )

    assert updated.map_generation == park_map.map_generation + 1
    assert updated.lookup(ref) == "id-replacement-fetch-ball"
    for other_ref, object_id in park_map.entries.items():
        if other_ref != ref:
            assert updated.entries[other_ref] == object_id


def test_replace_requires_expected_old_identity() -> None:
    park_map = _park_map()
    with pytest.raises(ParkMapConflict):
        park_map.replace_reference(
            "DOG_HOUSE.DOG_PULSE",
            "new-pulse-id",
            expected_old_object_id="guessed-old-id",
        )


def test_replace_cannot_adopt_id_owned_by_another_reference() -> None:
    park_map = _park_map()
    with pytest.raises(DuplicateParkObjectId):
        park_map.replace_reference(
            "DOG_HOUSE.DOG_PULSE",
            park_map.lookup("DOG_POUND"),
            expected_old_object_id=park_map.lookup("DOG_HOUSE.DOG_PULSE"),
        )


def test_hostname_like_device_key_is_not_permanent_device_identity() -> None:
    park_map = ParkMap.from_dict(_mapping(device_id="stable-device-17", device_key="initial-hostname"))

    assert park_map.device_key("stable-device-17") == "initial-hostname"
    assert (
        park_map.lookup_device("stable-device-17", "DOG_TAG")
        == _entries("stable-device-17")["DEVICE.stable-device-17.DOG_TAG"]
    )

    serialized = park_map.to_dict()
    serialized["devices"]["stable-device-17"]["device_key"] = "renamed-folder-alias"
    changed_key = ParkMap.from_dict(serialized)

    assert changed_key.lookup_device("stable-device-17", "DOG_TAG") == park_map.lookup_device(
        "stable-device-17", "DOG_TAG"
    )


def test_register_device_requires_complete_exact_reference_set() -> None:
    base = _mapping()
    base["devices"] = {}
    base["entries"] = {
        key: value
        for key, value in base["entries"].items()
        if not key.startswith("DEVICE.")
    }
    park_map = ParkMap.from_dict(base)

    refs = {
        ParkMap.device_ref("device-002", suffix): f"id-new-{index:02d}"
        for index, suffix in enumerate(sorted(DEVICE_REFERENCE_SUFFIXES), start=1)
    }
    registered = park_map.register_device(
        DeviceRegistration(DeviceId("device-002"), "target-b"),
        refs,
    )
    assert registered.map_generation == park_map.map_generation + 1
    assert registered.lookup_device("device-002", "PLAYGROUND.FETCH_BALL").startswith("id-new-")

    incomplete = dict(refs)
    incomplete.pop(ParkMap.device_ref("device-002", "DOG_PULSE"))
    with pytest.raises(ParkMapError):
        park_map.register_device(
            DeviceRegistration(DeviceId("device-002"), "target-b"),
            incomplete,
        )


def test_schema_rejects_unknown_top_level_fields() -> None:
    body = _mapping()
    body["guess_if_missing"] = True
    with pytest.raises(Exception):
        load_schema_store().validate("park-map.schema.json", body)
