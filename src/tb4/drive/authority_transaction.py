"""Bounded exact-operation reconciliation; no callable payload or executor.

Internal cooperative primitive, not an authorization API. Role enrollment,
durable write-ahead state and scheduling are supplied by later runtime steps.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

from tb4.command_contract import (binding, compact_record, expand_leaf, operation_id,
                                  validate_request, validate_result, validate_shape, ContractError)
from tb4.exchange_layout import MAX_GENERATION, encoded, validate_document
from .docs_authority import AuthorityError, WriteResult, require


@dataclass(frozen=True, repr=False)
class OwnerGuard:
    owner: str
    epoch: int

    def matches(self, document):
        records = document["records"]
        row = records["global.leadership"]
        leader = row["body"]
        return (type(self.owner) is str and 1 <= len(self.owner) <= 128
                and type(self.epoch) is int and 1 <= self.epoch <= MAX_GENERATION
                and type(leader) is dict and leader.get("owner") == self.owner
                and type(leader.get("epoch")) is int and leader["epoch"] == self.epoch
                and row["generation"] == self.epoch and row["retention"] == "BUSY"
                and leader.get("phase") == "ACTIVE"
                and records["global.force_request"]["retention"] == "FREE")


@dataclass(frozen=True, repr=False)
class RecordMutation:
    binding: object
    owner: OwnerGuard
    header: bytes
    protected: bytes
    before: bytes
    after: bytes

    @classmethod
    def prepare(cls, snapshot, *, owner, changes, protect):
        document = snapshot.document()
        require(isinstance(owner, OwnerGuard) and owner.matches(document), "OWNER_SUPERSEDED")
        require(type(changes) is dict and changes and type(protect) in {set, frozenset}, "MUTATION_SHAPE")
        records = document["records"]
        require(set(changes) <= records.keys() and protect <= records.keys()
                and not set(changes) & protect, "MUTATION_SLOTS")
        require(not {"global.leadership", "global.force_request"} & set(changes), "ELECTION_SEPARATE")
        proposed = copy.deepcopy(document)
        proposed["records"].update(copy.deepcopy(changes))
        validate_document(proposed)
        require(any(encoded(changes[k]) != encoded(records[k]) for k in changes), "NO_CHANGE")
        return cls(snapshot.binding, owner,
                   encoded({k:v for k,v in document.items() if k != "records"}),
                   encoded({k:records[k] for k in protect}),
                   encoded({k:records[k] for k in changes}), encoded(changes))

    def evaluate(self, snapshot):
        import json
        document = snapshot.document()
        if snapshot.binding != self.binding:
            return "CONFLICT", None
        if not self.owner.matches(document):
            return "SUPERSEDED", None
        if encoded({k:v for k,v in document.items() if k != "records"}) != self.header:
            return "CONFLICT", None
        records = document["records"]
        protected, before, after = (json.loads(v) for v in (self.protected, self.before, self.after))
        if any(encoded(records[k]) != encoded(value) for k,value in protected.items()):
            return "CONFLICT", None
        if all(encoded(records[k]) == encoded(value) for k,value in after.items()):
            return "CONFIRMED", None
        if any(encoded(records[k]) != encoded(value) for k,value in before.items()):
            return "CONFLICT", None
        document["records"].update(after)
        validate_document(document)
        return "READY", document


@dataclass(frozen=True)
class Reconciliation:
    outcome: str
    reads: int
    writes: int
    inspect_required: bool
    # Confirmation of this shared transition is not permission to execute work.
    execution_authorized: bool = False


def reconcile(backend, plan, *, mode, max_reads=6, max_writes=3):
    """START after durable intent, INSPECT after any possibly sent prior request.

Call counts are bounded, not provider wall time. The injected transport needs
timeouts; the runtime owns quota/backoff and persistence. Unknown responses never
trigger another mutation in this call. START is not allowed as restart recovery.
"""
    require(mode in {"START", "INSPECT"} and isinstance(plan, RecordMutation), "RECOVERY_MODE")
    require(type(max_reads) is int and 2 <= max_reads <= 12
            and type(max_writes) is int and 1 <= max_writes <= 4, "RETRY_BUDGET")
    pending, rejected_revision, writes = mode == "INSPECT", None, 0
    for reads in range(1, max_reads + 1):
        try:
            snapshot = backend.read()
            state, desired = plan.evaluate(snapshot)
        except AuthorityError:
            return Reconciliation("UNKNOWN" if pending else "UNAVAILABLE", reads, writes, pending)
        if state != "READY":
            return Reconciliation(state, reads, writes, pending and state != "CONFIRMED")
        if pending:
            continue  # Stale/absent readback does not prove the write never applied.
        if snapshot.revision == rejected_revision:
            return Reconciliation("REJECTED", reads, writes, False)
        if writes == max_writes or reads == max_reads:
            return Reconciliation("CONFLICT", reads, writes, False)
        result = backend.compare_replace(snapshot, desired)
        writes += 1
        if result == WriteResult.REJECTED:
            rejected_revision = snapshot.revision
        elif result == WriteResult.UNAVAILABLE:
            return Reconciliation("UNAVAILABLE", reads, writes, False)
        else:
            pending = True
    return Reconciliation("UNKNOWN", max_reads, writes, True)


def terminal_publication(snapshot, *, target_index, expected_binding,
                         result_sha256, owner, now):
    """Port RP-013's same-operation finalization to one native authority CAS.

