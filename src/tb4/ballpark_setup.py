"""Repository-guided private drafts. Neither a proposal nor a draft grants work.

The trusted local installer supplies the source adapter, runtime facts and owner
decision. Device text is never read as instructions. Shared publication is a
separate guarded boundary; the active descriptor is unchanged by this module.
"""
from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
import re

from .ballpark import (BallparkError, PLATFORM, LAUNCH, ROLES, TRANSPORTS,
                      catalogue, llm_projection, require, shape, validate, validate_revision)
from .commissioning_state import Setup, storage_spec
from .instructions import (ENTRY, REPOSITORY, REPOSITORY_ID, PinnedWorkflow, RuntimeFacts,
                           check_boundary, select)
from .privacy import closed

GUIDANCE = "skill/tb4/operations/setup-r2.md"
FIELDS = {"roles": ROLES, "platform": PLATFORM, "launch_mode": LAUNCH, "transports": TRANSPORTS}
SELECTION = dict(type="object", properties={"device_id": {"type": "string", "format": "uuid"}, **FIELDS},
                 required=["device_id"], additionalProperties=False)
PROPOSAL = closed({"schema_version": {"const": 1},
                   "expected_revision": {"type": "integer", "minimum": 0},
                   "devices": {"type": "array", "maxItems": 64, "items": SELECTION}})


def digest(value):
    return hashlib.sha256(value).hexdigest()


def pin_record(pin):
    return dict(commit=pin.commit, profile=pin.profile, policy_digest=pin.policy_digest,
                runtime={**asdict(pin.runtime), "capabilities": sorted(pin.runtime.capabilities)},
                instructions=pin.instructions, files={p: digest(b) for p, b in pin.files})


def validate_pin(value):
    require(type(value) is dict and set(value) == {
        "commit", "profile", "policy_digest", "runtime", "instructions", "files"}, "BALLPARK_PIN")
    for key, pattern in (("commit", r"[0-9a-f]{40}"), ("profile", r"[a-z][a-z0-9-]{0,63}"),
                         ("policy_digest", r"[0-9a-f]{64}")):
        require(type(value[key]) is str and re.fullmatch(pattern, value[key]), "BALLPARK_PIN")
    from .instructions import _facts, _path
    runtime = value["runtime"]
    require(type(runtime) is dict and set(runtime) == {"build_commit", "protocol", "capabilities"}
            and type(runtime["capabilities"]) is list
            and all(type(c) is str for c in runtime["capabilities"])
            and len(set(runtime["capabilities"])) == len(runtime["capabilities"]), "BALLPARK_PIN")
    _facts(RuntimeFacts(**{**runtime, "capabilities": frozenset(runtime["capabilities"])}))
    files = value["files"]
    require(type(files) is dict and 2 <= len(files) <= 17 and ENTRY in files and GUIDANCE in files
            and value["instructions"] in files and all((p == ENTRY or _path(p))
                and type(h) is str and re.fullmatch(r"[0-9a-f]{64}", h) for p, h in files.items()),
            "BALLPARK_PIN")
    return value


def restore_pin(source, value, runtime):
    """Fetch the same immutable closure; fresh eligibility never changes its pin."""
    value = validate_pin(value)
    require(value["runtime"] == {**asdict(runtime), "capabilities": sorted(runtime.capabilities)},
            "BALLPARK_RUNTIME_CHANGED")
    files = []
    for path, expected in value["files"].items():
        from .instructions import _read
        content = _read(source, value["commit"], path)
        require(digest(content) == expected, "BALLPARK_PIN_HASH")
        files.append((path, content))
    pin = PinnedWorkflow(value["commit"], value["profile"], runtime, value["policy_digest"],
                         value["instructions"], tuple(files))
    check_boundary(source, pin, runtime)
    return pin


def selections(proposal, entries, base):
    shape(proposal, PROPOSAL)
    require(type(proposal["schema_version"]) is int and type(proposal["expected_revision"]) is int
            and proposal["expected_revision"] == base, "BALLPARK_REVISION_CONFLICT")
    known = {e["device_id"]: e for e in entries if e is not None}
    ids = [d["device_id"] for d in proposal["devices"]]
    require(len(ids) == len(set(ids)) and set(ids) <= set(known), "BALLPARK_UNKNOWN_IDENTITY")
    for row in proposal["devices"]:
        if "roles" in row and "launch_mode" in row:
            require(set(row["roles"]) == set(row["launch_mode"]), "BALLPARK_LAUNCH_ROLE_MISMATCH")
    return known


