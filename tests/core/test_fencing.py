from __future__ import annotations

import pytest

from tb4.core.fencing import (
    FenceDisposition,
    FenceToken,
    FenceViolation,
    assert_fence,
    compare_fence,
    validate_generation_advance,
)
from tb4.core.models import Generation, ObjectStateRef, OperationId
from tb4.core.protocol_names import LogicalObject


def _token(
    *,
    object_id: str = "drive-fetch-ball-a",
    operation_id: str = "job-1700000000-a1b2c3d4",
    generation: int = 7,
    state: str = "CHEW",
) -> FenceToken:
    return FenceToken(
        object_id=object_id,
        operation_id=OperationId(operation_id),
        generation=Generation(generation),
        expected_state=ObjectStateRef(LogicalObject.FETCH_BALL, state),
    )


def test_matching_fence_passes() -> None:
    expected = _token()
    observed = _token()
    decision = compare_fence(expected, observed)
    assert decision.disposition is FenceDisposition.VALID
    assert decision.allowed
    assert_fence(expected, observed)


def test_old_worker_generation_is_stale() -> None:
    worker = _token(generation=7)
    current = _token(generation=8)
    decision = compare_fence(worker, current)
    assert decision.disposition is FenceDisposition.STALE
    with pytest.raises(FenceViolation):
        assert_fence(worker, current)


def test_wrong_job_id_is_rejected() -> None:
    decision = compare_fence(
        _token(),
        _token(operation_id="job-1700000001-deadbeef"),
    )
    assert decision.disposition is FenceDisposition.MISMATCH


def test_object_id_mismatch_is_rejected() -> None:
    decision = compare_fence(_token(), _token(object_id="other-object"))
    assert decision.disposition is FenceDisposition.MISMATCH


def test_new_state_with_stale_generation_is_still_rejected_as_stale() -> None:
    decision = compare_fence(
        _token(generation=7, state="CHEW"),
        _token(generation=8, state="RETURNING"),
    )
    assert decision.disposition is FenceDisposition.STALE


def test_same_generation_wrong_state_is_rejected() -> None:
    decision = compare_fence(_token(), _token(state="RETURNING"))
    assert decision.disposition is FenceDisposition.MISMATCH


def test_observed_older_generation_is_mismatch_not_permission() -> None:
    decision = compare_fence(_token(generation=8), _token(generation=7))
    assert decision.disposition is FenceDisposition.MISMATCH


def test_missing_fence_component_is_never_a_wildcard() -> None:
    data = _token().to_mapping()
    for key in tuple(data):
        incomplete = dict(data)
        del incomplete[key]
        with pytest.raises(ValueError, match="missing fence component"):
            FenceToken.from_mapping(incomplete)


def test_fence_mapping_round_trip() -> None:
    token = _token()
    assert FenceToken.from_mapping(token.to_mapping()) == token


def test_generation_advance_must_be_strictly_monotonic() -> None:
    assert validate_generation_advance(Generation(7), Generation(8))
    assert validate_generation_advance(Generation(7), Generation(10))
    assert not validate_generation_advance(Generation(7), Generation(7))
    assert not validate_generation_advance(Generation(7), Generation(6))