The result already exists in RETURNING. This does not execute, obtain, fabricate
or durably spool it. The caller provides a pinned binding and current-owner guard;
RP-017/043/047/048 must provide role grants and durable runtime integration.
"""
    require(type(target_index) is int and 0 <= target_index < 64, "TARGET_SLOT")
    document = snapshot.document()
    records = document["records"]
    prefix = f"target.{target_index:03d}."
    try:
        work, result_row, status = (records[prefix+k] for k in ("work", "result", "status"))
        validate_shape("binding", expected_binding)
        request = {**work["body"], "operation_id":work["operation_id"], "generation":work["generation"]}
        validate_shape("request", request)
        protected = {prefix+"work"}
        artifacts = {}
        if request["payload"]["kind"] == "ARTIFACT":
            slot = f"artifact.{target_index:03d}.input"
            require(request["payload"]["slot"] == slot, "ARTIFACT_BINDING")
            artifact = records[slot]
            require(artifact["operation_id"] == expected_binding["operation_id"]
                    and artifact["generation"] == request["payload"]["artifact_generation"]
                    and artifact["retention"] == "BUSY", "ARTIFACT_BINDING")
            descriptor = artifact["body"]
            require(type(descriptor) is dict and set(descriptor) == {
                "target_id", "size_bytes", "sha256", "complete"}, "ARTIFACT_BINDING")
            require(descriptor["complete"] is True and type(descriptor["size_bytes"]) is int
                    and type(descriptor["target_id"]) is str and type(descriptor["sha256"]) is str,
                    "ARTIFACT_BINDING")
            artifacts[slot] = {"generation":artifact["generation"], **descriptor}
            protected.add(slot)
        validate_request(request, domain_id=document["domain_id"],
                         targets={expected_binding["target_id"]}, now=now, artifacts=artifacts)
        require(binding(request) == expected_binding and document["domain_id"] == expected_binding["domain_id"]
                and work["retention"] == "BUSY"
                and expected_binding["operation_id"] == operation_id(document["domain_id"],
                    expected_binding["target_id"], expected_binding["generation"]), "WORK_BINDING")
        result = expand_leaf("result", result_row, expected_binding)
        require(result_row["retention"] == "BUSY", "PUBLICATION_STATE")
        validate_result(result, expected_binding)
        require(result["result_sha256"] == result_sha256, "RESULT_BINDING")
        require(status["operation_id"] == expected_binding["operation_id"]
                and status["generation"] == expected_binding["generation"]
                and status["retention"] == "BUSY", "STATUS_BINDING")
        value = dict(binding=expected_binding, receipt="ADMITTED", execution=result["execution"],
                     publication="PENDING", consumption="NOT_READY", terminal=False,
                     result_sha256=result_sha256, **status["body"])
        validate_shape("status_projection", value)
        require(value["stage"] == "RETURNING" and value["responsible"] == "FETCHER"
                and value["wait_reason"] == "PUBLICATION", "PUBLICATION_STATE")
        require(type(now) is int and value["last_progress_at"] <= now <= 10**12, "TIME_RANGE")
        value.update(publication="CONFIRMED", consumption="PENDING", terminal=True,
                     stage="AWAITING_CONSUMPTION", responsible="COACH", wait_reason="RESULT_ACK",
                     stage_at=now, last_progress_at=now, next_check_at=None, deadline_at=None)
        new_status = compact_record("status_projection", value, expected_binding, target_index)
        new_result = copy.deepcopy(result_row)
        new_result["retention"] = "UNREAD"
        return RecordMutation.prepare(snapshot, owner=owner,
            changes={prefix+"status":new_status, prefix+"result":new_result}, protect=protected)
    except (KeyError, TypeError, ContractError):
        raise AuthorityError("PUBLICATION_INVALID") from None
