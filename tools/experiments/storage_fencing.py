"""RP-008 isolated candidate model, never a production lease implementation.

The model assumes one linearizable authority and an authoritative monotonic clock.
These are explicit hypotheses to compare with real provider capabilities.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json


@dataclass(frozen=True)
class Snapshot:
    domain: str
    revision: int = 0
    owner: str | None = None
    epoch: int = 0
    expires: int = 0
    value: str = "initial"


class AtomicDomain:
    """Ideal single-object CAS and fence check at the same mutation boundary."""
    def __init__(self, domain="synthetic-domain"):
        self.state = Snapshot(domain)
        self.now = 0
        self.reachable = True
        self.clock_certain = True
        self.trace = []

    def read(self):
        return self.state if self.reachable else None

    def acquire(self, observed, actor, ttl=10, *, commissioning_authorized=False):
        if not self.reachable or not self.clock_certain or observed != self.state or ttl <= 0:
            return None
        current = self.state
        if current.owner is None and not commissioning_authorized:
            return None
        if current.owner not in {None, actor} and current.expires > self.now:
            return None
        renewal = current.owner == actor and current.expires > self.now
        self.state = replace(current, owner=actor, revision=current.revision + 1,
                             epoch=current.epoch if renewal else current.epoch + 1,
                             expires=self.now + ttl)
        self.trace.append(("grant", actor, self.state.epoch))
        return self.state

    def authorized(self, actor, epoch):
        return (self.reachable and self.clock_certain and self.state.owner == actor
                and self.state.epoch == epoch and self.now < self.state.expires)

    def mutate(self, observed, actor, epoch, value):
        # One indivisible model transition, not a read followed by a real write.
        if observed != self.state or not self.authorized(actor, epoch):
            self.trace.append(("refused", actor, epoch))
            return False
        self.state = replace(self.state, revision=self.state.revision + 1, value=value)
        self.trace.append(("write", actor, epoch))
        return True


def candidate_report():
    authority = AtomicDomain()
    old = authority.acquire(authority.read(), "candidate-a", commissioning_authorized=True)
    authorized_before_pause = authority.authorized("candidate-a", old.epoch)
    authority.now = 11
    new = authority.acquire(authority.read(), "candidate-b")
    new_write = authority.mutate(authority.read(), "candidate-b", new.epoch, "new-value")
    stale_write = authority.mutate(old, "candidate-a", old.epoch, "stale-value")
    # A separate ordinary file/router has no atomic connection to authority.
    unguarded_external_value = "stale-value" if authorized_before_pause else None
    return {
        "schema_version": 1,
        "scope": "SYNTHETIC_MODEL_ONLY",
        "authority_and_resource_same_atomic_boundary": {
            "new_write_accepted": new_write, "suspended_old_write_accepted": stale_write,
            "preserved_value": authority.state.value,
        },
        "lease_check_then_separate_unfenced_write": {
            "old_check_was_valid": authorized_before_pause,
            "old_effect_after_takeover": unguarded_external_value,
            "safe": False,
        },
        "production_mechanism_selected": False,
    }


if __name__ == "__main__":
    print(json.dumps(candidate_report(), sort_keys=True))
