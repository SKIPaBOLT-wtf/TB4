"""Commissioned WATCHDOG publication with durable inspect-only recovery."""
from __future__ import annotations

import copy
import json

from .ballpark import BallparkError, catalogue, llm_projection, require
from .ballpark_records import compact, header, provenance, receipt, shared, validate_receipt
from .ballpark_setup import GuidedBallpark, digest, package as draft_package, pin_record
from .commissioning_checks import CommissionedStorage
from .commissioning_state import storage_spec
from .discovery_state import catalogue_record
from .discovery_workflow import Discovery
from .drive.authority_transaction import OwnerGuard, RecordMutation, reconcile
from .drive.commissioning import frozen_plan, restored_plan
from .exchange_layout import empty_document, encoded, validate_document
from .instructions import check_boundary
from .watchdog.leadership_runtime import Action


def changes(document, draft, choices):
    """Pure exact revision plan; byte budgets apply before any write-ahead save."""
    spec, _ = storage_spec(choices["storage"])
    require(validate_document(document) == spec.capacity and document["domain_id"] == spec.domain_id,
            "BALLPARK_AUTHORITY_BINDING")
    records = document["records"]
    require(records["global.commissioning"] == dict(generation=0, operation_id=spec.setup_id,
        retention="RETAINED", body=spec.marker("STORAGE_READY")), "BALLPARK_AUTHORITY_BINDING")
    candidate = draft["candidate"]
    require(candidate is not None and draft["decision"] is not None, "BALLPARK_CHOICES_INCOMPLETE")
    if draft["base_revision"] == 0:
        from .exchange_layout import empty_record
        require(records["global.registry"] == empty_record()
                and records["global.settings"] == dict(generation=0, operation_id=spec.setup_id,
                    retention="RETAINED", body={"descriptor_state": "UNCONFIGURED"}),
                "BALLPARK_REVISION_CONFLICT")
    else:
        require(shared(document) == catalogue(choices["descriptor"]), "BALLPARK_REVISION_CONFLICT")
    slots, updates = [], {}
    op, revision = draft["decision"]["id"], candidate["revision"]
    for device in candidate["devices"]:
        matches = []
        for index in range(spec.capacity.devices):
            row = records[f"target.{index:03d}.catalogue"]
            body = catalogue_record(row)
            known = body.get("discovery")
            if known and known["device_id"] == device["device_id"]:
                require(known["alias"] == device["alias"], "BALLPARK_IDENTITY_CONFLICT")
                matches.append((index, row, body))
        require(len(matches) == 1, "BALLPARK_DISCOVERY_NOT_PUBLISHED")
        index, row, body = matches[0]
        slots.append(index)
        require(row["generation"] < 2**63-1, "BALLPARK_GENERATION_EXHAUSTED")
        updates[f"target.{index:03d}.catalogue"] = dict(generation=row["generation"]+1,
            operation_id=op, retention="RETAINED", body={**body, "ballpark": compact(device, revision)})
    updates["global.registry"] = dict(generation=revision, operation_id=op, retention="RETAINED",
                                      body=header(draft, slots))
    updates["global.settings"] = dict(generation=revision, operation_id=op, retention="RETAINED",
        body=dict(descriptor_state="VALIDATED", revision=revision, timing=copy.deepcopy(choices["timing"])))
    proposed = copy.deepcopy(document)
    proposed["records"].update(updates)
    validate_document(proposed)
    require(shared(proposed) == catalogue(candidate), "BALLPARK_RECORD_DIGEST")
    return updates