def package(value, payload):
    """Validate the draft on every protected-frame read, including restart."""
    try:
        require(type(value) is dict and set(value) == {"schema_version", "authority", "base_revision",
            "discovery_revision", "pin", "proposal", "candidate", "decision"}
            and type(value["schema_version"]) is int and value["schema_version"] == 1, "BALLPARK_DRAFT")
        choices = payload["choices"]
        require(choices["role"] == "watchdog" and payload.get("discovery") is not None,
                "BALLPARK_NOT_CONFIGURED")
        spec, authority = storage_spec(choices["storage"])
        image = payload["discovery"]["image"]
        active = choices["descriptor"]
        base = 0 if active is None else active["revision"]
        require(value["authority"] == authority.record() and type(value["base_revision"]) is int
                and value["base_revision"] == base and type(value["discovery_revision"]) is int
                and 0 <= value["discovery_revision"] <= image["revision"], "BALLPARK_DRAFT_BINDING")
        validate_pin(value["pin"])
        known = selections(value["proposal"], image["entries"], base)
        candidate, decision = value["candidate"], value["decision"]
        require((candidate is None) == (decision is None), "BALLPARK_DECISION")
        if candidate is not None:
            candidate = validate(candidate)
            require(candidate["installation_id"] == payload["installation_id"]
                    and candidate["domain_id"] == spec.domain_id
                    and candidate["revision"] == base + 1
                    and len(candidate["devices"]) <= spec.capacity.devices, "BALLPARK_DRAFT_BINDING")
            if active is not None:
                validate_revision(active, candidate, expected_revision=base)
            rows = value["proposal"]["devices"]
            require(len(candidate["devices"]) == len(rows), "BALLPARK_DECISION")
            for device, row in zip(candidate["devices"], rows):
                require(set(row) == {"device_id", *FIELDS}
                        and all(device[k] == row[k] for k in row)
                        and device["alias"] == known[row["device_id"]]["alias"], "BALLPARK_DECISION")
                # These are chosen setup properties, not capability/health proof.
                require(device["capabilities"] == {} and device["observations"] == {}
                        and device["interfaces"] == [] and device["display_name"] == device["alias"],
                        "BALLPARK_DECISION")
            require(type(decision) is dict and set(decision) == {"id", "at", "kind", "candidate_digest"}
                    and decision["kind"] == "LOCAL_OWNER_CONFIRMATION"
                    and type(decision["id"]) is str and re.fullmatch(r"[0-9a-f]{64}", decision["id"])
                    and type(decision["at"]) is int and 0 <= decision["at"] <= 10**12,
                    "BALLPARK_DECISION")
            from .exchange_layout import encoded
            require(decision["candidate_digest"] == digest(encoded(candidate)), "BALLPARK_DECISION")
        return copy.deepcopy(value)
    except BallparkError:
        raise
    except Exception:
        raise BallparkError("BALLPARK_DRAFT") from None


