from __future__ import annotations

import copy

import pytest

from tb4.core.schemas import SchemaValidationError, load_schema_store


BASE = {
    "schema_version": 1,
    "protocol_major": 1,
    "artifact_id": "drive-desc-123",
    "kind": "REQUEST_SCRIPT",
    "content_object_id": "drive-content-456",
    "size_bytes": 1234,
    "sha256": "a" * 64,
    "interpreter_hint": "pwsh",
    "safe_suffix": ".ps1",
    "created_at": 1790430000,
    "expires_at": 1790433600,
    "complete": True,
}


def validate(body: dict) -> None:
    load_schema_store().validate("artifact.schema.json", body)


def test_request_script_artifact_fixture_is_valid() -> None:
    validate(BASE)


def test_large_result_artifact_fixture_is_valid() -> None:
    body = copy.deepcopy(BASE)
    body.update(
        {
            "kind": "RESULT_TEXT",
            "size_bytes": 524288,
            "interpreter_hint": None,
            "safe_suffix": ".txt",
        }
    )
    validate(body)


def test_binary_result_artifact_fixture_is_valid() -> None:
    body = copy.deepcopy(BASE)
    body.update(
        {
            "kind": "RESULT_BINARY",
            "size_bytes": 10_000_000,
            "interpreter_hint": None,
            "safe_suffix": ".bin",
        }
    )
    validate(body)


def test_hash_must_be_lowercase_sha256() -> None:
    for invalid in ["a" * 63, "A" * 64, "z" * 64, "../hash"]:
        body = copy.deepcopy(BASE)
        body["sha256"] = invalid
        with pytest.raises(SchemaValidationError):
            validate(body)


def test_protocol_schema_has_hard_absolute_size_ceiling() -> None:
    body = copy.deepcopy(BASE)
    body["size_bytes"] = 1_073_741_825
    with pytest.raises(SchemaValidationError):
        validate(body)


def test_incomplete_descriptor_is_not_valid() -> None:
    body = copy.deepcopy(BASE)
    body["complete"] = False
    with pytest.raises(SchemaValidationError):
        validate(body)


@pytest.mark.parametrize(
    "field,value",
    [
        ("path", "../../tmp/evil.ps1"),
        ("local_path", "C:\\Windows\\Temp\\evil.ps1"),
        ("remote_path", "/tmp/evil"),
        ("filename", "../evil.ps1"),
        ("command", "pwsh -enc ..."),
        ("arguments", ["--unsafe"]),
    ],
)
def test_path_and_command_metadata_are_forbidden(field: str, value: object) -> None:
    body = copy.deepcopy(BASE)
    body[field] = value
    with pytest.raises(SchemaValidationError):
        validate(body)


@pytest.mark.parametrize(
    "suffix",
    ["../../evil", ".exe", ".cmd", ".bat", "x.ps1", "/tmp/a.sh", ""],
)
def test_safe_suffix_is_strict_whitelist(suffix: str) -> None:
    body = copy.deepcopy(BASE)
    body["safe_suffix"] = suffix
    with pytest.raises(SchemaValidationError):
        validate(body)


@pytest.mark.parametrize(
    "hint",
    ["pwsh -NoProfile", "/bin/bash", "python3 -c", "cmd.exe", "../pwsh"],
)
def test_interpreter_hint_cannot_be_shell_fragment_or_path(hint: str) -> None:
    body = copy.deepcopy(BASE)
    body["interpreter_hint"] = hint
    with pytest.raises(SchemaValidationError):
        validate(body)


def test_script_suffix_must_match_script_family_whitelist() -> None:
    body = copy.deepcopy(BASE)
    body["safe_suffix"] = ".txt"
    with pytest.raises(SchemaValidationError):
        validate(body)


def test_binary_and_data_result_cannot_request_interpreter() -> None:
    for kind in ["RESULT_BINARY", "RESULT_DATA"]:
        body = copy.deepcopy(BASE)
        body.update(
            {
                "kind": kind,
                "interpreter_hint": "pwsh",
                "safe_suffix": ".bin",
            }
        )
        with pytest.raises(SchemaValidationError):
            validate(body)


def test_artifact_and_content_ids_reject_path_syntax() -> None:
    for field in ["artifact_id", "content_object_id"]:
        body = copy.deepcopy(BASE)
        body[field] = "../not-an-id"
        with pytest.raises(SchemaValidationError):
            validate(body)
