"""Conditional design proofs; provider and real sink qualification remain separate."""
from dataclasses import replace
from itertools import permutations

import pytest

from tools.experiments.docs_authority import Authority, Observation, Receipt, Sink


def active(targets=("sink-a",)):
    authority = Authority(targets)
    sinks = [Sink(t) for t in targets]
    assert authority.claim(authority.read(), "actor-a", commissioning=True)
    grant = authority.read()
    assert authority.activate(grant, "actor-a", 1, [s.fence(grant) for s in sinks])
    return authority, sinks


def takeover(authority, actor="actor-b"):
    snapshot = authority.read()
    return authority.claim(snapshot, actor, silence=Observation(snapshot, 10))


@pytest.mark.parametrize("order", list(permutations(("actor-a", "actor-b", "actor-c"))))
def test_simultaneous_commissioners_only_one_cas_winner(order):
    authority = Authority()
    initial = authority.read()
    results = [authority.claim(initial, actor, commissioning=True) for actor in order]
    assert results == [True, False, False]
    assert authority.state.phase == "ACTIVATING"
    assert authority.state.owner == order[0]


def test_no_implicit_commissioning_or_same_name_domain_adoption():
    authority = Authority()
    assert not authority.claim(authority.read(), "actor-a")
    assert not authority.claim(replace(authority.read(), domain="different-domain"),
                               "actor-a", commissioning=True)
    assert authority.state.epoch == 0


def test_fresh_incumbent_and_heartbeat_change_defeat_delayed_challenge():
    authority, _ = active()
    stale = authority.read()
    assert not authority.claim(stale, "actor-b")
    assert not authority.claim(stale, "actor-b", silence=Observation(stale, 9))
    assert authority.heartbeat(stale, "actor-a", 1)
    assert not authority.claim(stale, "actor-b", silence=Observation(stale, 100))
    current = authority.read()
    assert not authority.claim(current, "actor-b", silence=Observation(stale, 100))


def test_clock_uncertainty_and_authority_partition_refuse_takeover_and_writes():
    authority, _ = active()
    current = authority.read()
    assert not authority.claim(current, "actor-b", silence=Observation(current, 100, False))
    authority.reachable = False
    assert not authority.claim(current, "actor-b", silence=Observation(current, 100))
    assert not authority.publish(current, "actor-a", 1, "unsafe")


def test_takeover_does_not_need_authoritative_wall_clock_but_needs_all_sink_barriers():
    authority, sinks = active(("sink-a", "sink-b"))
    old = authority.read()
    assert takeover(authority)
    grant = authority.read()
    first = sinks[0].fence(grant)
    assert not authority.activate(grant, "actor-b", 2, [first])
    assert not authority.activate(grant, "actor-b", 2, [first, first])
    assert sinks[0].start(grant, "new-op", "synthetic") == "FENCED"
    second = sinks[1].fence(grant)
    assert authority.activate(grant, "actor-b", 2, [first, second])
    assert all(s.start(old, "stale-op", "synthetic") == "FENCED" for s in sinks)
    assert not authority.publish(authority.read(), "actor-a", 1, "stale")


def test_suspended_old_actor_is_rejected_even_after_fresh_authority_read():
    authority, (sink,) = active()
    old = authority.read()
    assert takeover(authority)
    grant = authority.read()
    receipt = sink.fence(grant)
    assert authority.activate(grant, "actor-b", 2, [receipt])
    assert not authority.publish(old, "actor-a", 1, "old")
    assert not authority.publish(authority.read(), "actor-a", 1, "fresh-but-not-owner")
    assert sink.start(old, "old-op", "synthetic") == "FENCED"
    assert sink.fence(replace(old, phase="ACTIVATING")) is None
    assert sink.floor == 2


