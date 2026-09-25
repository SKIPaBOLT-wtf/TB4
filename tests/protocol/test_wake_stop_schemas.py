from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "protocol" / "schemas"
EXAMPLE_ROOT = ROOT / "protocol" / "examples"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(schema_name: str) -> Draft202012Validator:
    common = _load(SCHEMA_DIR / "control-envelope.schema.json")
    schema = _load(SCHEMA_DIR / schema_name)
    registry = Registry().with_resource(common["$id"], Resource.from_contents(common))
    return Draft202012Validator(schema, registry=registry)


def _wake(name: str) -> dict:
    return _load(EXAMPLE_ROOT / "wake-bone" / name)


def _stop(name: str) -> dict:
    return _load(EXAMPLE_ROOT / "stop-ball" / name)


def test_wake_and_stop_schemas_are_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(_load(SCHEMA_DIR / "wake-bone.schema.json"))
    Draft202012Validator.check_schema(_load(SCHEMA_DIR / "stop-ball.schema.json"))


@pytest.mark.parametrize("name", ["toss.json", "done.json", "failed.json"])
def test_wake_fixtures_validate(name: str) -> None:
    _validator("wake-bone.schema.json").validate(_wake(name))


@pytest.mark.parametrize("name", ["requested.json", "acknowledged.json"])
def test_stop_fixtures_validate(name: str) -> None:
    _validator("stop-ball.schema.json").validate(_stop(name))


def test_wake_done_requires_confirmed_fetcher_pulse() -> None:
    body = deepcopy(_wake("done.json"))
    body["pulse_confirmed_at"] = 0
    with pytest.raises(ValidationError):
        _validator("wake-bone.schema.json").validate(body)


def test_wake_failed_requires_reason_and_terminal_integrity() -> None:
    body = deepcopy(_wake("failed.json"))
    body["reason_code"] = None
    with pytest.raises(ValidationError):
        _validator("wake-bone.schema.json").validate(body)

    body = deepcopy(_wake("failed.json"))
    body["result_sha256"] = None
    with pytest.raises(ValidationError):
        _validator("wake-bone.schema.json").validate(body)


def test_structurally_invalid_zero_expiry_is_rejected() -> None:
    body = deepcopy(_wake("toss.json"))
    body["expires_at"] = 0
    with pytest.raises(ValidationError):
        _validator("wake-bone.schema.json").validate(body)


def test_runtime_expiry_remains_a_deadline_guard_responsibility() -> None:
    body = deepcopy(_wake("toss.json"))
    body["given_at"] = 1
    body["expires_at"] = 2
    _validator("wake-bone.schema.json").validate(body)


@pytest.mark.parametrize(
    "field",
    ["ssh_password", "ssh_private_key", "password", "token", "credentials"],
)
def test_wake_body_rejects_credential_fields(field: str) -> None:
    body = deepcopy(_wake("toss.json"))
    body[field] = "secret"
    with pytest.raises(ValidationError):
        _validator("wake-bone.schema.json").validate(body)


def test_stop_ball_requires_exact_fetch_ball_object_and_job_identity() -> None:
    for field in ("fetch_ball_object_id", "job_id", "generation"):
        body = deepcopy(_stop("requested.json"))
        del body[field]
        with pytest.raises(ValidationError):
            _validator("stop-ball.schema.json").validate(body)


def test_stop_ball_generation_is_target_generation() -> None:
    body = _stop("requested.json")
    assert body["generation"] == 11
    assert body["job_id"] == "job-1700000400-e1f2a3b4"


def test_stop_ack_requires_timestamp_and_integrity() -> None:
    body = deepcopy(_stop("acknowledged.json"))
    body["acknowledged_at"] = 0
    with pytest.raises(ValidationError):
        _validator("stop-ball.schema.json").validate(body)

    body = deepcopy(_stop("acknowledged.json"))
    body["result_sha256"] = None
    with pytest.raises(ValidationError):
        _validator("stop-ball.schema.json").validate(body)


def test_lifecycle_state_is_not_duplicated_in_either_body() -> None:
    for schema_name, body in (
        ("wake-bone.schema.json", _wake("toss.json")),
        ("stop-ball.schema.json", _stop("requested.json")),
    ):
        body["state"] = "TOSS"
        with pytest.raises(ValidationError):
            _validator(schema_name).validate(body)
