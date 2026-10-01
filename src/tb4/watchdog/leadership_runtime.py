"""Unreleased native-authority role composition; never wraps legacy v1 writers.

Commissioning supplies private, installation-bound checkpoint/capability ports.
Work adapters implement one bounded action; provider and OS qualification is
separate. No credential material, discovery or action runs in construction.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import secrets

from tb4.drive.authority_transaction import OwnerGuard, RecordMutation, reconcile
from tb4.drive.docs_authority import AuthorityError, require
from tb4.drive.leadership import ClockSample, ElectionMutation, Grant, Leadership, transition_id


class Action(StrEnum):
    REPAIR = "REPAIR"
    REGISTER = "REGISTER"
    IDENTITY = "IDENTITY"
    ROUTE = "ROUTE"
    RETENTION = "RETENTION"
    SCAN = "SCAN"
    WOL = "WOL"
    SSH = "SSH"
    LAUNCH = "LAUNCH"


SHARED = frozenset({Action.REPAIR, Action.REGISTER, Action.IDENTITY, Action.ROUTE, Action.RETENTION})


@dataclass(frozen=True, repr=False)
class Capabilities:
    installation_id: str
    observe: bool
    coordinate: bool
    actions: frozenset[Action]


@dataclass(frozen=True, repr=False)
class Work:
    action: Action
    operation_id: str
    # Shared: pure prepare(snapshot, OwnerGuard) -> exact RecordMutation.
    # External: invoke(Grant, operation_id) -> COMPLETE/NO_WORK/UNKNOWN.
    execute: object


@dataclass(frozen=True, repr=False)
class Receipt:
    action: Action
    operation_id: str
    epoch: int
    outcome: str


@dataclass(frozen=True, repr=False)
class Checkpoint:
    grant: Grant | None = None
    election: ElectionMutation | None = None
    mutation: RecordMutation | None = None
    receipts: tuple[Receipt, ...] = ()


@dataclass(frozen=True, repr=False)
class NativeWatchdogContext:
    leadership: Leadership
    # read() and replace(expected, desired) must be durable, atomic, exclusive
    # to installation_id/binding. No in-memory production implementation here.
    checkpoint: object
    capabilities: object  # local inspection callable; never returns a secret
    clock: object         # trusted commissioned ClockSample provider
    next_work: object     # local scheduler; called only after fresh admission
    commissioning: bool = False
    transition: object = lambda: secrets.token_hex(32)
    status: object = lambda state, reason: None


class NativeWatchdogRuntime:
    def __init__(self, context):
        require(type(context) is NativeWatchdogContext and isinstance(context.leadership, Leadership), "NATIVE_CONTEXT")
        self.context, self.leadership = context, context.leadership
        store = context.checkpoint
        require(store.installation_id == self.leadership.actor
                and store.binding == self.leadership.backend.binding, "LOCAL_INSTALLATION_BINDING")
        require(type(context.commissioning) is bool and all(callable(x) for x in
                (context.capabilities, context.clock, context.next_work, context.transition, context.status)), "NATIVE_PORTS")
        self._active = False
        self._since = None
        self._due = self._renew_at = self._last_clock = None
        self.state, self.reason = "PAUSED", "ROLE_STARTUP"

    def _status(self, active, reason):
        self._active = active
        self.state, self.reason = ("RUNNING" if active else "PAUSED"), reason
        self.context.status(self.state, self.reason)
        return active

    def _caps(self):
        value = self.context.capabilities()
        require(type(value) is Capabilities and value.installation_id == self.leadership.actor
                and type(value.observe) is bool and type(value.coordinate) is bool
                and type(value.actions) is frozenset and all(type(a) is Action for a in value.actions),
                "LOCAL_CAPABILITIES")
        return value

    def _load(self):
        require(self.context.checkpoint.installation_id == self.leadership.actor
                and self.context.checkpoint.binding == self.leadership.backend.binding,
                "LOCAL_INSTALLATION_BINDING")
        state = self.context.checkpoint.read()
        require(type(state) is Checkpoint and (state.grant is None or type(state.grant) is Grant)
                and (state.election is None or type(state.election) is ElectionMutation)
                and (state.mutation is None or type(state.mutation) is RecordMutation)
                and type(state.receipts) is tuple and len(state.receipts) <= len(Action)
                and all(type(r) is Receipt and type(r.action) is Action and transition_id(r.operation_id)
                        and type(r.epoch) is int and r.epoch > 0
                        and r.outcome in {"UNKNOWN", "COMPLETE", "NO_WORK", "SUPERSEDED", "NOT_DISPATCHED"}
                        for r in state.receipts)
                and len({r.action for r in state.receipts}) == len(state.receipts), "LOCAL_CHECKPOINT")
        if state.grant is not None:
            require(state.grant.owner == self.leadership.actor, "LOCAL_GRANT_OWNER")
        for plan in (state.election, state.mutation):
            if plan is not None:
                require(plan.binding == self.leadership.backend.binding
                        and plan.owner.owner == self.leadership.actor, "LOCAL_PLAN_BINDING")
        return state

    def _save(self, before, after):
        require(self.context.checkpoint.replace(before, after) is True
                and self._load() == after, "LOCAL_CHECKPOINT_UNCONFIRMED")
        return after

    def _elect(self, state, plan=None):
        mode = "INSPECT" if plan is None else "START"
        if plan is not None:
            state = self._save(state, replace(state, election=plan))
        plan = state.election
        report = self.leadership.commit(plan, mode=mode)
        if report.outcome == "CONFIRMED":
            grant = (self.leadership.confirmed_grant(plan, report)
                     if plan.action in {"ACQUIRE", "CLAIM_FORCE"} else state.grant)
            return self._save(state, replace(state, election=None, grant=grant))
        if report.outcome == "SUPERSEDED" or (report.outcome in {"CONFLICT", "REJECTED", "UNAVAILABLE"}
                                               and not report.inspect_required):
            return self._save(state, replace(state, election=None, grant=None))
        return state  # Same possibly sent transition remains inspect-only.

    def tick(self):
        try:
            clock = self.context.clock()
            require(type(clock) is ClockSample and clock.monotonic_trusted, "RUNTIME_CLOCK")
            if self._last_clock is not None and clock.monotonic < self._last_clock:
                self._due = self._since = None
                self._last_clock = clock.monotonic
                return self._status(False, "CLOCK_UNCERTAIN")
            self._last_clock = clock.monotonic
            if self._due is not None and clock.monotonic < self._due:
                return self._active
            self._due = clock.monotonic + self.leadership.profile.standby_s
            caps = self._caps()
            if not caps.observe:
                return self._status(False, "AUTHORIZATION")
            state = self._load()
            if state.election is not None:
                # INSPECT never sends a mutation, including after restart.
                state = self._elect(state)
                if state.election is not None:
                    return self._status(False, "LEADERSHIP_UNKNOWN")
            observed = self.leadership.observe(clock)
            if self._since is None or self._since.progress != observed.progress:
                self._since = observed
            if not caps.coordinate:
                return self._status(False, "AUTHORIZATION")
            owned = self.leadership._owns(observed.leader, observed.request, state.grant)
            if owned:
                if self._renew_at is None or clock.monotonic >= self._renew_at:
                    plan = self.leadership.renew(observed, state.grant, transition=self.context.transition())
                    state = self._elect(state, plan)
                    if state.election is not None or state.grant is None:
                        return self._status(False, "LEADERSHIP_UNKNOWN")
                    self._renew_at = clock.monotonic + self.leadership.profile.lease_renew_s
                self._due = clock.monotonic + self.leadership.profile.control_s
                return self._status(True, "ROLE_LOOP")
            if state.grant is not None:
                state = self._save(state, replace(state, grant=None))
            if observed.leader is None:
                if not self.context.commissioning:
                    return self._status(False, "COMMISSIONING_REQUIRED")
                plan = self.leadership.acquire(observed, transition=self.context.transition(), commissioning=True)
            elif (observed.request is not None and observed.request["requester"] == self.leadership.actor
                  and clock.wall_trusted and observed.request["requested_at"] <= clock.utc < observed.request["expires_at"]):
                plan = self.leadership.claim_requested(observed, request_id=observed.request["request_id"])
            elif self.leadership.stale(observed, since=self._since):
                plan = self.leadership.acquire(observed, since=self._since, transition=self.context.transition())
            else:
                return self._status(False, "OLDER_DOG_DETECTED")
            state = self._elect(state, plan)
            if state.grant is None or state.election is not None:
                return self._status(False, "LEADERSHIP_UNKNOWN")
            self._renew_at = clock.monotonic + self.leadership.profile.lease_renew_s
            self._due = clock.monotonic + self.leadership.profile.control_s
            return self._status(True, "ROLE_LOOP")
        except Exception:
            # Provider/store/capability exception bodies are never surfaced.
            return self._status(False, "AUTHORITY_UNAVAILABLE")

    def _admit(self, action=None):
        require(self._active, "ROLE_PAUSED")
        caps = self._caps()
        require(caps.observe and caps.coordinate and (action is None or action in caps.actions), "ACTION_CAPABILITY")
        state = self._load()
        require(state.election is None and state.grant is not None, "LEADERSHIP_UNKNOWN")
        clock = self.context.clock()
        require(type(clock) is ClockSample and clock.monotonic_trusted
                and (self._last_clock is None or clock.monotonic >= self._last_clock), "RUNTIME_CLOCK")
        observed = self.leadership.observe(clock)
        if not self.leadership._owns(observed.leader, observed.request, state.grant):
            self._status(False, "OLDER_DOG_DETECTED")
            raise AuthorityError("OWNER_SUPERSEDED")
        return state, observed.snapshot

    def _receipt(self, state, receipt, *, mutation=...):
        rows = tuple(r for r in state.receipts if r.action != receipt.action) + (receipt,)
        pending = state.mutation if mutation is ... else mutation
        return self._save(state, replace(state, receipts=rows, mutation=pending))

    def perform(self, work):
        require(type(work) is Work and type(work.action) is Action and transition_id(work.operation_id)
                and callable(work.execute), "WORK_SHAPE")
        state, snapshot = self._admit(work.action)
        old = next((r for r in state.receipts if r.action == work.action), None)
        if old is not None and (old.operation_id == work.operation_id or old.outcome == "UNKNOWN"):
            return old.outcome  # A possibly sent external effect is never replayed.
        receipt = Receipt(work.action, work.operation_id, state.grant.epoch, "UNKNOWN")
        if work.action in SHARED:
            if state.mutation is not None:
                return "UNKNOWN"
            plan = work.execute(snapshot, OwnerGuard(state.grant.owner, state.grant.epoch))
            require(type(plan) is RecordMutation and plan.owner == OwnerGuard(state.grant.owner, state.grant.epoch)
                    and plan.binding == self.leadership.backend.binding, "SHARED_PLAN_BINDING")
            state = self._receipt(state, receipt, mutation=plan)
            report = reconcile(self.leadership.backend, plan, mode="START", max_reads=4, max_writes=2)
            if report.outcome == "CONFIRMED":
                self._receipt(state, replace(receipt, outcome="COMPLETE"), mutation=None)
                return "COMPLETE"
            return "UNKNOWN"
        state = self._receipt(state, receipt)
        try:
            # Recheck after local durability, immediately before one external call.
            state, _ = self._admit(work.action)
        except Exception:
            self._receipt(state, replace(receipt, outcome="NOT_DISPATCHED"))
            raise
        try:
            result = work.execute(state.grant, work.operation_id)
        except Exception:
            result = "UNKNOWN"
        if type(result) is not str or result not in {"COMPLETE", "NO_WORK", "UNKNOWN"}:
            result = "UNKNOWN"
        self._receipt(state, replace(receipt, outcome=result))
        return result

    def inspect_shared(self):
        state = self._load()
        if state.mutation is None:
            return "NO_WORK"
        report = reconcile(self.leadership.backend, state.mutation, mode="INSPECT", max_reads=4, max_writes=1)
        if report.outcome in {"CONFIRMED", "SUPERSEDED"}:
            rows = [r for r in state.receipts if r.action in SHARED and r.outcome == "UNKNOWN"]
            require(len(rows) == 1, "LOCAL_MUTATION_RECEIPT")
            self._receipt(state, replace(rows[0], outcome="COMPLETE" if report.outcome == "CONFIRMED" else "SUPERSEDED"), mutation=None)
        return report.outcome

    def cycle(self):
        if not self.tick():
            return
        try:
            self._admit()  # No scheduler/helper construction while standby.
            self.inspect_shared()
            work = self.context.next_work()
            if work is not None:
                self.perform(work)
        except Exception:
            self._status(False, "AUTHORITY_UNAVAILABLE")

    def run(self, stop_event):
        while not stop_event.is_set():
            self.cycle()
            stop_event.wait(self.leadership.profile.control_s if self._active else self.leadership.profile.standby_s)
        self._status(False, "COOPERATIVE_STOP")
        return 0  # Never clear the shared owner or cancel unrelated work.