@pytest.mark.parametrize("known", [False, True])
def test_previously_started_effect_must_finish_with_known_outcome_before_activation(known):
    authority, (sink,) = active()
    old = authority.read()
    assert sink.start(old, "old-op", "synthetic") == "STARTED"
    assert takeover(authority)
    grant = authority.read()
    assert sink.fence(grant) is None
    assert sink.floor == 2  # New stale starts are already refused while draining.
    assert sink.start(old, "another-op", "synthetic") == "FENCED"
    sink.finish("old-op", outcome_known=known)
    receipt = sink.fence(grant)
    assert (receipt is not None) is known
    if known:
        assert authority.activate(grant, "actor-b", 2, [receipt])
    else:
        assert authority.state.phase == "ACTIVATING"


@pytest.mark.parametrize("fault", ["unreachable", "lost-durable-state", "wrong-domain"])
def test_unqualified_or_unreachable_sink_cannot_acknowledge(fault):
    authority, (sink,) = active()
    assert takeover(authority)
    if fault == "unreachable":
        sink.reachable = False
    elif fault == "lost-durable-state":
        sink.integrity_known = False
    else:
        sink.domain = "another-domain"
    assert sink.fence(authority.read()) is None
    assert not authority.activate(authority.read(), "actor-b", 2, [])


def test_interrupted_activation_then_higher_epoch_rejects_old_receipts_and_fence():
    authority, (sink,) = active()
    assert takeover(authority)
    old_grant = authority.read()
    old_receipt = sink.fence(old_grant)
    assert takeover(authority, "actor-c")
    new_grant = authority.read()
    receipt = sink.fence(new_grant)
    assert not authority.activate(old_grant, "actor-b", 2, [old_receipt])
    assert not authority.activate(new_grant, "actor-c", 3, [old_receipt])
    assert sink.fence(old_grant) is None
    assert authority.activate(new_grant, "actor-c", 3, [receipt])


def test_applied_claim_lost_reply_is_inspected_without_reissuing_cas():
    authority, _ = active()
    authority.lose_next_reply = True
    count = authority.cas_requests
    assert takeover(authority) is None
    observed = authority.read()
    assert (observed.owner, observed.epoch, observed.phase) == ("actor-b", 2, "ACTIVATING")
    assert authority.cas_requests == count + 1
    assert not authority.claim(observed, "actor-b", silence=Observation(observed, 20))


def test_effect_identity_survives_takeover_no_payload_substitution_or_reexecution():
    authority, (sink,) = active()
    assert sink.start(authority.read(), "same-op", "payload-one") == "STARTED"
    sink.finish("same-op")
    assert takeover(authority)
    grant = authority.read()
    assert authority.activate(grant, "actor-b", 2, [sink.fence(grant)])
    assert sink.start(authority.read(), "same-op", "payload-one") == "KNOWN"
    assert sink.start(authority.read(), "same-op", "different-payload") == "IDENTITY_CONFLICT"
    assert len(sink.starts) == 1


@pytest.mark.parametrize("pause_point", ["before-claim", "after-claim", "after-fence", "after-active"])
def test_all_old_start_interleavings_are_drained_or_rejected_before_new_active(pause_point):
    authority, (sink,) = active()
    old = authority.read()
    if pause_point == "before-claim":
        assert sink.start(old, "old-op", "synthetic") == "STARTED"
    assert takeover(authority)
    grant = authority.read()
    if pause_point == "after-claim":
        assert sink.start(old, "old-op", "synthetic") == "STARTED"
    receipt = sink.fence(grant)
    if pause_point == "after-fence":
        assert sink.start(old, "old-op", "synthetic") == "FENCED"
    if receipt is None:
        assert authority.state.phase == "ACTIVATING"
        sink.finish("old-op")
        receipt = sink.fence(grant)
    assert authority.activate(grant, "actor-b", 2, [receipt])
    if pause_point == "after-active":
        assert sink.start(old, "old-op", "synthetic") == "FENCED"
    assert all(job[2] == "FINISHED" for job in sink.jobs.values())
    assert sink.start(authority.read(), "new-op", "synthetic") == "STARTED"


def test_stale_document_readback_does_not_authorize_a_later_cas():
    authority, _ = active()
    stale = authority.read()
    assert authority.publish(stale, "actor-a", 1, "new-value")
    assert not authority.publish(stale, "actor-a", 1, "lost-update")
    assert authority.state.value == "new-value"