def package(value, payload):
    try:
        require(type(value) is dict and set(value) == {"active", "pending"}, "BALLPARK_PUBLICATION")
        choices = payload["choices"]
        require(choices["role"] == "watchdog", "BALLPARK_PUBLICATION")
        spec, authority = storage_spec(choices["storage"])
        if value["active"] is not None:
            validate_receipt(value["active"], choices)
        pending = value["pending"]
        if pending is not None:
            draft = draft_package(payload["ballpark_draft"], payload)
            require(type(pending) is dict and set(pending) == {"authority", "draft_sha256", "plan"}
                    and pending["authority"] == authority.record()
                    and pending["draft_sha256"] == digest(encoded(draft)), "BALLPARK_PENDING")
            plan = restored_plan(pending["plan"], None)
            require(plan.owner.owner == payload["installation_id"]
                    and type(plan.owner.epoch) is int and 1 <= plan.owner.epoch <= 2**63-1,
                    "BALLPARK_PENDING")
            parts = {key: json.loads(getattr(plan, key)) for key in ("header", "protected", "before", "after")}
            require(all(encoded(v) == getattr(plan, k) for k,v in parts.items()), "BALLPARK_PENDING")
            document = empty_document(spec.domain_id, spec.capacity)
            require(parts["header"] == {k:v for k,v in document.items() if k != "records"}
                    and type(parts["protected"]) is dict and set(parts["protected"]) == {"global.commissioning"}
                    and type(parts["before"]) is dict and type(parts["after"]) is dict
                    and set(parts["before"]) == set(parts["after"]), "BALLPARK_PENDING")
            # Reconstruct only touched rows and the fixed commissioning guard.
            # The prior selected device set is a subset of the new revision.
            document["records"].update(parts["before"])
            document["records"].update(parts["protected"])
            # Unselected catalogues have no valid allocation in empty_document;
            # matching selected IDs uses only the exact recorded touched rows.
            expected = _pending_changes(document, draft, choices, parts["before"])
            require(parts["after"] == expected, "BALLPARK_PENDING")
            validate_document(document)
            document["records"].update(parts["after"])
            validate_document(document)
            require(shared(document) == catalogue(draft["candidate"]), "BALLPARK_PENDING")
        return copy.deepcopy(value)
    except BallparkError:
        raise
    except Exception:
        raise BallparkError("BALLPARK_PUBLICATION") from None


def _pending_changes(document, draft, choices, before):
    """Validate an exact frozen plan without inventing absent remote bindings."""
    from .exchange_layout import empty_record
    spec, _ = storage_spec(choices["storage"])
    records = document["records"]
    require(records["global.commissioning"] == dict(generation=0, operation_id=spec.setup_id,
        retention="RETAINED", body=spec.marker("STORAGE_READY")), "BALLPARK_PENDING")
    if draft["base_revision"] == 0:
        require(records["global.registry"] == empty_record()
                and records["global.settings"] == dict(generation=0, operation_id=spec.setup_id,
                    retention="RETAINED", body={"descriptor_state": "UNCONFIGURED"}), "BALLPARK_PENDING")
    else:
        require(shared(document) == catalogue(choices["descriptor"]), "BALLPARK_PENDING")
    op, revision = draft["decision"]["id"], draft["candidate"]["revision"]
    expected, slots = {}, []
    for device in draft["candidate"]["devices"]:
        matches = [(k,r) for k,r in before.items() if k.startswith("target.")]
        matches = [(k,r) for k,r in matches if catalogue_record(r).get("discovery", {}).get("device_id") == device["device_id"]]
        require(len(matches) == 1, "BALLPARK_PENDING")
        key, row = matches[0]
        index = int(key.split(".")[1])
        require(key == f"target.{index:03d}.catalogue" and 0 <= index < spec.capacity.devices,
                "BALLPARK_PENDING")
        require(row["body"]["discovery"]["alias"] == device["alias"], "BALLPARK_PENDING")
        slots.append(index)
        expected[key] = dict(generation=row["generation"]+1, operation_id=op, retention="RETAINED",
                             body={**row["body"], "ballpark": compact(device, revision)})
    expected["global.registry"] = dict(generation=revision, operation_id=op, retention="RETAINED",
                                      body=header(draft, slots))
    expected["global.settings"] = dict(generation=revision, operation_id=op, retention="RETAINED",
        body=dict(descriptor_state="VALIDATED", revision=revision, timing=copy.deepcopy(choices["timing"])))
    require(set(expected) == set(before), "BALLPARK_PENDING")
    return expected


