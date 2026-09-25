from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tb4.core.models import (
    ArtifactId,
    DeviceId,
    EpochSeconds,
    Generation,
    ObjectStateRef,
    OperationId,
    ReasonCode,
)
from tb4.core.protocol_names import (
    FetchResultCode,
    LogicalObject,
    Role,
    state_filename,
)


ROOT = Path(__file__).resolve().parents[2]


def _yaml(name: str) -> dict:
    return yaml.safe_load((ROOT / "protocol" / name).read_text(encoding="utf-8"))


def test_role_enum_exactly_matches_canonical_registry() -> None:
    canonical = set(_yaml("objects.yaml")["roles"])
    assert {item.value for item in Role} == canonical


def test_logical_object_enum_exactly_matches_canonical_registry() -> None:
    objects = _yaml("objects.yaml")
    canonical = set(objects["fixed_objects"]) | set(objects["stateful_objects"])
    assert {item.value for item in LogicalObject} == canonical


def test_fetch_result_codes_match_terminal_fetch_ball_states() -> None:
    machine = _yaml("state-machines.yaml")["state_machines"]["FETCH_BALL"]
    terminal = {
        state
        for state, definition in machine["states"].items()
        if definition["terminal"]
    }
    assert {item.value for item in FetchResultCode} == terminal


def test_state_filename_matches_every_canonical_stateful_name() -> None:
    objects = _yaml("objects.yaml")["stateful_objects"]
    machines = _yaml("state-machines.yaml")["state_machines"]

    for object_name, definition in objects.items():
        logical = LogicalObject(object_name)
        for state in machines[object_name]["states"]:
            if "filenames" in definition:
                expected = definition["filenames"][state]
            elif "root_name" in definition:
                expected = f"{definition['root_name']}_{state}"
            else:
                expected = f"{object_name}_{state}"
            assert state_filename(logical, state) == expected


def test_operation_id_round_trip_and_rejects_malformed_values() -> None:
    value = OperationId("job-1700000000-a1b2c3d4")
    assert str(value) == "job-1700000000-a1b2c3d4"
    with pytest.raises(ValueError):
        OperationId("short")
    with pytest.raises(ValueError):
        OperationId("job id with spaces")


def test_device_and_artifact_ids_are_bounded() -> None:
    assert str(DeviceId("target-a")) == "target-a"
    assert str(ArtifactId("toy box/artifact 1")) == "toy box/artifact 1"
    with pytest.raises(ValueError):
        DeviceId("bad device")
    with pytest.raises(ValueError):
        ArtifactId("")


def test_generation_is_nonnegative_immutable_value() -> None:
    generation = Generation(7)
    assert int(generation) == 7
    assert generation.next() == Generation(8)
    with pytest.raises(ValueError):
        Generation(-1)
    with pytest.raises(TypeError):
        Generation(True)  # type: ignore[arg-type]


def test_epoch_seconds_and_reason_codes_follow_schema_shape() -> None:
    assert int(EpochSeconds(0)) == 0
    assert str(ReasonCode("COMMAND_FAILED")) == "COMMAND_FAILED"
    with pytest.raises(ValueError):
        EpochSeconds(-1)
    with pytest.raises(ValueError):
        ReasonCode("not uppercase")


def test_object_state_reference_round_trips_canonical_identity() -> None:
    original = ObjectStateRef(LogicalObject.FETCH_BALL, "chew")
    encoded = original.to_dict()
    assert encoded == {"logical_object": "FETCH_BALL", "state": "CHEW"}
    assert ObjectStateRef.from_dict(encoded) == original
    assert original.filename == "FETCH_BALL_CHEW"


def test_stateful_filename_helper_rejects_fixed_objects() -> None:
    with pytest.raises(ValueError):
        state_filename(LogicalObject.DOG_TAG, "READY")
