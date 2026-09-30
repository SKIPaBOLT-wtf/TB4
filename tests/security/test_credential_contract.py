from __future__ import annotations

import copy
import json
import re

import pytest

from tb4.credential_contract import (CredentialContractError, CredentialResolver, Inspection, Outcome, Purpose)

INSTALLATION = "00000000-0000-4000-8000-000000000011"
STANDBY = "00000000-0000-4000-8000-000000000012"
TARGET = "00000000-0000-4000-8000-000000000013"
TRUST = "a" * 64
CANARY = "synthetic-material-never-returned"


class FixtureStore:
    """No real store/SSH. Only this fixture can see its synthetic material."""
    def __init__(self, installation=INSTALLATION):
        self.installation_id = installation
        self.state = Outcome.READY
        self.version = 1
        self.permissions = True
        self.approved = True
        self.material = CANARY
        self.inspections = 0
        self.attempts = 0
        self.executions = 0
        self.mode = "normal"
        self.now = 100

    def inspect(self, binding):
        self.inspections += 1
        if self.mode == "inspect_exception":
            raise RuntimeError(self.material)
        return Inspection(self.state, self.version, self.approved, self.permissions)

    def use_fixed(self, binding, purpose, *, expected_version):
        self.attempts += 1
        if self.mode == "permission_race":
            self.permissions = False
        if self.mode == "version_race":
            self.version += 1
        if self.mode == "expiry_race":
            self.now = binding.expires_at
        if self.now >= binding.expires_at:
            return Outcome.EXPIRED
        if not self.permissions or not self.approved or expected_version != self.version or self.state is not Outcome.READY:
            return Outcome.DENIED
        assert type(purpose) is Purpose
        self.executions += 1
        if self.mode == "lost_ack":
            raise RuntimeError(self.material)
        if self.mode == "raw_result":
            return self.material
        return Outcome.SUCCEEDED


def setup(*, purposes=frozenset({Purpose.FETCHER_STATUS}), expires=200):
    store = FixtureStore()
    resolver = CredentialResolver(INSTALLATION, store, clock=lambda: store.now)
    handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator="protected-fixture-slot",
                             purposes=purposes, expires_at=expires, owner_authorized=True)
    return resolver, store, handle


def request(purpose=Purpose.FETCHER_STATUS, target=TARGET, trust=TRUST):
    return dict(purpose=purpose, target_id=target, target_trust=trust)


def test_handle_is_random_opaque_and_reports_never_return_binding_or_material(capsys):
    resolver, store, handle = setup()
    assert re.fullmatch(r"cr_[0-9a-f]{32}", handle)
    capability = resolver.capability(handle, **request()).report()
    use = resolver.invoke(handle, **request()).report()
    assert capability == dict(configured=True, available=True, outcome="READY")
    assert use == dict(outcome="SUCCEEDED", retry_automatically=False, inspection_required=False)
    body = json.dumps([capability, use]) + repr(resolver._bindings[handle])
    assert all(value not in body for value in (CANARY, handle, TARGET, TRUST, INSTALLATION, "protected-fixture-slot"))
    assert not capsys.readouterr().out and not capsys.readouterr().err
    assert store.executions == 1


@pytest.mark.parametrize("state", [Outcome.ABSENT, Outcome.LOCKED, Outcome.EXPIRED, Outcome.REVOKED, Outcome.DENIED, Outcome.STORE_UNAVAILABLE])
def test_unavailable_store_states_are_explicit_and_never_execute(state):
    resolver, store, handle = setup()
    store.state = state
    assert resolver.capability(handle, **request()).outcome is state
    assert resolver.invoke(handle, **request()).outcome is state
    assert store.attempts == store.executions == 0


def test_handle_target_trust_and_purpose_are_independent_gates():
    resolver, store, handle = setup()
    assert resolver.capability("absent", **request()).outcome is Outcome.ABSENT
    assert resolver.invoke(handle, **request(target=STANDBY)).outcome is Outcome.MISMATCHED
    assert resolver.invoke(handle, **request(trust="b" * 64)).outcome is Outcome.MISMATCHED
    assert resolver.invoke(handle, **request(purpose=Purpose.FETCHER_START)).outcome is Outcome.DENIED
    assert resolver.invoke(handle, **request(purpose="arbitrary private shell command")).outcome is Outcome.DENIED
    assert store.attempts == 0


@pytest.mark.parametrize("field", ["permissions", "approved"])
def test_unverified_permissions_or_store_block_capability_and_use(field):
    resolver, store, handle = setup()
    setattr(store, field, False)
    assert resolver.capability(handle, **request()).outcome is Outcome.DENIED
    assert resolver.invoke(handle, **request()).outcome is Outcome.DENIED
    assert store.attempts == 0


