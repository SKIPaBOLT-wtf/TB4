from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from tb4.core.protocol_names import LogicalObject, Role
from tb4.core.retry import RetryPolicy
from tb4.core.schemas import canonical_json_text
from tb4.drive.body_keeper import BodyKeeper
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.drive.state_walker import StateWalker
from tb4.watchdog.health import (
    FaultScope,
    FaultSignal,
    HealthOutcome,
    WatchdogHealth,
    WorkKind,
    classify_fault_code,
)


@dataclass
class FakeClock:
    monotonic_value: float = 100.0
    epoch_value: int = 1_700_100_000

    def monotonic(self):
        return self.monotonic_value

    def epoch(self):
        value = self.epoch_value
        self.epoch_value += 1
        return value

    def sleep(self, seconds):
        self.monotonic_value += seconds
        self.epoch_value += int(seconds)


def clean_body(now: int = 1_700_100_000):
    return {
        "schema_version": 1,
        "protocol_major": 1,
        "reported_at": now,
        "source": "WATCHDOG",
        "scope": "NONE",
        "fault_code": None,
        "description": None,
        "invariant_key": None,
        "first_seen_at": 0,
        "last_seen_at": 0,
        "occurrence_count": 0,
    }


def make_health():
    backend = InMemoryDriveBackend()
    clock = FakeClock()
    created = backend.create_text(
        backend.root_id,
        "DOG_SHIT_CLEAN",
        canonical_json_text(clean_body()),
    )
    assert created.ok and created.value is not None

    policy = RetryPolicy((0.01, 0.02, 0.04), 3)
    walker = StateWalker(backend, policy, clock.monotonic, clock.sleep)
    keeper = BodyKeeper(backend, policy, clock.monotonic, clock.sleep)
    health = WatchdogHealth(
        backend=backend,
        state_walker=walker,
        body_keeper=keeper,
        dog_shit_object_id=created.value.metadata.object_id,
        epoch_now=clock.epoch,
    )
    backend.reset_operation_counts()
    return backend, clock, walker, health, created.value.metadata.object_id


def read_body(backend, object_id):
    result = backend.read_text(object_id)
    assert result.ok and result.value is not None
    return json.loads(result.value.text)


def review_fault(walker, object_id):
    result = walker.walk(
        object_id=object_id,
        logical_object=LogicalObject.WATCHDOG_FAULT,
        expected_state="BLOCKING",
        target_state="REVIEWED",
        actor=Role.COACH,
    )
    assert result.success


def signal(code: str, *, description="test fault", invariant="test.invariant"):
    return FaultSignal(
        code=code,
        description=description,
        scope=classify_fault_code(code),
        invariant_key=invariant,
    )


def test_fault_classifier_is_explicit_and_rejects_unknown_codes():
    assert classify_fault_code("WOL_FAILED") is FaultScope.TARGET_LOCAL
    assert classify_fault_code("DRIVE_TRANSIENT") is FaultScope.TRANSPORT_RECOVERABLE
    assert classify_fault_code("PARK_MAP_AMBIGUOUS") is FaultScope.PROTOCOL_BLOCKING
    assert classify_fault_code("DRIVE_ROOT_UNREACHABLE") is FaultScope.GLOBAL_BLOCKING

    with pytest.raises(ValueError):
        classify_fault_code("SOMETHING_NEW_AND_UNCLASSIFIED")


def test_missing_fault_register_fails_closed_for_all_work():
    backend = InMemoryDriveBackend()
    clock = FakeClock()
    policy = RetryPolicy((0.01,), 1)
    health = WatchdogHealth(
        backend=backend,
        state_walker=StateWalker(backend, policy, clock.monotonic, clock.sleep),
        body_keeper=BodyKeeper(backend, policy, clock.monotonic, clock.sleep),
        dog_shit_object_id="missing-dog-shit",
        epoch_now=clock.epoch,
    )

    assert classify_fault_code("DRIVE_ROOT_UNREACHABLE") is FaultScope.GLOBAL_BLOCKING
    assert health.can_accept(WorkKind.NORMAL_CONTROL) is False
    assert health.can_accept(WorkKind.DIAGNOSTIC_READ) is False
    assert health.can_accept(WorkKind.REPAIR) is False


