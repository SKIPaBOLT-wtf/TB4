"""RP-008 A003 owner-directed availability model, not an installed runtime.

Atomic shared writes are fenced. Already-dispatched external effects are separate
records and do not form a global role-activation barrier.
"""
from dataclasses import dataclass, replace
from math import isfinite


@dataclass(frozen=True)
class ForceRequest:
    request_id: str
    requester: str
    computer_name: str
    expected_epoch: int
    expires_at: float


@dataclass(frozen=True)
class Work:
    operation: str
    state: str
    payload_digest: str


@dataclass(frozen=True)
class Record:
    domain: str
    revision: int = 0  # Synthetic only; real Docs revisions are opaque.
    epoch: int = 0
    owner: str | None = None
    computer_name: str | None = None
    heartbeat_at: float | None = None
    heartbeat_sequence: int = 0
    phase: str = "UNCOMMISSIONED"
    force_request: ForceRequest | None = None
    transition: str | None = None
    value: str = "initial"
    work: tuple[Work, ...] = ()

    def progress(self):
        return self.domain, self.owner, self.epoch, self.heartbeat_sequence, self.heartbeat_at


@dataclass(frozen=True)
class StableObservation:
    progress: tuple
    monotonic_elapsed: float
    clock_certain: bool = True


def valid_time(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


class AvailableAuthority:
    def __init__(self, enrolled=None, *, domain="synthetic-domain", work=()):
        self.enrolled = enrolled or {"actor-a": "computer-a", "actor-b": "computer-b",
                                     "actor-c": "computer-c"}
        self.state = Record(domain, work=tuple(work))
        self.reachable = True
        self.lose_next_reply = False
        self.mutations = 0

    def read(self):
        return self.state if self.reachable else None

    def _cas(self, observed, desired):
        if observed is None or observed != self.read():
            return False
        self.state = replace(desired, revision=observed.revision + 1)
        self.mutations += 1
        if self.lose_next_reply:
            self.lose_next_reply = False
            return None
        return True

    def stale(self, observed, now, timeout, stable=None):
        if not valid_time(timeout) or timeout <= 0 or observed is None:
            return False
        if (valid_time(now) and valid_time(observed.heartbeat_at)
                and now >= observed.heartbeat_at):
            return now - observed.heartbeat_at >= timeout
        return (stable is not None and stable.clock_certain
                and stable.progress == observed.progress()
                and valid_time(stable.monotonic_elapsed)
                and stable.monotonic_elapsed >= timeout)

    def claim(self, observed, actor, transition, *, now, timeout=10,
              commissioning=False, stable=None):
        if observed is None or observed != self.read() or actor not in self.enrolled or not transition:
            return False
        if observed.owner is None:
            if not commissioning or observed.phase != "UNCOMMISSIONED":
                return False
        elif not self.stale(observed, now, timeout, stable):
            return False
        return self._cas(observed, replace(observed, owner=actor,
                         computer_name=self.enrolled[actor], epoch=observed.epoch + 1,
                         phase="ACTIVE", heartbeat_at=(now if valid_time(now) and
                         (observed.heartbeat_at is None or now >= observed.heartbeat_at) else None),
                         heartbeat_sequence=0, force_request=None, transition=transition))

    def owns(self, observed, actor, epoch):
        return (observed is not None and observed == self.read()
                and observed.phase == "ACTIVE" and observed.owner == actor
                and observed.epoch == epoch and observed.force_request is None)

    def heartbeat(self, observed, actor, epoch, now):
        if not self.owns(observed, actor, epoch):
            return False
        return self._cas(observed, replace(observed,
                         heartbeat_at=(now if valid_time(now) and
                         (observed.heartbeat_at is None or now >= observed.heartbeat_at) else None),
                         heartbeat_sequence=observed.heartbeat_sequence + 1))

    def publish(self, observed, actor, epoch, value):
        if not self.owns(observed, actor, epoch):
            return False
        return self._cas(observed, replace(observed, value=value))

    def request_force(self, observed, actor, request_id, *, now, ttl=5):
        if (observed is None or observed != self.read() or actor not in self.enrolled
                or actor == observed.owner or observed.phase != "ACTIVE"
                or observed.force_request is not None or not request_id
                or not valid_time(now) or not valid_time(ttl) or ttl <= 0):
            return False
        request = ForceRequest(request_id, actor, self.enrolled[actor], observed.epoch, now + ttl)
        return self._cas(observed, replace(observed, force_request=request))

    def claim_requested(self, observed, actor, request_id, *, now):
        if observed is None or observed != self.read() or not valid_time(now):
            return False
        request = observed.force_request
        if (request is None or request.requester != actor or request.request_id != request_id
                or request.expected_epoch != observed.epoch or now >= request.expires_at):
            return False
        # No acknowledgement, shutdown, drain or response from the former owner.
        return self._cas(observed, replace(observed, owner=actor,
                         computer_name=request.computer_name, epoch=observed.epoch + 1,
                         phase="ACTIVE", heartbeat_at=now, heartbeat_sequence=0,
                         force_request=None, transition=request_id))

    def expire_request(self, observed, actor, *, now):
        if (observed is None or observed != self.read() or actor not in self.enrolled
                or observed.force_request is None or not valid_time(now)
                or now < observed.force_request.expires_at):
            return False
        return self._cas(observed, replace(observed, force_request=None))

    def may_dispatch(self, observed, actor, epoch):
        # Mandatory fresh cooperative check; not an atomic external effect fence.
        return self.owns(observed, actor, epoch)
