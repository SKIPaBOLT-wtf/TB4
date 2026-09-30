"""Unreleased R2 fixed-layout contract. Pure data; never provisions or dispatches.

Record bodies are opaque here. RP-010 supplies business schemas and ownership;
this module enforces layout identity, finite serialization and preservation only.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, asdict
import json
from uuid import UUID


class LayoutError(ValueError):
    """Allowlisted diagnostic only, without private record content."""


MAX_DOCUMENT_BYTES = 512 * 1024
MAX_GENERATION = 2**63 - 1
CAPACITY_LIMITS = {"devices": (1, 64), "ingress": (1, 16),
                   "history": (1, 128), "quarantine": (1, 32)}
GLOBAL_BUDGETS = {"leadership": 2048, "force_request": 1024, "commissioning": 4096,
                  "settings": 4096, "summary": 8192, "registry": 4096}
TARGET_BUDGETS = {"catalogue": 1024, "work": 1536, "result": 1536,
                  "cancel": 384, "ack": 384, "status": 512}
POOL_BUDGETS = {"ingress": 1024, "history": 384, "quarantine": 512}
RETENTION = {"FREE", "BUSY", "UNREAD", "UNKNOWN", "RETAINED", "CONSUMED"}


def require(condition, code):
    if not condition:
        raise LayoutError(code)


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def encoded(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise LayoutError("INVALID_JSON") from None


@dataclass(frozen=True)
class Capacity:
    devices: int = 8
    ingress: int = 4
    history: int = 32
    quarantine: int = 8

    def __post_init__(self):
        for field, limits in CAPACITY_LIMITS.items():
            require(integer(getattr(self, field), *limits), "CAPACITY_RANGE")

    @classmethod
    def parse(cls, value):
        require(type(value) is dict and set(value) == set(CAPACITY_LIMITS), "CAPACITY_SHAPE")
        return cls(**value)

    @property
    def worst_case_bytes(self):
        # Each slot budget includes its JSON key, envelope and payload. The fixed
        # reserve includes global slots, root header and separators, not payload IO.
        return (32768 + self.devices * sum(TARGET_BUDGETS.values())
                + 2 * self.devices * 512
                + sum(getattr(self, k) * budget for k, budget in POOL_BUDGETS.items()))


def slots(capacity):
    require(isinstance(capacity, Capacity), "CAPACITY_SHAPE")
    result = {"global." + key: budget for key, budget in GLOBAL_BUDGETS.items()}
    for index in range(capacity.devices):
        for kind, budget in TARGET_BUDGETS.items():
            result[f"target.{index:03d}.{kind}"] = budget
        for kind in ("input", "output"):
            result[f"artifact.{index:03d}.{kind}"] = 512
    for kind, budget in POOL_BUDGETS.items():
        for index in range(getattr(capacity, kind)):
            result[f"{kind}.{index:03d}"] = budget
    return result


def empty_record(generation=0):
    return {"generation": generation, "operation_id": None, "retention": "FREE", "body": None}


def empty_document(domain_id, capacity=Capacity()):
    document = {"layout_version": 1, "compatibility_status": "UNRELEASED",
                "domain_id": domain_id, "layout_revision": 1,
                "capacity": asdict(capacity),
                "records": {key: empty_record() for key in slots(capacity)}}
    validate_document(document)
    return document


def validate_document(document):
    require(type(document) is dict and set(document) == {
        "layout_version", "compatibility_status", "domain_id", "layout_revision",
        "capacity", "records"}, "DOCUMENT_SHAPE")
    require(type(document["layout_version"]) is int and document["layout_version"] == 1
            and document["compatibility_status"] == "UNRELEASED", "LAYOUT_VERSION")
    try:
        domain = document["domain_id"]
        require(type(domain) is str and str(UUID(domain)) == domain, "DOMAIN_ID")
    except (ValueError, TypeError, AttributeError):
        raise LayoutError("DOMAIN_ID") from None
    require(integer(document["layout_revision"], 1, MAX_GENERATION), "LAYOUT_REVISION")
    capacity = Capacity.parse(document["capacity"])
    budgets, records = slots(capacity), document["records"]
    require(type(records) is dict and set(records) == set(budgets), "SLOT_IDENTITIES")
    for key, record in records.items():
        require(type(record) is dict and set(record) == {
            "generation", "operation_id", "retention", "body"}, "RECORD_SHAPE")
        require(integer(record["generation"], 0, MAX_GENERATION), "RECORD_GENERATION")
        op = record["operation_id"]
        require(op is None or (type(op) is str and 1 <= len(op) <= 64), "OPERATION_ID")
        require(type(record["retention"]) is str and record["retention"] in RETENTION, "RETENTION")
        if record["retention"] == "FREE":
            require(op is None and record["body"] is None, "FREE_HAS_CONTENT")
        require(len(encoded({key: record})) <= budgets[key], "SLOT_BYTE_BUDGET")
    raw = encoded(document)
    require(len(raw) <= capacity.worst_case_bytes <= MAX_DOCUMENT_BYTES, "DOCUMENT_BYTE_BUDGET")
    return capacity


def admission(document, target_index):
    """Capacity facts only; not authorization, execution acceptance or a reservation."""
    capacity = validate_document(document)
    require(integer(target_index, 0, capacity.devices - 1), "TARGET_SLOT")
    records = document["records"]
    target = f"target.{target_index:03d}."
    free_ingress = tuple(key for key in slots(capacity)
                         if key.startswith("ingress.") and records[key]["retention"] == "FREE")
    free_work = all(records[target + k]["retention"] == "FREE" for k in ("work", "result"))
    free_artifacts = all(records[f"artifact.{target_index:03d}." + k]["retention"] == "FREE"
                         for k in ("input", "output"))
    free_history = any(key.startswith("history.") and record["retention"] == "FREE"
                       for key, record in records.items())
    return {"new_work_has_space": bool(free_ingress) and free_work and free_artifacts and free_history,
            "free_ingress": free_ingress,
            "cancel_has_space": records[target + "cancel"]["retention"] == "FREE",
            "ack_has_space": records[target + "ack"]["retention"] == "FREE",
            "status_is_readable": True}


def expand_document(document, capacity):
    """Prepare an unpublished expansion. Caller must authorize/provision/read back.

    This does not resize live storage or assert that new raw bindings exist.
    Existing records are copied exactly, including all retained/unknown bodies.
    """
    old = validate_document(document)
    require(isinstance(capacity, Capacity), "CAPACITY_SHAPE")
    require(all(getattr(capacity, key) >= getattr(old, key) for key in CAPACITY_LIMITS), "SHRINK_REQUIRES_MIGRATION")
    require(capacity != old, "NO_CAPACITY_CHANGE")
    require(document["layout_revision"] < MAX_GENERATION, "LAYOUT_REVISION_EXHAUSTED")
    expanded = copy.deepcopy(document)
    expanded["capacity"] = asdict(capacity)
    expanded["layout_revision"] += 1
    for key in slots(capacity):
        expanded["records"].setdefault(key, empty_record())
    validate_document(expanded)
    return expanded


def physical_keys(capacity):
    # One authoritative native document plus two pre-existing raw slots per target.
    return ("authority",) + tuple(key for key in slots(capacity) if key.startswith("artifact."))


def provisioning_plan(capacity, receipts):
    """Resume inspection plan only. Missing/ambiguous outcomes never permit create."""
    require(type(receipts) is dict and set(receipts) == set(physical_keys(capacity)), "PROVISIONING_IDENTITIES")
    known_ids, create, inspect = set(), [], []
    for key in physical_keys(capacity):
        receipt = receipts[key]
        require(type(receipt) is dict and set(receipt) == {"outcome", "object_id"}, "PROVISIONING_RECEIPT")
        outcome, object_id = receipt["outcome"], receipt["object_id"]
        require(type(outcome) is str and outcome in {"NOT_STARTED", "UNKNOWN", "CONFIRMED"}, "PROVISIONING_OUTCOME")
        if outcome == "CONFIRMED":
            require(type(object_id) is str and 1 <= len(object_id) <= 128
                    and object_id.isascii() and all(c.isalnum() or c in "-_" for c in object_id), "OBJECT_ID")
            require(object_id not in known_ids, "DUPLICATE_OBJECT_ID")
            known_ids.add(object_id)
        else:
            require(object_id is None, "UNCONFIRMED_BINDING")
            (create if outcome == "NOT_STARTED" else inspect).append(key)
    return {"create_only_after_intent": tuple(create), "inspect_same_operation": tuple(inspect),
            "ready_for_schema_readback": not create and not inspect}
