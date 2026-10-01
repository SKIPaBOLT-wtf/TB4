"""Owner-coordinated fixed-record enrollment with authenticated peer ports and no replay."""
from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
import secrets

from .ballpark_setup import pin_record, validate_pin
from .commissioning_state import Setup, storage_spec
from .discovery_workflow import Discovery
from .discovery_state import catalogue_record
from .drive.authority_transaction import RecordMutation, OwnerGuard, reconcile
from .drive.commissioning import frozen_plan, restored_plan
from .enrollment_records import enrollment, target, view
from .exchange_layout import empty_document, encoded, validate_document
from .fetcher_enrollment import announcement
from .fetcher_profile import require, integer, compact, freshness, EnrollmentError
from .instructions import RuntimeFacts, select, check_boundary
from .watchdog.leadership_runtime import Action

GUIDANCE = "skill/tb4/operations/enrollment-r2.md"


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


@dataclass(frozen=True, repr=False)
class VerifiedPeer:
    """Trusted verifier result, never deserialized from an announcement.

    Production verification must bind the authenticated installation to the actual
    approved device and current profile bytes. No default accepting verifier.
    """
    installation_id: str
    device_id: str
    nonce: str
    profile_sha256: str
    verified_at: int
    runtime: RuntimeFacts


def transition(document, request, *, mode, operation):
    """Pure bounded after-image. The caller separately verifies owner and peer."""
    require(mode in {"REGISTER", "PROFILE", "REVOKE"}, "ENROLLMENT_TRANSITION")
    require(type(operation) is str and len(operation) == 64
            and all(c in "0123456789abcdef" for c in operation), "ENROLLMENT_OPERATION")
    if mode == "REVOKE":
        require(type(request) is dict and set(request) == {"slot", "installation_id", "expected_revision"},
                "ENROLLMENT_REVOCATION")
    else:
        request = announcement(request)
    row, body, approved, prior, old_profile = target(document, request["slot"])
    require(row["generation"] < 2**63-1, "ENROLLMENT_GENERATION_EXHAUSTED")
    next_body = copy.deepcopy(body)
    if mode == "REVOKE":
        require(prior is not None and prior["state"] == "ENROLLED"
                and prior["installation_id"] == request["installation_id"]
                and integer(request["expected_revision"], 1, 2**63-2)
                and prior["revision"] == request["expected_revision"], "ENROLLMENT_REVOCATION")
        next_binding = [1, prior["installation_id"], prior["revision"]+1, 1, prior["nonce"]]
        next_profile = compact(old_profile, prior["revision"]+1)
    else:
        require(approved["device_id"] == request["device_id"], "ENROLLMENT_DEVICE_CHANGED")
        if prior is None:
            require(mode == "REGISTER" and request["expected_enrollment_revision"] == 0
                    and request["profile"]["revision"] == 1, "ENROLLMENT_NOT_APPROVED")
            next_binding = [1, request["installation_id"], 1, 0, request["nonce"]]
        else:
            require(mode == "PROFILE" and prior["state"] == "ENROLLED"
                    and prior["installation_id"] == request["installation_id"]
                    and prior["nonce"] == request["nonce"]
                    and request["expected_enrollment_revision"] == prior["revision"],
                    "ENROLLMENT_REINSTALL_MAINTENANCE")
            require(request["profile"]["revision"] == old_profile["revision"]+1
                    and request["profile"]["polling"]["observed_at"] > old_profile["polling"]["observed_at"],
                    "ENROLLMENT_STALE_PROFILE")
            next_binding = body["enrollment"]
        for key, other in document["records"].items():
            if key.endswith(".catalogue") and key != f"target.{request['slot']:03d}.catalogue":
                other_binding = enrollment(catalogue_record(other)["enrollment"])
                require(other_binding is None or other_binding["installation_id"] != request["installation_id"],
                        "ENROLLMENT_INSTALLATION_DUPLICATE")
        next_profile = compact(request["profile"], next_binding[2])
    next_body.update(enrollment=next_binding, fetcher=next_profile)
    key = f"target.{request['slot']:03d}.catalogue"
    after = {key: dict(generation=row["generation"]+1, operation_id=operation,
                      retention="RETAINED", body=next_body)}
    proposed = copy.deepcopy(document)
    proposed["records"].update(after)
    validate_document(proposed)  # Full key/envelope/body budget, before save/write.
    catalogue_record(after[key])
    return after


