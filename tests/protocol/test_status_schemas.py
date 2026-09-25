from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "protocol" / "schemas"
EXAMPLE_DIR = ROOT / "protocol" / "examples" / "status"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(name: str) -> Draft202012Validator:
    schema = _load(SCHEMA_DIR / name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.mark.parametrize(
    ("schema_name", "fixture_name"),
    [
        ("dog-tag.schema.json", "dog-tag.json"),
        ("dog-pulse.schema.json", "dog-pulse-idle.json"),
        ("dog-pulse.schema.json", "dog-pulse-busy.json"),
        ("dog-sniff.schema.json", "dog-sniff-online.json"),
        ("dog-sniff.schema.json", "dog-sniff-offline.json"),
        ("dog-sniff.schema.json", "dog-sniff-unknown.json"),
        ("target-fault.schema.json", "target-fault-clear.json"),
        ("target-fault.schema.json", "target-fault-tangled.json"),
    ],
)
def test_status_fixtures_validate(schema_name: str, fixture_name: str) -> None:
    _validator(schema_name).validate(_load(EXAMPLE_DIR / fixture_name))


def test_dog_tag_capabilities_do_not_encode_reachability() -> None:
    body = deepcopy(_load(EXAMPLE_DIR / "dog-tag.json"))
    body["online"] = True
    with pytest.raises(ValidationError):
        _validator("dog-tag.schema.json").validate(body)

    body = deepcopy(_load(EXAMPLE_DIR / "dog-tag.json"))
    body["ip_address"] = "192.0.2.1"
    with pytest.raises(ValidationError):
        _validator("dog-tag.schema.json").validate(body)


def test_dog_tag_rejects_secret_like_fields() -> None:
    for field in ("password", "token", "credentials", "ssh_private_key"):
        body = deepcopy(_load(EXAMPLE_DIR / "dog-tag.json"))
        body[field] = "secret"
        with pytest.raises(ValidationError):
            _validator("dog-tag.schema.json").validate(body)


def test_dog_pulse_sequence_and_time_types_are_strict() -> None:
    body = deepcopy(_load(EXAMPLE_DIR / "dog-pulse-idle.json"))
    body["sequence"] = -1
    with pytest.raises(ValidationError):
        _validator("dog-pulse.schema.json").validate(body)

    body = deepcopy(_load(EXAMPLE_DIR / "dog-pulse-idle.json"))
    body["emitted_at"] = "now"
    with pytest.raises(ValidationError):
        _validator("dog-pulse.schema.json").validate(body)


def test_dog_pulse_claim_fields_are_paired() -> None:
    body = deepcopy(_load(EXAMPLE_DIR / "dog-pulse-busy.json"))
    body["claimed_operation_id"] = None
    with pytest.raises(ValidationError):
        _validator("dog-pulse.schema.json").validate(body)

    body = deepcopy(_load(EXAMPLE_DIR / "dog-pulse-busy.json"))
    body["claimed_generation"] = None
    with pytest.raises(ValidationError):
        _validator("dog-pulse.schema.json").validate(body)


def test_dog_sniff_observations_are_bounded() -> None:
    body = deepcopy(_load(EXAMPLE_DIR / "dog-sniff-online.json"))
    body["addresses"] = [f"192.0.2.{i}" for i in range(9)]
    with pytest.raises(ValidationError):
        _validator("dog-sniff.schema.json").validate(body)


def test_no_observation_can_be_unknown_without_becoming_offline() -> None:
    body = _load(EXAMPLE_DIR / "dog-sniff-unknown.json")
    assert body["reachability"] == "UNKNOWN"
    assert body["observed_at"] == 0
    _validator("dog-sniff.schema.json").validate(body)


def test_target_fault_description_is_bounded() -> None:
    body = deepcopy(_load(EXAMPLE_DIR / "target-fault-tangled.json"))
    body["description"] = "x" * 513
    with pytest.raises(ValidationError):
        _validator("target-fault.schema.json").validate(body)


def test_target_fault_body_does_not_duplicate_leash_filename_state() -> None:
    body = deepcopy(_load(EXAMPLE_DIR / "target-fault-tangled.json"))
    body["leash_state"] = "TANGLED"
    with pytest.raises(ValidationError):
        _validator("target-fault.schema.json").validate(body)
