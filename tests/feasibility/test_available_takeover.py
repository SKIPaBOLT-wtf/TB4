"""Current owner policy: stale-record takeover does not wait for old machines."""
from dataclasses import replace
from itertools import permutations

import pytest

from tools.experiments.available_takeover import AvailableAuthority, StableObservation, Work


def active(**kwargs):
    authority = AvailableAuthority(**kwargs)
    assert authority.claim(authority.read(), "actor-a", "commission", now=100, commissioning=True)
    return authority


def test_powered_off_owner_and_unreachable_effect_sink_do_not_block_new_watchdog():
    unresolved = Work("old-operation", "UNKNOWN", "synthetic-digest")
    authority = active(work=(unresolved,))
    old = authority.read()
    assert authority.claim(old, "actor-b", "takeover-b", now=110)
    current = authority.read()
    assert (current.phase, current.owner, current.computer_name, current.epoch) == (
        "ACTIVE", "actor-b", "computer-b", 2)
    assert current.work == (unresolved,)  # No drain/ACK/dead-machine contact occurred.
    assert authority.publish(current, "actor-b", 2, "network-summary")
    assert not authority.publish(old, "actor-a", 1, "stale-overwrite")


@pytest.mark.parametrize("order", list(permutations(("actor-a", "actor-b", "actor-c"))))
def test_first_successful_conditional_claim_wins_even_when_all_read_same_stale_record(order):
    authority = active()
    stale = authority.read()
    accepted = [authority.claim(stale, actor, "claim-" + actor, now=110) for actor in order]
    assert accepted == [True, False, False]
    assert authority.state.owner == order[0]
    assert authority.state.epoch == 2


def test_fresh_incumbent_is_preferred_and_renewal_invalidates_paused_claim():
    authority = active()
    before = authority.read()
    assert not authority.claim(before, "actor-b", "early", now=109)
    assert authority.heartbeat(before, "actor-a", 1, 109)
    assert not authority.claim(before, "actor-b", "old-read", now=111)
    assert not authority.claim(authority.read(), "actor-b", "new-read", now=111)


def test_fresh_start_can_take_over_already_expired_timestamp_without_waiting_a_second_window():
    authority = active()
    first_read = authority.read()
    assert authority.claim(first_read, "actor-b", "first-read-takeover", now=1000)
    assert authority.state.phase == "ACTIVE"


def test_force_button_flag_blocks_old_writes_then_transfers_fresh_role_without_old_ack():
    authority = active()
    old = authority.read()
    assert authority.request_force(old, "actor-b", "request-b", now=101)
    flagged = authority.read()
    assert (flagged.force_request.computer_name, flagged.force_request.expected_epoch) == ("computer-b", 1)
    assert not authority.publish(old, "actor-a", 1, "paused-write")
    assert not authority.publish(flagged, "actor-a", 1, "fresh-read-write")
    assert not authority.heartbeat(flagged, "actor-a", 1, 101)
    assert not authority.may_dispatch(flagged, "actor-a", 1)
    assert authority.claim_requested(flagged, "actor-b", "request-b", now=101)
    assert authority.state.owner == "actor-b"
    assert authority.state.phase == "ACTIVE"


def test_concurrent_force_requests_cannot_overwrite_first_flag():
    authority = active()
    snapshot = authority.read()
    assert authority.request_force(snapshot, "actor-b", "request-b", now=101)
    assert not authority.request_force(snapshot, "actor-c", "request-c", now=101)
    assert not authority.request_force(authority.read(), "actor-c", "request-c", now=101)
    assert not authority.claim_requested(authority.read(), "actor-c", "request-b", now=101)
    assert authority.state.force_request.requester == "actor-b"


def test_crashed_force_requester_has_bounded_flag_and_does_not_block_stale_takeover():
    authority = active()
    assert authority.request_force(authority.read(), "actor-b", "request-b", now=101, ttl=2)
    flagged = authority.read()
    assert not authority.expire_request(flagged, "actor-c", now=102)
    assert not authority.claim_requested(flagged, "actor-b", "request-b", now=103)
    assert authority.expire_request(flagged, "actor-c", now=103)
    assert authority.heartbeat(authority.read(), "actor-a", 1, 103)
    assert authority.request_force(authority.read(), "actor-b", "request-again", now=104)
    assert authority.claim(authority.read(), "actor-c", "expired-owner", now=113)
    assert authority.state.force_request is None
    assert authority.state.owner == "actor-c"


