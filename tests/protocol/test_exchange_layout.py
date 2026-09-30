from copy import deepcopy
from dataclasses import asdict
from itertools import product
import json
from pathlib import Path

import pytest

from tb4.exchange_layout import (Capacity, LayoutError, MAX_DOCUMENT_BYTES,
    MAX_GENERATION, admission, empty_document, empty_record, encoded,
    expand_document, physical_keys, provisioning_plan, slots, validate_document)

DOMAIN = "00000000-0000-4000-8000-000000000001"


def test_machine_contract_and_validator_share_capacity_and_byte_limits():
    from tb4.exchange_layout import CAPACITY_LIMITS, GLOBAL_BUDGETS, TARGET_BUDGETS, POOL_BUDGETS
    spec = json.loads((Path(__file__).resolve().parents[2] /
                      "protocol/drafts/r2-exchange-layout.json").read_text(encoding="utf-8"))
    assert spec["defaults"] == asdict(Capacity())
    assert spec["capacity_limits"] == {k:list(v) for k,v in CAPACITY_LIMITS.items()}
    assert spec["global_slot_bytes"] == GLOBAL_BUDGETS
    assert spec["target_slot_bytes"] == TARGET_BUDGETS
    assert spec["pool_slot_bytes"] == POOL_BUDGETS
    assert spec["max_document_bytes"] == MAX_DOCUMENT_BYTES
    assert spec["normal_operation_create_count"] == 0


def occupy(document, key, retention="BUSY"):
    document["records"][key] = {"generation": 4, "operation_id": "synthetic-operation",
                                "retention": retention, "body": {"marker": "retained"}}


@pytest.mark.parametrize("counts", list(product((1, 64), (1, 16), (1, 128), (1, 32))))
def test_capacity_corners_fit_document_budget_and_have_exact_stable_slots(counts):
    capacity = Capacity(*counts)
    document = empty_document(DOMAIN, capacity)
    assert validate_document(document) == capacity
    assert len(document["records"]) == 6 + 8 * capacity.devices + sum(counts[1:])
    assert len(physical_keys(capacity)) == 1 + 2 * capacity.devices
    assert len(encoded(document)) <= capacity.worst_case_bytes <= MAX_DOCUMENT_BYTES
    assert "target.000.cancel" in document["records"]
    assert f"target.{capacity.devices-1:03d}.ack" in document["records"]
    assert f"target.{capacity.devices:03d}.work" not in document["records"]


def test_default_is_setup_policy_not_topology_and_maximum_is_finite():
    assert asdict(Capacity()) == dict(devices=8, ingress=4, history=32, quarantine=8)
    assert Capacity(64, 16, 128, 32).worst_case_bytes == MAX_DOCUMENT_BYTES
    assert empty_document(DOMAIN)["compatibility_status"] == "UNRELEASED"


@pytest.mark.parametrize("field,bad", [("devices",0),("devices",65),("ingress",17),
    ("history",129),("quarantine",33),("devices",True),("devices",1.0),("history",-1)])
def test_capacity_rejects_bad_bounds_and_coercion(field,bad):
    values = asdict(Capacity())
    values[field] = bad
    with pytest.raises(LayoutError, match="CAPACITY_RANGE"):
        Capacity.parse(values)


@pytest.mark.parametrize("fault", ["extra-capacity", "unknown-slot", "missing-slot", "wrong-domain",
    "unknown-header", "released-claim", "bool-generation", "generation-wrap", "free-with-data"])
def test_closed_layout_and_record_identity_fail_before_admission(fault):
    document = empty_document(DOMAIN)
    record = document["records"]["target.000.work"]
    if fault == "extra-capacity":
        document["capacity"]["parallel_lanes"] = 4
    elif fault == "unknown-slot":
        document["records"]["job-created-on-demand"] = empty_record()
    elif fault == "missing-slot":
        del document["records"]["target.000.cancel"]
    elif fault == "wrong-domain":
        document["domain_id"] = "computer-a"
    elif fault == "unknown-header":
        document["second_authority"] = "another-document"
    elif fault == "released-claim":
        document["compatibility_status"] = "RELEASED"
    elif fault == "bool-generation":
        record["generation"] = True
    elif fault == "generation-wrap":
        record["generation"] = MAX_GENERATION + 1
    else:
        record["body"] = "unread data"
    with pytest.raises(LayoutError):
        admission(document, 0)


@pytest.mark.parametrize("fill", ["work", "result", "ingress", "history", "artifact-input", "artifact-output"])
def test_work_saturation_never_consumes_reserved_cancel_ack_or_status_capacity(fill):
    document = empty_document(DOMAIN)
    if fill in {"work", "result"}:
        occupy(document, "target.000." + fill, "UNREAD")
    elif fill.startswith("artifact-"):
        occupy(document, "artifact.000." + fill.split("-")[1], "UNKNOWN")
    else:
        for key in document["records"]:
            if key.startswith(fill + "."):
                occupy(document, key, "RETAINED")
    before = deepcopy(document)
    status = admission(document, 0)
    assert status["new_work_has_space"] is False
    assert status["cancel_has_space"] is True
    assert status["ack_has_space"] is True
    assert status["status_is_readable"] is True
    assert document == before


