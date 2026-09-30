"""RP-008 A002 executable design model. Not a production transport or gateway.

One CAS object and durable, authenticated sink gates are explicit assumptions.
No server clock, numeric Docs revision, remote shell or provider access is used.
"""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class State:
    domain: str
    revision: int = 0  # Synthetic CAS identity, never a Google revision format.
    epoch: int = 0
    owner: str | None = None
    phase: str = "UNCOMMISSIONED"
    heartbeat: int = 0
    targets: tuple[str, ...] = ()
    value: str = "initial"


@dataclass(frozen=True)
class Observation:
    snapshot: State
    elapsed: float
    clock_certain: bool = True


@dataclass(frozen=True)
class Receipt:
    domain: str
    target: str
    epoch: int
    owner: str


class Authority:
    def __init__(self, targets=("sink-a",), domain="synthetic-domain"):
        self.state = State(domain, targets=tuple(targets))
        self.reachable = True
        self.cas_requests = 0
        self.lose_next_reply = False

    def read(self):
        return self.state if self.reachable else None

    def _cas(self, expected, desired):
        if not self.reachable or expected != self.state:
            return False
        self.cas_requests += 1
        self.state = replace(desired, revision=expected.revision + 1)
        if self.lose_next_reply:
            self.lose_next_reply = False
            return None  # Caller inspects the same transition, never replays it.
        return True

    def claim(self, observed, actor, *, commissioning=False, silence=None, grace=10):
        if observed is None or observed != self.read() or not actor:
            return False
        if observed.owner is None:
            if not commissioning or observed.phase != "UNCOMMISSIONED":
                return False
        elif observed.owner == actor:
            return False  # Renewal is separate and never grants a new epoch.
        elif (silence is None or not silence.clock_certain or grace <= 0
              or silence.elapsed < grace or silence.snapshot != observed):
            return False
        return self._cas(observed, replace(observed, owner=actor,
                         epoch=observed.epoch + 1, phase="ACTIVATING", heartbeat=0))

    def heartbeat(self, observed, actor, epoch):
        if not self.owns(observed, actor, epoch):
            return False
        return self._cas(observed, replace(observed, heartbeat=observed.heartbeat + 1))

    def owns(self, observed, actor, epoch, *, active=False):
        return (observed is not None and observed == self.read()
                and observed.owner == actor and observed.epoch == epoch
                and observed.phase in (("ACTIVE",) if active else ("ACTIVE", "ACTIVATING")))

    def activate(self, observed, actor, epoch, receipts):
        # Receipt authenticity/durable gate enrollment is assumed, not simulated crypto.
        if not self.owns(observed, actor, epoch) or observed.phase != "ACTIVATING":
            return False
        expected = {Receipt(observed.domain, t, epoch, actor) for t in observed.targets}
        if len(receipts) != len(expected) or set(receipts) != expected:
            return False
        return self._cas(observed, replace(observed, phase="ACTIVE"))

    def publish(self, observed, actor, epoch, value):
        if not self.owns(observed, actor, epoch, active=True):
            return False
        return self._cas(observed, replace(observed, value=value))


class Sink:
    """Indivisible durable fence/admission gate; all effects must pass through it.

The single process dictionary represents durable state and an exclusive lock.
It does NOT qualify an OS lock, filesystem, restart, router, SSH or child process.
"""
    def __init__(self, target="sink-a", domain="synthetic-domain"):
        self.target = target
        self.domain = domain
        self.floor = 0
        self.owner = None
        self.reachable = True
        self.integrity_known = True
        self.jobs = {}
        self.starts = []

    def fence(self, observed):
        # The adapter must authenticate the authority snapshot and caller.
        if (not self.reachable or not self.integrity_known or observed is None
                or observed.domain != self.domain or self.target not in observed.targets
                or observed.phase != "ACTIVATING" or observed.epoch < self.floor
                or (observed.epoch == self.floor and observed.owner != self.owner)):
            return None
        self.floor, self.owner = observed.epoch, observed.owner
        # Revocation is recorded BEFORE waiting for previously admitted effects.
        if any(job[0] < self.floor and job[2] != "FINISHED" for job in self.jobs.values()):
            return None
        return Receipt(self.domain, self.target, self.floor, self.owner)

    def start(self, observed, operation, payload):
        if (not self.reachable or not self.integrity_known or observed is None
                or observed.domain != self.domain or self.target not in observed.targets
                or observed.phase != "ACTIVE" or observed.epoch != self.floor
                or observed.owner != self.owner):
            return "FENCED"
        existing = self.jobs.get(operation)
        if existing:
            return "KNOWN" if existing[1] == payload else "IDENTITY_CONFLICT"
        self.jobs[operation] = (observed.epoch, payload, "RUNNING")
        self.starts.append((observed.epoch, operation))
        return "STARTED"

    def finish(self, operation, *, outcome_known=True):
        epoch, payload, _ = self.jobs[operation]
        self.jobs[operation] = (epoch, payload, "FINISHED" if outcome_known else "UNKNOWN")