def test_stale_role_claim_and_force_claim_race_has_one_winner():
    authority = active()
    assert authority.request_force(authority.read(), "actor-b", "request-b", now=109)
    flagged = authority.read()
    assert authority.claim(flagged, "actor-c", "stale-c", now=110)
    assert not authority.claim_requested(flagged, "actor-b", "request-b", now=110)
    assert authority.state.owner == "actor-c"


def test_old_owner_with_fresh_read_cannot_adopt_new_epoch_or_replay_old_force_flag():
    authority = active()
    assert authority.claim(authority.read(), "actor-b", "claim-b", now=110)
    current = authority.read()
    assert not authority.publish(current, "actor-a", 1, "stale")
    assert not authority.publish(current, "actor-a", 2, "borrowed-epoch")
    assert not authority.claim_requested(current, "actor-a", "old-request", now=110)


def test_computer_display_name_is_not_ownership_identity():
    authority = active(enrolled={"actor-a": "same-name", "actor-b": "same-name"})
    assert authority.claim(authority.read(), "actor-b", "claim-b", now=110)
    assert authority.state.computer_name == "same-name"
    assert not authority.publish(authority.read(), "actor-a", 2, "wrong-installation")


def test_partition_does_not_grant_offline_shared_write_or_claim():
    authority = active()
    cached = authority.read()
    authority.reachable = False
    assert authority.read() is None
    assert not authority.claim(cached, "actor-b", "partition-claim", now=200)
    assert not authority.publish(cached, "actor-a", 1, "offline")
    authority.reachable = True
    assert authority.claim(authority.read(), "actor-b", "rejoin", now=200)


@pytest.mark.parametrize("now", [None, float("nan"), 90])
def test_uncertain_or_backward_clock_uses_unchanged_progress_window_without_owner_ack(now):
    authority = active()
    observation = authority.read()
    assert not authority.claim(observation, "actor-b", "too-soon", now=now)
    stable = StableObservation(observation.progress(), 10)
    assert authority.claim(observation, "actor-b", "window-claim", now=now, stable=stable)
    assert authority.state.phase == "ACTIVE"


def test_stale_monotonic_observation_cannot_ignore_renewal():
    authority = active()
    old_progress = authority.read().progress()
    assert authority.heartbeat(authority.read(), "actor-a", 1, None)
    stable = StableObservation(old_progress, 100)
    assert not authority.claim(authority.read(), "actor-b", "outdated", now=None, stable=stable)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True])
def test_invalid_stale_threshold_cannot_authorize_claim(value):
    authority = active()
    assert not authority.claim(authority.read(), "actor-b", "bad-threshold", now=1000, timeout=value)


def test_lost_claim_response_is_inspected_by_same_transition_without_new_claim():
    authority = active()
    authority.lose_next_reply = True
    before = authority.mutations
    assert authority.claim(authority.read(), "actor-b", "claim-b", now=110) is None
    observed = authority.read()
    assert (observed.owner, observed.epoch, observed.transition) == ("actor-b", 2, "claim-b")
    assert authority.mutations == before + 1


def test_wrong_domain_and_unenrolled_claimant_are_rejected():
    authority = active()
    assert not authority.claim(replace(authority.read(), domain="another"), "actor-b", "bad", now=110)
    assert not authority.claim(authority.read(), "not-enrolled", "bad", now=110)


def test_external_precheck_has_a_suspension_window_and_must_not_be_called_fenced_execution():
    authority = active()
    old = authority.read()
    dispatch_allowed_before_pause = authority.may_dispatch(old, "actor-a", 1)
    assert authority.claim(authority.read(), "actor-b", "claim-b", now=110)
    # A real effect dispatched after this pause cannot be atomically revoked by Docs.
    assert dispatch_allowed_before_pause is True
    assert authority.state.owner == "actor-b"
    assert not authority.may_dispatch(authority.read(), "actor-a", 1)
    # Shared-state mutation is different: its actual CAS rejects the old snapshot.
    assert not authority.publish(old, "actor-a", 1, "late-shared-write")