def package(value, payload):
    require(type(value) is dict and set(value) == {"authority", "active", "pending"}, "ENROLLMENT_PACKAGE")
    choices = payload["choices"]
    spec, handle = storage_spec(choices["storage"])
    require(choices["role"] == "watchdog" and value["authority"] == handle.record()
            and type(value["active"]) is dict and len(value["active"]) <= spec.capacity.devices,
            "ENROLLMENT_PACKAGE")
    for index, item in value["active"].items():
        require(type(index) is str and index.isascii() and index.isdecimal() and str(int(index)) == index
                and integer(int(index), 0, spec.capacity.devices-1)
                and type(item) is dict and set(item) == {"device_id", "enrollment", "approval_id", "profile_revision"},
                "ENROLLMENT_PACKAGE")
        from .credential_contract import identity
        binding = enrollment(item["enrollment"])
        require(identity(item["device_id"]) and binding is not None
                and binding["installation_id"] != payload["installation_id"]
                and type(item["approval_id"]) is str and len(item["approval_id"]) == 64
                and all(c in "0123456789abcdef" for c in item["approval_id"])
                and integer(item["profile_revision"], 1, 2**63-1), "ENROLLMENT_PACKAGE")
    pending = value["pending"]
    if pending is not None:
        require(type(pending) is dict and set(pending) == {"mode", "request", "operation", "pin", "plan"},
                "ENROLLMENT_PENDING")
        validate_pin(pending["pin"])
        require(GUIDANCE in pending["pin"]["files"]
                and pending["request"]["installation_id"] != payload["installation_id"], "ENROLLMENT_PENDING")
        plan = restored_plan(pending["plan"], None)
        require(plan.owner.owner == payload["installation_id"] and integer(plan.owner.epoch, 1, 2**63-1),
                "ENROLLMENT_PENDING")
        parts = {k: json.loads(getattr(plan, k)) for k in ("header", "protected", "before", "after")}
        require(all(encoded(v) == getattr(plan, k) for k,v in parts.items()), "ENROLLMENT_PENDING")
        document = empty_document(spec.domain_id, spec.capacity)
        require(parts["header"] == {k:v for k,v in document.items() if k != "records"}, "ENROLLMENT_PENDING")
        index = pending["request"]["slot"]
        require(integer(index, 0, spec.capacity.devices-1), "ENROLLMENT_PENDING")
        key = f"target.{index:03d}.catalogue"
        guarded = {"global.registry", "global.settings", "global.commissioning"} | {
            f"target.{i:03d}.catalogue" for i in range(spec.capacity.devices)} - {key}
        require(type(parts["protected"]) is dict and set(parts["protected"]) == guarded
                and type(parts["before"]) is dict and set(parts["before"]) == {key}
                and type(parts["after"]) is dict and set(parts["after"]) == {key}, "ENROLLMENT_PENDING")
        document["records"].update(parts["protected"])
        document["records"].update(parts["before"])
        require(document["records"]["global.commissioning"] == dict(generation=0,
                operation_id=spec.setup_id, retention="RETAINED", body=spec.marker("STORAGE_READY")),
                "ENROLLMENT_PENDING")
        require(transition(document, pending["request"], mode=pending["mode"], operation=pending["operation"])
                == parts["after"], "ENROLLMENT_PENDING")
    return copy.deepcopy(value)


