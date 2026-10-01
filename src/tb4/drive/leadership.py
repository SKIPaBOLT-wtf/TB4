"""Unreleased RP-016 cooperative native-authority leadership.

Enrollment and clock confidence are trusted commissioned inputs, not credentials.
No host/sink contact, process start or GUI action happens in this module.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import json
import re
from uuid import UUID

from tb4.exchange_layout import MAX_GENERATION, empty_record, encoded, validate_document
from tb4.timing_contract import TimingProfile, number
from .authority_transaction import OwnerGuard, RecordMutation, reconcile
from .docs_authority import AuthorityError, require


LEADER = "global.leadership"
FORCE = "global.force_request"
LEADER_FIELDS = {"owner", "computer_name", "epoch", "phase", "heartbeat_at",
                 "heartbeat_sequence", "acquisition_id", "transition_id"}
REQUEST_FIELDS = {"request_id", "requester", "computer_name", "expected_epoch",
                  "requested_at", "expires_at"}


def identity(value):
    try:
        return type(value) is str and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def transition_id(value):
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def bounded_int(value, low=0, high=MAX_GENERATION):
    return type(value) is int and low <= value <= high


def wall_time(value):
    return bounded_int(value, 0, 10**12)


@dataclass(frozen=True)
class ClockSample:
    utc: int | None
    monotonic: float
    wall_trusted: bool
    monotonic_trusted: bool = True

    def __post_init__(self):
        require(type(self.wall_trusted) is bool and type(self.monotonic_trusted) is bool
                and number(self.monotonic) and (self.utc is None or wall_time(self.utc))
                and (not self.wall_trusted or self.utc is not None), "CLOCK_SAMPLE")


@dataclass(frozen=True, repr=False)
class Grant:
    owner: str
    epoch: int
    acquisition_id: str


@dataclass(frozen=True, repr=False)
class Observation:
    snapshot: object
    clock: ClockSample
    leader: dict | None
    request: dict | None
    progress: bytes
    _origin: object


@dataclass(frozen=True, repr=False)
class ElectionMutation(RecordMutation):
    """Typed preparation is separate from ordinary record mutation authorization."""
    action: str

    def evaluate(self, snapshot):
        document = snapshot.document()
        if snapshot.binding != self.binding or encoded({k:v for k,v in document.items()
                                                       if k != "records"}) != self.header:
            return "CONFLICT", None
        rows = document["records"]
        before, after = json.loads(self.before), json.loads(self.after)
        if all(encoded(rows[k]) == encoded(v) for k,v in after.items()):
            return "CONFIRMED", None
        if any(encoded(rows[k]) != encoded(v) for k,v in before.items()):
            return "SUPERSEDED", None
        # A fresh unrelated record change does not rewind/rewrite that work.
        document["records"].update(after)
        validate_document(document)
        return "READY", document


class Leadership:
    def __init__(self, backend, *, actor, enrollment, profile=None):
        require(type(enrollment) is dict and 1 <= len(enrollment) <= 64
                and all(identity(k) and type(v) is str and 1 <= len(v) <= 128
                        for k,v in enrollment.items()) and actor in enrollment, "ENROLLMENT")
        self.backend, self.actor = backend, actor
        self.enrollment = dict(enrollment)
        self.profile = TimingProfile() if profile is None else profile
        require(isinstance(self.profile, TimingProfile), "TIMING_PROFILE")
        self._origin = object()
        self._last_plan = self._last_report = None

    def observe(self, clock):
        require(isinstance(clock, ClockSample), "CLOCK_SAMPLE")
        snapshot = self.backend.read()
        leader, request = self._records(snapshot.document())
        progress = encoded(None if leader is None else {k:leader[k] for k in (
            "owner", "epoch", "acquisition_id", "heartbeat_at", "heartbeat_sequence")})
        return Observation(snapshot, clock, copy.deepcopy(leader), copy.deepcopy(request), progress, self._origin)

    def _records(self, document):
        rows = document["records"]
        leader_row, request_row = rows[LEADER], rows[FORCE]
        if leader_row["retention"] == "FREE":
            require(leader_row == empty_record() and request_row == empty_record(), "UNCOMMISSIONED_SHAPE")
            return None, None
        leader = leader_row["body"]
        require(type(leader) is dict and set(leader) == LEADER_FIELDS, "LEADERSHIP_SHAPE")
        require(identity(leader["owner"]) and leader["owner"] in self.enrollment
                and leader["computer_name"] == self.enrollment[leader["owner"]]
                and bounded_int(leader["epoch"], 1)
                and leader_row["generation"] == leader["epoch"]
                and leader_row["retention"] == "BUSY" and leader["phase"] == "ACTIVE"
                and transition_id(leader["acquisition_id"]) and transition_id(leader["transition_id"])
                and leader_row["operation_id"] == leader["acquisition_id"]
                and bounded_int(leader["heartbeat_sequence"])
                and (leader["heartbeat_at"] is None or wall_time(leader["heartbeat_at"])), "LEADERSHIP_IDENTITY")
        if request_row["retention"] == "FREE":
            require(request_row == empty_record(leader["epoch"]), "FORCE_GENERATION")
            return leader, None
        request = request_row["body"]
        require(type(request) is dict and set(request) == REQUEST_FIELDS, "FORCE_SHAPE")
        require(identity(request["requester"]) and request["requester"] in self.enrollment
                and request["requester"] != leader["owner"]
                and request["computer_name"] == self.enrollment[request["requester"]]
                and bounded_int(request["expected_epoch"],1) and request["expected_epoch"] == leader["epoch"]
                and request_row["generation"] == leader["epoch"] and request_row["retention"] == "BUSY"
                and transition_id(request["request_id"]) and request_row["operation_id"] == request["request_id"]
                and wall_time(request["requested_at"]) and wall_time(request["expires_at"])
                and 0 < request["expires_at"]-request["requested_at"] <= self.profile.lease_stale_s,
                "FORCE_IDENTITY")
        return leader, request

    def _observation(self, observed):
        require(isinstance(observed, Observation) and observed._origin is self._origin, "OBSERVATION_ORIGIN")
        # Do not trust mutable decoded values returned for display.
        leader, request = self._records(observed.snapshot.document())
        require(encoded(leader) == encoded(observed.leader) and encoded(request) == encoded(observed.request),
                "OBSERVATION_CHANGED")
        progress = encoded(None if leader is None else {k:leader[k] for k in (
            "owner", "epoch", "acquisition_id", "heartbeat_at", "heartbeat_sequence")})
        require(observed.progress == progress and isinstance(observed.clock,ClockSample), "OBSERVATION_CHANGED")
        return leader, request

    def stale(self, observed, *, since=None):
        leader, _ = self._observation(observed)
        require(leader is not None, "COMMISSIONING_REQUIRED")
        clock, heartbeat = observed.clock, leader["heartbeat_at"]
        if clock.wall_trusted and heartbeat is not None and clock.utc >= heartbeat:
            # The commissioned profile already includes visibility/queue/skew slack.
            return clock.utc-heartbeat >= self.profile.lease_stale_s
        if since is None:
            return False
        self._observation(since)
        expected = encoded({k:leader[k] for k in (
            "owner", "epoch", "acquisition_id", "heartbeat_at", "heartbeat_sequence")})
        require(observed.progress == expected, "OBSERVATION_CHANGED")
        return (since.progress == observed.progress and since.clock.monotonic_trusted
                and clock.monotonic_trusted and clock.monotonic >= since.clock.monotonic
                and clock.monotonic-since.clock.monotonic >= self.profile.lease_stale_s)

    def _plan(self, observed, *, leader, request, action):
        self._observation(observed)
        document = observed.snapshot.document()
        before = {k:document["records"][k] for k in (LEADER,FORCE)}
        leader_row = dict(generation=leader["epoch"], operation_id=leader["acquisition_id"],
                          retention="BUSY", body=leader)
        request_row = (empty_record(leader["epoch"]) if request is None else dict(
            generation=leader["epoch"], operation_id=request["request_id"], retention="BUSY", body=request))
        after = {LEADER:leader_row, FORCE:request_row}
        candidate = copy.deepcopy(document); candidate["records"].update(after)
        validate_document(candidate); self._records(candidate)
        return ElectionMutation(observed.snapshot.binding, OwnerGuard(self.actor,leader["epoch"]),
            encoded({k:v for k,v in document.items() if k != "records"}), encoded({}),
            encoded(before), encoded(after), action)

    def acquire(self, observed, *, transition, since=None, commissioning=False):
        leader, _ = self._observation(observed)
        require(transition_id(transition) and type(commissioning) is bool, "TRANSITION_ID")
        if leader is None:
            require(commissioning, "COMMISSIONING_REQUIRED")
            epoch = 1
        else:
            require(not commissioning and self.stale(observed,since=since), "INCUMBENT_FRESH")
            require(leader["epoch"] < MAX_GENERATION, "EPOCH_EXHAUSTED")
            require(transition != leader["acquisition_id"], "TRANSITION_REUSED")
            epoch = leader["epoch"]+1
        clock = observed.clock
        new = dict(owner=self.actor, computer_name=self.enrollment[self.actor], epoch=epoch,
            phase="ACTIVE", heartbeat_at=(clock.utc if clock.wall_trusted and (leader is None
                or leader["heartbeat_at"] is None or clock.utc >= leader["heartbeat_at"]) else None),
            heartbeat_sequence=0, acquisition_id=transition, transition_id=transition)
        # No examination, cancellation, drain or acknowledgement of target work.
        return self._plan(observed, leader=new, request=None, action="ACQUIRE")

    def _owns(self, leader, request, grant):
        return (isinstance(grant,Grant) and leader is not None and request is None
                and grant.owner == self.actor == leader["owner"]
                and type(grant.epoch) is int and grant.epoch == leader["epoch"]
                and grant.acquisition_id == leader["acquisition_id"])

    def renew(self, observed, grant, *, transition):
        leader, request = self._observation(observed)
        require(self._owns(leader,request,grant), "OWNER_SUPERSEDED")
        require(transition_id(transition) and transition != leader["transition_id"], "TRANSITION_ID")
        require(leader["heartbeat_sequence"] < MAX_GENERATION, "HEARTBEAT_EXHAUSTED")
        new = copy.deepcopy(leader)
        clock = observed.clock
        new.update(heartbeat_sequence=leader["heartbeat_sequence"]+1, transition_id=transition,
            heartbeat_at=(clock.utc if clock.wall_trusted and (leader["heartbeat_at"] is None
                         or clock.utc >= leader["heartbeat_at"]) else None))
        return self._plan(observed,leader=new,request=None,action="RENEW")

    def request_force(self, observed, *, request_id, user_requested):
        leader, previous = self._observation(observed)
        require(user_requested is True, "LOCAL_USER_REQUEST_REQUIRED")
        require(leader is not None and leader["owner"] != self.actor and previous is None, "FORCE_UNAVAILABLE")
        require(transition_id(request_id) and observed.clock.wall_trusted, "FORCE_CLOCK_OR_ID")
        now = observed.clock.utc
        require(now+self.profile.lease_stale_s <= 10**12, "TIME_RANGE")
        request = dict(request_id=request_id, requester=self.actor,
            computer_name=self.enrollment[self.actor], expected_epoch=leader["epoch"],
            requested_at=now, expires_at=now+self.profile.lease_stale_s)
        return self._plan(observed,leader=leader,request=request,action="REQUEST_FORCE")

    def claim_requested(self, observed, *, request_id):
        leader, request = self._observation(observed)
        require(request is not None and request["requester"] == self.actor
                and request["request_id"] == request_id and observed.clock.wall_trusted
                and request["requested_at"] <= observed.clock.utc < request["expires_at"], "FORCE_UNAVAILABLE")
        require(leader["epoch"] < MAX_GENERATION, "EPOCH_EXHAUSTED")
        new = dict(owner=self.actor, computer_name=self.enrollment[self.actor], epoch=leader["epoch"]+1,
            phase="ACTIVE", heartbeat_at=(observed.clock.utc if leader["heartbeat_at"] is None
                or observed.clock.utc >= leader["heartbeat_at"] else None), heartbeat_sequence=0,
            acquisition_id=request_id, transition_id=request_id)
        return self._plan(observed,leader=new,request=None,action="CLAIM_FORCE")

    def expire_request(self, observed):
        leader, request = self._observation(observed)
        require(request is not None and observed.clock.wall_trusted
                and observed.clock.utc >= request["expires_at"], "REQUEST_NOT_EXPIRED")
        return self._plan(observed,leader=leader,request=None,action="EXPIRE_FORCE")

    def commit(self, plan, *, mode):
        require(isinstance(plan,ElectionMutation) and plan.owner.owner == self.actor, "ELECTION_PLAN")
        # The low-level reconciler also inspects after any accepted/lost response.
        report = reconcile(self.backend,plan,mode=mode,max_reads=4,max_writes=2)
        self._last_plan, self._last_report = plan, report
        return report

    def confirmed_grant(self, plan, report):
        require(isinstance(plan,ElectionMutation) and plan.action in {"ACQUIRE","CLAIM_FORCE"}
                and plan is self._last_plan and report is self._last_report
                and report.outcome == "CONFIRMED", "ACQUISITION_UNCONFIRMED")
        leader = json.loads(plan.after)[LEADER]["body"]
        require(leader["owner"] == self.actor, "ACTOR_BINDING")
        return Grant(self.actor,leader["epoch"],leader["acquisition_id"])

    def current_before_dispatch(self, grant, clock):
        """Fresh cooperative check, never an atomic OS/network admission lock.

The caller can be suspended immediately after True, then another owner can win.
Do not use this boolean as a durable/external bearer authorization token.
"""
        observed = self.observe(clock)
        return self._owns(observed.leader,observed.request,grant)
