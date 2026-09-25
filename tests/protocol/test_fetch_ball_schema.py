from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "protocol" / "schemas"
EXAMPLE_DIR = ROOT / "protocol" / "examples" / "fetch-ball"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    common = _load(SCHEMA_DIR / "control-envelope.schema.json")
    schema = _load(SCHEMA_DIR / "fetch-ball.schema.json")
    registry = Registry().with_resource(
        common["$id"], Resource.from_contents(common)
    )
    return Draft202012Validator(schema, registry=registry)


def _fixture(name: str) -> dict:
    return _load(EXAMPLE_DIR / name)


def test_schema_itself_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(_load(SCHEMA_DIR / "fetch-ball.schema.json"))


@pytest.mark.parametrize(
    "name",
    [
        "inline-toss.json",
        "artifact-toss.json",
        "chew.json",
        "done.json",
        "partial.json",
        "failed.json",
        "cancelled.json",
        "gone.json",
    ],
)
def test_canonical_fetch_ball_fixtures_validate(name: str) -> None:
    _validator().validate(_fixture(name))


def test_inline_and_artifact_payload_sources_are_mutually_exclusive() -> None:
    body = deepcopy(_fixture("inline-toss.json"))
    body["payload_artifact_id"] = "unexpected-artifact"
    with pytest.raises(ValidationError):
        _validator().validate(body)


def test_artifact_payload_cannot_embed_inline_script() -> None:
    body = deepcopy(_fixture("artifact-toss.json"))
    body["inline_payload"] = "echo duplicate"
    with pytest.raises(ValidationError):
        _validator().validate(body)


def test_oversized_inline_payload_is_rejected() -> None:
    body = deepcopy(_fixture("inline-toss.json"))
    body["inline_payload"] = "x" * 8193
    with pytest.raises(ValidationError):
        _validator().validate(body)


def test_partial_requires_known_completed_effect_evidence() -> None:
    body = deepcopy(_fixture("partial.json"))
    body["completed_effects"] = []
    with pytest.raises(ValidationError):
        _validator().validate(body)


def test_partial_cannot_claim_unknown_effects() -> None:
    body = deepcopy(_fixture("partial.json"))
    body["effects_known"] = "UNKNOWN"
    with pytest.raises(ValidationError):
        _validator().validate(body)


def test_gone_requires_unknown_effect_marker_and_no_exit_code() -> None:
    body = deepcopy(_fixture("gone.json"))
    body["effects_known"] = "PARTIAL"
    with pytest.raises(ValidationError):
        _validator().validate(body)

    body = deepcopy(_fixture("gone.json"))
    body["exit_code"] = 1
    with pytest.raises(ValidationError):
        _validator().validate(body)


def test_terminal_result_requires_remote_result_identity_evidence() -> None:
    body = deepcopy(_fixture("done.json"))
    body["result_sha256"] = None
    with pytest.raises(ValidationError):
        _validator().validate(body)

    body = deepcopy(_fixture("done.json"))
    body["finished_at"] = 0
    with pytest.raises(ValidationError):
        _validator().validate(body)


def test_terminal_result_cannot_lose_fencing_identity() -> None:
    for field in ("generation", "operation_id"):
        body = deepcopy(_fixture("done.json"))
        del body[field]
        with pytest.raises(ValidationError):
            _validator().validate(body)


def test_filename_lifecycle_state_is_not_duplicated_in_body() -> None:
    body = deepcopy(_fixture("chew.json"))
    body["state"] = "CHEW"
    with pytest.raises(ValidationError):
        _validator().validate(body)


def test_unknown_body_fields_are_rejected() -> None:
    body = deepcopy(_fixture("inline-toss.json"))
    body["mystery_meat"] = "nope"
    with pytest.raises(ValidationError):
        _validator().validate(body)