def test_busy_target_does_not_hide_other_target_or_pending_control_identity():
    document = empty_document(DOMAIN)
    occupy(document, "target.000.work")
    occupy(document, "target.000.cancel")
    assert not admission(document, 0)["cancel_has_space"]
    assert admission(document, 0)["ack_has_space"]
    assert admission(document, 1)["new_work_has_space"]
    assert document["records"]["target.000.cancel"]["operation_id"] == "synthetic-operation"


@pytest.mark.parametrize("payload", ["x" * 2000, "\U0001f642" * 500, "\"\\\n" * 400])
def test_slot_budget_counts_utf8_and_json_escaping_not_character_guess(payload):
    document = empty_document(DOMAIN)
    occupy(document, "target.000.work")
    document["records"]["target.000.work"]["body"] = payload
    with pytest.raises(LayoutError, match="SLOT_BYTE_BUDGET"):
        validate_document(document)


def test_saturated_maximum_document_remains_within_measured_canonical_byte_budget():
    capacity = Capacity(64, 16, 128, 32)
    document = empty_document(DOMAIN, capacity)
    for key, budget in slots(capacity).items():
        record = {"generation": MAX_GENERATION, "operation_id": "o" * 64,
                  "retention": "RETAINED", "body": ""}
        record["body"] = "x" * (budget - len(encoded({key: record})))
        document["records"][key] = record
        assert len(encoded({key: record})) == budget
    validate_document(document)
    assert len(encoded(document)) <= MAX_DOCUMENT_BYTES


@pytest.mark.parametrize("retention", ["BUSY", "UNREAD", "UNKNOWN", "RETAINED", "CONSUMED"])
def test_expansion_preserves_exact_records_and_does_not_mutate_original(retention):
    original = empty_document(DOMAIN, Capacity(1,1,1,1))
    occupy(original, "target.000.result", retention)
    before = deepcopy(original)
    expanded = expand_document(original, Capacity(2,2,2,2))
    assert original == before
    assert expanded["layout_revision"] == 2
    assert expanded["domain_id"] == DOMAIN
    for key, record in before["records"].items():
        assert encoded(expanded["records"][key]) == encoded(record)
    assert expanded["records"]["target.001.work"] == empty_record()


def test_shrink_revision_wrap_and_noop_are_explicit_failures():
    document = empty_document(DOMAIN)
    with pytest.raises(LayoutError, match="SHRINK_REQUIRES_MIGRATION"):
        expand_document(document, Capacity(1,1,1,1))
    with pytest.raises(LayoutError, match="NO_CAPACITY_CHANGE"):
        expand_document(document, Capacity())
    document["layout_revision"] = MAX_GENERATION
    with pytest.raises(LayoutError, match="LAYOUT_REVISION_EXHAUSTED"):
        expand_document(document, Capacity(devices=9))


def test_interrupted_provisioning_inspects_unknown_instead_of_creating_duplicate():
    capacity = Capacity(1,1,1,1)
    receipts = {key: {"outcome":"NOT_STARTED", "object_id":None} for key in physical_keys(capacity)}
    receipts["authority"] = {"outcome":"UNKNOWN", "object_id":None}
    receipts["artifact.000.input"] = {"outcome":"CONFIRMED", "object_id":"synthetic-input"}
    plan = provisioning_plan(capacity, receipts)
    assert plan["inspect_same_operation"] == ("authority",)
    assert plan["create_only_after_intent"] == ("artifact.000.output",)
    assert not plan["ready_for_schema_readback"]
    assert receipts["authority"]["outcome"] == "UNKNOWN"


@pytest.mark.parametrize("fault", ["missing", "duplicate", "unknown-with-id", "real-path-shape"])
def test_provisioning_never_guesses_missing_or_ambiguous_binding(fault):
    capacity = Capacity(1,1,1,1)
    receipts = {key: {"outcome":"CONFIRMED", "object_id":f"synthetic-{i}"}
                for i,key in enumerate(physical_keys(capacity))}
    assert provisioning_plan(capacity, receipts)["ready_for_schema_readback"]
    if fault == "missing":
        del receipts["authority"]
    elif fault == "duplicate":
        receipts["authority"]["object_id"] = receipts["artifact.000.input"]["object_id"]
    elif fault == "unknown-with-id":
        receipts["authority"]["outcome"] = "UNKNOWN"
    else:
        receipts["authority"]["object_id"] = "../different-root"
    with pytest.raises(LayoutError):
        provisioning_plan(capacity, receipts)
