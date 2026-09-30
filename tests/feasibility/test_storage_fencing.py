"""Counterexamples are passing tests, not claims that the candidate is safe."""
from itertools import permutations

import pytest

from tb4.drive.google_backend import GoogleDriveBackend
from tools.experiments.storage_fencing import AtomicDomain, candidate_report


class Request:
    def __init__(self, action):
        self.action = action

    def execute(self):
        return self.action()


class SyntheticDrive:
    """Two-phase scheduling around the real adapter's unconditional write call."""
    def __init__(self):
        self.metadata = {"id": "synthetic-object", "name": "unclaimed", "parents": ["synthetic-root"],
                         "mimeType": "text/plain", "version": "1"}
        self.body = b"version-one-body"
        self.before_update = None
        self.before_media = None
        self.updates = []

    def files(self):
        return self

    def get(self, **kwargs):
        return Request(lambda: dict(self.metadata))

    def get_media(self, **kwargs):
        def read():
            if self.before_media:
                callback, self.before_media = self.before_media, None
                callback()
            return self.body
        return Request(read)

    def update(self, **kwargs):
        self.updates.append(kwargs)

        def apply():
            if self.before_update:
                callback, self.before_update = self.before_update, None
                callback()
            self.metadata.update(kwargs.get("body", {}))
            self.metadata["version"] = str(int(self.metadata["version"]) + 1)
            return dict(self.metadata)
        return Request(apply)


def test_current_google_adapter_two_successful_claims_despite_same_expected_version():
    drive = SyntheticDrive()
    adapter = GoogleDriveBackend(drive)
    observations = []

    def candidate_b_runs_while_a_suspended_after_precheck():
        result = adapter.rename("synthetic-object", "candidate-b", expected_version_token="1")
        assert result.ok
        observations.append(adapter.get_metadata("synthetic-object").value.name)

    drive.before_update = candidate_b_runs_while_a_suspended_after_precheck
    result = adapter.rename("synthetic-object", "candidate-a", expected_version_token="1")
    assert result.ok
    observations.append(adapter.get_metadata("synthetic-object").value.name)
    assert observations == ["candidate-b", "candidate-a"]
    assert drive.metadata["version"] == "3"
    assert adapter.capabilities.atomic_version_precondition is False
    # Neither actual update request conveys an atomic version or ownership fence.
    assert all(set(call) == {"fileId", "body", "fields", "supportsAllDrives"} for call in drive.updates)


def test_metadata_and_body_read_can_span_versions_in_actual_adapter():
    drive = SyntheticDrive()
    adapter = GoogleDriveBackend(drive)

    def intervening_write():
        drive.metadata["version"] = "2"
        drive.body = b"version-two-body"

    drive.before_media = intervening_write
    result = adapter.read_text("synthetic-object")
    assert result.ok
    assert result.value.metadata.version_token == "1"
    assert result.value.text == "version-two-body"


@pytest.mark.parametrize("order", list(permutations(["candidate-a", "candidate-b", "candidate-c"])))
def test_ideal_cas_simultaneous_starts_have_one_winner(order):
    domain = AtomicDomain()
    shared_observation = domain.read()
    results = [domain.acquire(shared_observation, actor, commissioning_authorized=True) for actor in order]
    assert sum(result is not None for result in results) == 1
    assert domain.state.owner == order[0] and domain.state.epoch == 1


def test_commissioning_needs_explicit_authority_before_first_claim():
    domain = AtomicDomain()
    assert domain.acquire(domain.read(), "candidate-a") is None
    assert domain.state.revision == 0


def test_valid_incumbent_wins_and_wallclock_age_is_not_an_input():
    domain = AtomicDomain()
    old = domain.acquire(domain.read(), "candidate-a", commissioning_authorized=True)
    assert domain.acquire(domain.read(), "candidate-b") is None
    renewed = domain.acquire(domain.read(), "candidate-a")
    assert renewed.epoch == old.epoch and renewed.revision > old.revision


def test_delayed_observation_cannot_claim_or_overwrite_new_generation():
    domain = AtomicDomain()
    stale = domain.read()
    old = domain.acquire(stale, "candidate-a", commissioning_authorized=True)
    assert domain.acquire(stale, "candidate-b", commissioning_authorized=True) is None
    assert not domain.mutate(stale, "candidate-a", old.epoch, "stale")


def test_partition_refuses_renewal_and_protected_mutation():
    domain = AtomicDomain()
    old = domain.acquire(domain.read(), "candidate-a", commissioning_authorized=True)
    domain.reachable = False
    assert domain.read() is None
    assert domain.acquire(old, "candidate-a") is None
    assert not domain.mutate(old, "candidate-a", old.epoch, "partition-write")
    assert domain.state.value == "initial"


def test_suspended_incumbent_is_fenced_after_takeover_even_with_fresh_read():
    domain = AtomicDomain()
    old = domain.acquire(domain.read(), "candidate-a", commissioning_authorized=True)
    domain.now = 11
    new = domain.acquire(domain.read(), "candidate-b")
    assert new.epoch > old.epoch
    assert domain.mutate(domain.read(), "candidate-b", new.epoch, "new-value")
    assert not domain.mutate(domain.read(), "candidate-a", old.epoch, "old-value")
    assert domain.state.value == "new-value"


def test_lease_loss_and_clock_uncertainty_stop_at_atomic_effect_boundary():
    domain = AtomicDomain()
    old = domain.acquire(domain.read(), "candidate-a", commissioning_authorized=True)
    domain.now = 10
    assert not domain.mutate(old, "candidate-a", old.epoch, "expired")
    domain.clock_certain = False
    assert domain.acquire(domain.read(), "candidate-b") is None


def test_equal_revision_in_another_domain_does_not_authorize_claim():
    first, second = AtomicDomain("synthetic-one"), AtomicDomain("synthetic-two")
    assert second.acquire(first.read(), "candidate-a", commissioning_authorized=True) is None


def test_cas_lease_alone_does_not_fence_separate_drive_or_router_write():
    report = candidate_report()
    assert report["authority_and_resource_same_atomic_boundary"] == {
        "new_write_accepted": True, "suspended_old_write_accepted": False, "preserved_value": "new-value"}
    assert report["lease_check_then_separate_unfenced_write"]["old_check_was_valid"] is True
    assert report["lease_check_then_separate_unfenced_write"]["old_effect_after_takeover"] == "stale-value"
    assert report["production_mechanism_selected"] is False


def test_local_locks_in_two_unsynchronized_replicas_do_not_create_one_authority():
    first, second = AtomicDomain(), AtomicDomain()
    left = first.acquire(first.read(), "candidate-a", commissioning_authorized=True)
    right = second.acquire(second.read(), "candidate-b", commissioning_authorized=True)
    assert left is not None and right is not None
    assert first.state.owner != second.state.owner  # Same domain string is not shared atomic storage.