class Publisher:
    def __init__(self, guidance, discovery):
        require(type(guidance) is GuidedBallpark and type(discovery) is Discovery
                and guidance.setup is discovery.setup, "BALLPARK_CONTEXT")
        self.guide, self.discovery, self.setup = guidance, discovery, guidance.setup

    def _save(self, state):
        self.setup._fresh()
        self.setup._save({**self.setup._payload, "ballpark_publication": state})

    def _state(self):
        self.setup._fresh()
        value = self.setup._payload.get("ballpark_publication", {"active": None, "pending": None})
        return package(value, self.setup._payload)

    def publish(self):
        state = self._state()
        require(state["pending"] is None, "BALLPARK_INSPECT_REQUIRED")
        draft = self.guide._draft()
        require(self.guide.pin is not None and pin_record(self.guide.pin) == draft["pin"],
                "BALLPARK_GUIDANCE_REQUIRED")
        self.discovery._current(Action.REGISTER)
        snapshot = self.discovery._snapshot()
        updates = changes(snapshot.document(), draft, self.setup.private_choices())
        plan = RecordMutation.prepare(snapshot,
            owner=OwnerGuard(self.discovery.grant.owner, self.discovery.grant.epoch),
            changes=updates, protect={"global.commissioning"})
        state["pending"] = dict(authority=draft["authority"], draft_sha256=digest(encoded(draft)),
                                plan=frozen_plan(plan))
        check_boundary(self.guide.source, self.guide.pin, self.guide.runtime)
        self._save(state)
        # Any failure after durable intent leaves the same inspect-only operation.
        check_boundary(self.guide.source, self.guide.pin, self.guide.runtime)
        self.discovery._current(Action.REGISTER)
        self.setup._fresh()
        report = reconcile(self.discovery.leader.backend, plan, mode="START")
        if report.outcome == "CONFIRMED":
            return self.inspect()
        if not report.inspect_required:
            self._save({**state, "pending": None})
        return report.outcome

    def inspect(self):
        state = self._state()
        if state["pending"] is None:
            return "NO_WORK"
        draft = self.setup._payload["ballpark_draft"]
        choices = self.setup.private_choices()
        _, authority = storage_spec(choices["storage"])
        require(self.discovery.leader.backend.binding == self.discovery.port.authority(authority).binding,
                "BALLPARK_AUTHORITY_BINDING")
        try:
            CommissionedStorage(self.discovery.port).verify(choices["storage"])
            document = self.discovery.leader.backend.read().document()
            observed = shared(document)
        except Exception:
            return "UNKNOWN"
        meta = document["records"]["global.registry"]["body"]
        if (observed != catalogue(draft["candidate"]) or meta["provenance"] != provenance(draft)
                or document["records"]["global.settings"]["body"]["timing"] != choices["timing"]):
            return "UNKNOWN"
        # This is evidence of the exact prior write, not a fresh write grant. An
        # owner takeover cannot make a confirmed same-operation result disappear.
        next_payload = copy.deepcopy(self.setup._payload)
        next_payload["choices"]["descriptor"] = copy.deepcopy(draft["candidate"])
        next_payload["ballpark_publication"] = dict(active=receipt(draft, choices["timing"]), pending=None)
        next_payload["ballpark_draft"] = None
        if next_payload["state"] != "CANCELLED":
            next_payload.update(state="INCOMPLETE", reason="REVALIDATION_REQUIRED")
        self.setup._save(next_payload)
        self.guide.pin = None
        return "CONFIRMED"

    def view(self, *, now):
        state = self._state()
        active = state["active"]
        return dict(status="PUBLICATION_UNKNOWN" if state["pending"] else "ACTIVE" if active else "UNCONFIGURED",
                    descriptor=None if active is None else llm_projection(catalogue(
                        self.setup.private_choices()["descriptor"]), now=now),
                    timing=None if active is None else copy.deepcopy(active["timing"]))
