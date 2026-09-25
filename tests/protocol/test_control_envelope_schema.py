from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "protocol" / "schemas" / "control-envelope.schema.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _valid() -> dict:
    return {
        "schema_version": 1,
        "protocol_major": 1,
        "protocol_minor": 0,
        "generation": 7,
        "operation_id": "job-0007",
        "given_at": 1790350000,
        "expires_at": 1790350120,
        "started_at": 0,
        "finished_at": 0,
        "run_limit_s": 300,
        "payload_sha256": "a" * 64,
        "result_sha256": None,
        "artifact_refs": [],
    }


def test_schema_itself_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(_schema())


def test_valid_common_envelope() -> None:
    Draft202012Validator(_schema()).validate(_valid())


def test_generation_is_required() -> None:
    body = _valid()
    del body["generation"]
    with pytest.raises(ValidationError):
        Draft202012Validator(_schema()).validate(body)


def test_invalid_hash_is_rejected() -> None:
    body = _valid()
    body["payload_sha256"] = "not-a-sha"
    with pytest.raises(ValidationError):
        Draft202012Validator(_schema()).validate(body)


def test_lifecycle_state_is_forbidden_in_body() -> None:
    body = _valid()
    body["state"] = "CHEW"
    with pytest.raises(ValidationError):
        Draft202012Validator(_schema()).validate(body)


def test_artifact_reference_is_bounded_and_hashed() -> None:
    body = _valid()
    body["artifact_refs"] = [
        {
            "artifact_id": "drive-object-1",
            "kind": "SCRIPT",
            "size_bytes": 1234,
            "sha256": "b" * 64,
        }
    ]
    Draft202012Validator(_schema()).validate(body)


def test_operation_id_has_restricted_characters() -> None:
    body = _valid()
    body["operation_id"] = "job id with spaces"
    with pytest.raises(ValidationError):
        Draft202012Validator(_schema()).validate(body)


def test_run_limit_has_hard_protocol_ceiling() -> None:
    body = _valid()
    body["run_limit_s"] = 86401
    with pytest.raises(ValidationError):
        Draft202012Validator(_schema()).validate(body)