@pytest.mark.parametrize("mode", ["permission_race", "version_race"])
def test_adapter_must_recheck_permissions_and_generation_at_use(mode):
    resolver, store, handle = setup()
    assert resolver.capability(handle, **request()).available
    store.mode = mode
    assert resolver.invoke(handle, **request()).outcome is Outcome.DENIED
    assert store.attempts == 1 and store.executions == 0


def test_adapter_rechecks_expiry_after_successful_inspection():
    resolver, store, handle = setup()
    store.mode = "expiry_race"
    assert resolver.invoke(handle, **request()).outcome is Outcome.EXPIRED
    assert store.attempts == 1 and store.executions == 0


@pytest.mark.parametrize("mode", ["inspect_exception", "lost_ack", "raw_result"])
def test_provider_faults_and_raw_results_never_echo_or_retry(mode, capsys):
    resolver, store, handle = setup(purposes=frozenset({Purpose.FETCHER_START}))
    store.mode = mode
    report = resolver.invoke(handle, **request(Purpose.FETCHER_START)).report()
    assert report["outcome"] == ("STORE_UNAVAILABLE" if mode == "inspect_exception" else "UNKNOWN")
    assert report["retry_automatically"] is False
    assert report["inspection_required"] is (mode != "inspect_exception")
    assert store.attempts <= 1 and store.executions <= 1
    assert CANARY not in json.dumps(report)
    assert capsys.readouterr().out == ""


def test_expiry_boundary_revocation_and_local_rotation_preserve_unrelated_bindings():
    resolver, store, handle = setup(purposes=frozenset({Purpose.FETCHER_STATUS, Purpose.FETCHER_START}))
    unrelated = resolver.enroll(target_id=STANDBY, target_trust=TRUST, store_locator="unrelated-slot",
                                purposes=frozenset({Purpose.FETCHER_STATUS}), expires_at=200, owner_authorized=True)
    new = resolver.rotate(handle, new_store_locator="replacement-slot", expires_at=300, owner_authorized=True)
    assert new != handle and resolver.capability(handle, **request()).outcome is Outcome.REVOKED
    assert resolver._bindings[new].generation == 2
    assert resolver.capability(unrelated, **request(target=STANDBY)).available
    assert resolver.capability(new, **request(Purpose.FETCHER_START)).available
    resolver.revoke(new, owner_authorized=True)
    assert resolver.invoke(new, **request()).outcome is Outcome.REVOKED
    expired, expired_store, exp = setup(expires=100)
    assert expired.invoke(exp, **request()).outcome is Outcome.EXPIRED
    assert expired_store.attempts == 0


def test_failed_rotation_drops_only_candidate_and_preserves_old_binding():
    resolver, store, handle = setup()
    before = copy.deepcopy(resolver._bindings)
    with pytest.raises(CredentialContractError, match="ROTATION_CANDIDATE_UNAVAILABLE"):
        resolver.rotate(handle, new_store_locator="candidate-slot", expires_at=100, owner_authorized=True)
    assert resolver._bindings == before and resolver.capability(handle, **request()).available


def test_enrollment_and_lifecycle_need_explicit_local_authorization():
    resolver, store, handle = setup()
    for action in (lambda: resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator="slot",
                    purposes=frozenset({Purpose.FETCHER_START}), expires_at=200, owner_authorized=False),
                   lambda: resolver.rotate(handle, new_store_locator="slot", expires_at=200, owner_authorized=False),
                   lambda: resolver.revoke(handle, owner_authorized=False)):
        with pytest.raises(CredentialContractError, match="NOT_AUTHORIZED"):
            action()
    assert resolver.capability(handle, **request()).available and store.attempts == 0


def test_standby_advertises_its_own_store_and_never_imports_incumbent_identity():
    incumbent, primary_store, handle = setup()
    standby_store = FixtureStore(STANDBY)
    standby = CredentialResolver(STANDBY, standby_store, clock=lambda: 100)
    assert incumbent.capability(handle, **request()).available
    assert standby.capability(handle, **request()).outcome is Outcome.ABSENT
    standby._bindings[handle] = incumbent._bindings[handle]  # Simulated corrupt persisted cache.
    assert standby.capability(handle, **request()).report() == dict(configured=False, available=False, outcome="MISMATCHED")
    assert standby.invoke(handle, **request()).outcome is Outcome.MISMATCHED
    assert standby_store.inspections == standby_store.attempts == 0
    with pytest.raises(CredentialContractError, match="STORE_INSTALLATION_MISMATCH"):
        CredentialResolver(STANDBY, primary_store, clock=lambda: 100)


def test_store_identity_failure_cannot_echo_provider_text():
    class BrokenStore:
        @property
        def installation_id(self):
            raise RuntimeError(CANARY)
    with pytest.raises(CredentialContractError, match="STORE_INSTALLATION_MISMATCH") as error:
        CredentialResolver(INSTALLATION, BrokenStore(), clock=lambda: 100)
    assert CANARY not in str(error.value)