class GuidedBallpark:
    def __init__(self, setup, *, source, runtime):
        require(type(setup) is Setup and type(runtime) is RuntimeFacts, "BALLPARK_CONTEXT")
        self.setup, self.source, self.runtime = setup, source, runtime
        self.pin = None

    def _local(self):
        self.setup._fresh()
        require(self.setup._payload["state"] != "CANCELLED", "BALLPARK_CANCELLED")
        choices = self.setup.private_choices()
        require(choices["role"] == "watchdog" and choices["storage"] is not None
                and self.setup._payload.get("discovery") is not None, "BALLPARK_NOT_CONFIGURED")
        require("UNKNOWN" not in self.setup._payload["operations"].values()
                and self.setup._payload["discovery"]["pending"] is None, "BALLPARK_INSPECT_REQUIRED")
        require(not (self.setup._payload.get("ballpark_publication") or {}).get("pending"),
                "BALLPARK_INSPECT_REQUIRED")
        return choices, self.setup._payload["discovery"]["image"]

    def begin(self):
        choices, image = self._local()
        existing = self.setup._payload.get("ballpark_draft")
        if existing is not None:
            self.pin = restore_pin(self.source, existing["pin"], self.runtime)
            return self.questions()
        self.pin = select(self.source, self.runtime)
        self.pin.read(GUIDANCE)  # Must be in the verified compatible closure.
        _, authority = storage_spec(choices["storage"])
        base = 0 if choices["descriptor"] is None else choices["descriptor"]["revision"]
        value = dict(schema_version=1, authority=authority.record(), base_revision=base,
                     discovery_revision=image["revision"], pin=pin_record(self.pin),
                     proposal=dict(schema_version=1, expected_revision=base, devices=[]),
                     candidate=None, decision=None)
        check_boundary(self.source, self.pin, self.runtime)
        self._save(value)
        return self.questions()

    def _draft(self):
        self._local()
        return package(self.setup._payload.get("ballpark_draft"), self.setup._payload)

    def _save(self, draft):
        self.setup._fresh()
        package(draft, self.setup._payload)
        self.setup._save({**self.setup._payload, "ballpark_draft": draft,
                          "state": "INCOMPLETE", "reason": "REVALIDATION_REQUIRED"})

    def questions(self):
        draft = self._draft()
        entries = self.setup._payload["discovery"]["image"]["entries"]
        rows = {d["device_id"]: d for d in draft["proposal"]["devices"]}
        # No name/address/hint/source text or credential selector enters this view.
        return dict(kind="BALLPARK_SETUP_CHOICES", expected_revision=draft["base_revision"],
                    targets=[dict(device_id=e["device_id"], alias=e["alias"],
                        missing=sorted(set(FIELDS) - set(rows.get(e["device_id"], {}))))
                        for e in entries if e is not None],
                    target_selection_required=not bool(rows),
                    local_topology_required=draft["candidate"] is None)

    def propose(self, proposal):
        """Partial, nonsecret choices are data; they never count as approval."""
        draft = self._draft()
        require(draft["candidate"] is None, "BALLPARK_DECISION_ALREADY_STAGED")
        require(self.pin is not None, "BALLPARK_GUIDANCE_REQUIRED")
        _, image = self._local()
        selections(proposal, image["entries"], draft["base_revision"])
        check_boundary(self.source, self.pin, self.runtime)
        self._save({**draft, "proposal": copy.deepcopy(proposal), "discovery_revision": image["revision"]})
        return self.questions()

    def confirm(self, *, topology, at, owner_authorized=False):
        draft = self._draft()
        require(owner_authorized is True, "BALLPARK_AUTHORITY_REQUIRED")
        require(draft["candidate"] is None and self.pin is not None, "BALLPARK_DECISION_ALREADY_STAGED")
        _, image = self._local()
        require(draft["discovery_revision"] == image["revision"], "BALLPARK_DISCOVERY_CHANGED")
        known = selections(draft["proposal"], image["entries"], draft["base_revision"])
        require(draft["proposal"]["devices"] and all(set(row) == {"device_id", *FIELDS}
                for row in draft["proposal"]["devices"]), "BALLPARK_CHOICES_INCOMPLETE")
        spec, _ = storage_spec(self.setup.private_choices()["storage"])
        candidate = dict(schema_version=1, kind="BALLPARK_LOCAL", visibility="PROTECTED_LOCAL",
            installation_id=self.setup.installation_id, domain_id=spec.domain_id,
            revision=draft["base_revision"]+1, topology=topology, devices=[dict(**row,
                alias=known[row["device_id"]]["alias"], display_name=known[row["device_id"]]["alias"],
                interfaces=[], capabilities={}, observations={}) for row in draft["proposal"]["devices"]])
        validate(candidate)
        import secrets
        from .exchange_layout import encoded
        decision = dict(id=secrets.token_hex(32), at=at, kind="LOCAL_OWNER_CONFIRMATION",
                        candidate_digest=digest(encoded(candidate)))
        check_boundary(self.source, self.pin, self.runtime)
        self._save({**draft, "candidate": candidate, "decision": decision})
        return self.view(now=at)

    def view(self, *, now):
        draft = self._draft()
        require(draft["candidate"] is not None, "BALLPARK_CHOICES_INCOMPLETE")
        minimal = llm_projection(catalogue(draft["candidate"]), now=now)
        # This view is expressly a draft, never advertised as active or enrolled.
        return dict(status="STAGED_UNPUBLISHED", descriptor=minimal,
                    timing=copy.deepcopy(self.setup.private_choices()["timing"]))