class Enrollment:
    def __init__(self, discovery, *, source, runtime, verify_peer):
        require(type(discovery) is Discovery and type(runtime) is RuntimeFacts and callable(verify_peer),
                "ENROLLMENT_WATCHDOG_CONTEXT")
        self.discovery, self.setup = discovery, discovery.setup
        self.source, self.runtime, self.verify_peer = source, runtime, verify_peer

    def _state(self, *, cancelled=False):
        self.discovery._local(allow_cancelled=cancelled)
        _, handle = storage_spec(self.setup.private_choices()["storage"])
        state = self.setup._payload.get("enrollments", dict(authority=handle.record(), active={}, pending=None))
        return package(state, self.setup._payload)

    def _save(self, state):
        self.setup._fresh()
        self.setup._save({**self.setup._payload, "enrollments": state})

    def _peer(self, request, now, pin):
        try:
            verified = self.verify_peer(copy.deepcopy(request))
            require(type(verified) is VerifiedPeer and verified.installation_id == request["installation_id"]
                    and verified.device_id == request["device_id"] and verified.nonce == request["nonce"]
                    and verified.profile_sha256 == digest(request["profile"])
                    and type(verified.verified_at) is int and verified.verified_at == now
                    and type(verified.runtime) is RuntimeFacts
                    and verified.runtime.build_commit == request["profile"]["build_commit"], "ENROLLMENT_PEER_UNVERIFIED")
            peer_pin = select(self.source, verified.runtime)
            require(peer_pin.commit == pin.commit and peer_pin.profile == pin.profile
                    and peer_pin.instructions == pin.instructions, "ENROLLMENT_PEER_INCOMPATIBLE")
        except EnrollmentError:
            raise
        except Exception:
            raise EnrollmentError("ENROLLMENT_PEER_UNVERIFIED") from None
        p = request["profile"]
        require(p["polling"]["observed_at"] <= now
                and now-p["polling"]["observed_at"] < p["timing"]["fresh_s"], "ENROLLMENT_STALE_PROFILE")

    def register(self, request, *, owner_authorized=False):
        require(owner_authorized is True, "ENROLLMENT_OWNER_REQUIRED")
        return self._change(announcement(request), mode="REGISTER")

    def update(self, request):
        return self._change(announcement(request), mode="PROFILE")

    def revoke(self, slot, *, installation_id, expected_revision, owner_authorized=False):
        require(owner_authorized is True, "ENROLLMENT_OWNER_REQUIRED")
        from .credential_contract import identity
        require(integer(slot, 0, 63) and identity(installation_id)
                and integer(expected_revision, 1, 2**63-2), "ENROLLMENT_REVOCATION")
        return self._change(dict(slot=slot, installation_id=installation_id,
                                 expected_revision=expected_revision), mode="REVOKE")

    def _change(self, request, *, mode):
        state = self._state()
        require(state["pending"] is None and self.setup._payload.get("ballpark_draft") is None
                and not (self.setup._payload.get("ballpark_publication") or {}).get("pending")
                and (self.setup._payload.get("discovery") or {}).get("pending") is None
                and "UNKNOWN" not in self.setup._payload["operations"].values(), "ENROLLMENT_INSPECT_REQUIRED")
        now = self.discovery._current(Action.REGISTER)
        snapshot = self.discovery._snapshot()
        document = snapshot.document()
        pin = select(self.source, self.runtime)
        pin.read(GUIDANCE)
        row, body, approved, binding, profile = target(document, request["slot"])
        if mode != "REVOKE":
            require(request["installation_id"] != self.setup.installation_id, "ENROLLMENT_DISTINCT_INSTALLATION")
            self._peer(request, now, pin)
            if (binding is not None and binding["state"] == "ENROLLED"
                    and binding["installation_id"] == request["installation_id"]
                    and binding["nonce"] == request["nonce"] and profile == request["profile"]
                    and approved["device_id"] == request["device_id"]):
                self._adopt(state, request["slot"], body, row["operation_id"])
                return "CONFIRMED"  # Proven same report, no new CAS or approval.
        elif (binding is not None and binding["state"] == "REVOKED"
              and binding["installation_id"] == request["installation_id"]
              and binding["revision"] == request["expected_revision"]+1):
            return "CONFIRMED"
        operation = secrets.token_hex(32)
        updates = transition(document, request, mode=mode, operation=operation)
        key = f"target.{request['slot']:03d}.catalogue"
        capacity = validate_document(document)
        guarded = {"global.registry", "global.settings", "global.commissioning"} | {
            f"target.{i:03d}.catalogue" for i in range(capacity.devices)} - {key}
        plan = RecordMutation.prepare(snapshot, owner=OwnerGuard(self.discovery.grant.owner,
                    self.discovery.grant.epoch), changes=updates, protect=guarded)
        check_boundary(self.source, pin, self.runtime)
        state["pending"] = dict(mode=mode, request=copy.deepcopy(request), operation=operation,
                                pin=pin_record(pin), plan=frozen_plan(plan))
        self._save(state)
        check_boundary(self.source, pin, self.runtime)
        self.discovery._current(Action.REGISTER)
        self.setup._fresh()
        if mode != "REVOKE":
            self._peer(request, self.discovery._current(Action.REGISTER), pin)
        result = reconcile(self.discovery.leader.backend, plan, mode="START")
        if result.outcome == "CONFIRMED":
            return self.inspect()
        if not result.inspect_required:
            self._save({**state, "pending": None})
        return result.outcome

    def _adopt(self, state, index, body, operation):
        from .fetcher_profile import expand
        binding = enrollment(body["enrollment"])
        previous = state["active"].get(str(index))
        approval = (previous["approval_id"] if previous is not None
                    and previous["enrollment"][1] == binding["installation_id"] else operation)
        state["active"][str(index)] = dict(device_id=body["discovery"]["device_id"],
            enrollment=body["enrollment"], approval_id=approval,
            profile_revision=expand(body["fetcher"], binding["revision"])["revision"])
        self._save(state)

    def inspect(self):
        state = self._state(cancelled=True)
        pending = state["pending"]
        if pending is None:
            return "NO_WORK"
        try:
            # Existing port is read-only here; no owner/peer/instruction grant required.
            from .commissioning_checks import CommissionedStorage
            CommissionedStorage(self.discovery.port).verify(self.setup.private_choices()["storage"])
            document = self.discovery.leader.backend.read().document()
            after = json.loads(restored_plan(pending["plan"], None).after)
            key = next(iter(after))
            if document["records"][key] != after[key]:
                return "UNKNOWN"
            index = pending["request"]["slot"]
            _, body, _, _, _ = target(document, index)
        except Exception:
            return "UNKNOWN"
        state["pending"] = None
        self._adopt(state, index, body, pending["operation"])
        return "CONFIRMED"

    def summary(self, resolver=None, *, now, start=0, limit=4):
        self._state(cancelled=True)
        from .commissioning_checks import CommissionedStorage
        document = CommissionedStorage(self.discovery.port).verify(self.setup.private_choices()["storage"])
        return view(document, self.setup, resolver, now=now, start=start, limit=limit)