def test_park_map_ambiguity_sets_blocking_and_gates_normal_control():
    backend, _, _, health, object_id = make_health()

    result = health.report(
        signal(
            "PARK_MAP_AMBIGUOUS",
            description="canonical PARK_MAP has multiple irreducible candidates",
            invariant="park_map.unique_canonical",
        )
    )

    assert result.outcome is HealthOutcome.BLOCKING_SET
    assert backend.get_metadata(object_id).value.name == "DOG_SHIT_BLOCKING"
    body = read_body(backend, object_id)
    assert body["fault_code"] == "PARK_MAP_AMBIGUOUS"
    assert body["scope"] == "PROTOCOL_BLOCKING"
    assert body["occurrence_count"] == 1

    assert health.can_accept(WorkKind.NORMAL_CONTROL) is False
    assert health.can_accept(WorkKind.DIAGNOSTIC_READ) is True
    assert health.can_accept(WorkKind.REPAIR) is True


def test_ordinary_wol_failure_is_nonblocking():
    backend, _, _, health, object_id = make_health()

    result = health.report(signal("WOL_FAILED", invariant="target-a.wake"))

    assert result.outcome is HealthOutcome.NONBLOCKING
    assert backend.get_metadata(object_id).value.name == "DOG_SHIT_CLEAN"
    assert health.can_accept(WorkKind.NORMAL_CONTROL) is True


def test_one_fetch_ball_gone_is_nonblocking():
    backend, _, _, health, object_id = make_health()

    result = health.report(signal("FETCH_BALL_GONE", invariant="target-a.fetch"))

    assert result.outcome is HealthOutcome.NONBLOCKING
    assert backend.get_metadata(object_id).value.name == "DOG_SHIT_CLEAN"


def test_repeated_same_blocker_refreshes_one_current_fault():
    backend, _, _, health, object_id = make_health()
    fault = signal(
        "STATE_MUTATION_UNCONFIRMED",
        description="verified rename could not be reconciled",
        invariant="drive.verified_mutation",
    )

    first = health.report(fault)
    second = health.report(fault)

    assert first.outcome is HealthOutcome.BLOCKING_SET
    assert second.outcome is HealthOutcome.BLOCKING_REFRESHED
    assert backend.get_metadata(object_id).value.name == "DOG_SHIT_BLOCKING"
    body = read_body(backend, object_id)
    assert body["fault_code"] == "STATE_MUTATION_UNCONFIRMED"
    assert body["occurrence_count"] == 2


def test_review_acknowledgement_does_not_clear_broken_invariant():
    backend, _, walker, health, object_id = make_health()
    health.report(
        signal(
            "CANONICAL_TREE_AMBIGUOUS",
            description="live tree cannot be reconciled to one canonical object",
            invariant="tree.unique_live_objects",
        )
    )
    review_fault(walker, object_id)

    result = health.revalidate_reviewed(lambda: False)

    assert result.outcome is HealthOutcome.STILL_BLOCKING
    assert backend.get_metadata(object_id).value.name == "DOG_SHIT_BLOCKING"
    assert health.can_accept(WorkKind.NORMAL_CONTROL) is False


def test_reviewed_fault_clears_only_after_invariant_revalidation():
    backend, _, walker, health, object_id = make_health()
    health.report(
        signal(
            "DRIVE_AUTH_UNAVAILABLE",
            description="WATCHDOG cannot authorize canonical Drive operations",
            invariant="drive.authorization",
        )
    )
    review_fault(walker, object_id)

    result = health.revalidate_reviewed(lambda: True)

    assert result.outcome is HealthOutcome.CLEANED
    assert backend.get_metadata(object_id).value.name == "DOG_SHIT_CLEAN"
    body = read_body(backend, object_id)
    assert body["scope"] == "NONE"
    assert body["fault_code"] is None
    assert body["occurrence_count"] == 0
    assert health.can_accept(WorkKind.NORMAL_CONTROL) is True


def test_health_path_uses_exact_object_operations_not_folder_scans():
    backend, _, _, health, _ = make_health()

    health.report(
        signal(
            "PARK_MAP_AMBIGUOUS",
            invariant="park_map.unique_canonical",
        )
    )

    assert backend.operation_counts.get("list_children", 0) == 0
