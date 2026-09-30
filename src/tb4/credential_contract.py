"""Installation-local credential-use contract; never resolve material to a caller.

No OS store/key-file adapter is installed here. Trusted local adapters implement
permission-checked fixed use; public outputs contain only enumerated capability
and use outcomes. Production adapters and durable operation tracking are later
commissioning gates, not claims made by these synthetic contract fixtures.
"""
from __future__ import annotations

import re
import secrets
import threading
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class Purpose(StrEnum):
    FETCHER_STATUS = "FETCHER_STATUS"
    FETCHER_START = "FETCHER_START"


class Outcome(StrEnum):
    READY = "READY"
    ABSENT = "ABSENT"
    LOCKED = "LOCKED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    MISMATCHED = "MISMATCHED"
    DENIED = "DENIED"
    STORE_UNAVAILABLE = "STORE_UNAVAILABLE"
    SUCCEEDED = "SUCCEEDED"
    UNKNOWN = "UNKNOWN"


class CredentialContractError(ValueError):
    """Fixed diagnostics only."""


def require(condition, code):
    if not condition:
        raise CredentialContractError(code)


def identity(value):
    try:
        return type(value) is str and str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def same_store(store, installation_id):
    try:
        return type(store.installation_id) is str and store.installation_id == installation_id
    except Exception:
        return False


@dataclass(frozen=True, slots=True)
class Binding:
    # Even local exception/repr surfaces must not echo protected binding details.
    handle: str = field(repr=False)
    installation_id: str = field(repr=False)
    target_id: str = field(repr=False)
    target_trust: str = field(repr=False)
    store_locator: str = field(repr=False)
    purposes: frozenset[Purpose]
    expires_at: int = field(repr=False)
    generation: int = 1
    revoked: bool = False


@dataclass(frozen=True, slots=True)
class Inspection:
    outcome: Outcome
    # Version is provider-local and never projected to an LLM/report.
    version: int = field(default=0, repr=False)
    approved_store: bool = False
    permissions_verified: bool = False


class LocalStore(Protocol):
    installation_id: str

    def inspect(self, binding: Binding) -> Inspection: ...

    def use_fixed(self, binding: Binding, purpose: Purpose, *, expected_version: int) -> Outcome:
        """Recheck store state/version/permissions/expiry/trust with local use.

        The adapter maps the enum to a commissioned fixed helper. There is no
        arbitrary command or returned credential/payload/console-output argument.
        """
        ...


@dataclass(frozen=True, slots=True)
class Capability:
    configured: bool
    available: bool
    outcome: Outcome

    def report(self):
        return dict(configured=self.configured, available=self.available, outcome=self.outcome.value)


@dataclass(frozen=True, slots=True)
class UseResult:
    outcome: Outcome

    def report(self):
        return dict(outcome=self.outcome.value, retry_automatically=False,
                    inspection_required=self.outcome is Outcome.UNKNOWN)


class CredentialResolver:
    """Local binding lifecycle and one fixed-use attempt per call.

    Enrollment/rotation authorization is supplied by trusted local commissioning,
    never a remote request field. Each instance owns only its local installation.
    """
    def __init__(self, installation_id, store: LocalStore, *, clock):
        require(identity(installation_id), "INSTALLATION_ID_INVALID")
        require(same_store(store, installation_id), "STORE_INSTALLATION_MISMATCH")
        self._installation_id = installation_id
        self._store = store
        self._clock = clock
        self._bindings = {}
        self._lock = threading.RLock()

    def enroll(self, *, target_id, target_trust, store_locator, purposes, expires_at, owner_authorized):
        require(owner_authorized is True, "ENROLLMENT_NOT_AUTHORIZED")
        require(identity(target_id), "TARGET_ID_INVALID")
        require(type(target_trust) is str and re.fullmatch(r"[0-9a-f]{64}", target_trust), "TARGET_TRUST_INVALID")
        require(type(store_locator) is str and 0 < len(store_locator) <= 1024, "LOCAL_STORE_REFERENCE_INVALID")
        require(type(purposes) is frozenset and purposes and all(type(p) is Purpose for p in purposes), "PURPOSE_INVALID")
        require(type(expires_at) is int and 0 <= expires_at <= 10**12, "EXPIRY_INVALID")
        with self._lock:
            handle = "cr_" + secrets.token_hex(16)
            require(handle not in self._bindings, "HANDLE_COLLISION")
            self._bindings[handle] = Binding(handle, self._installation_id, target_id, target_trust,
                                             store_locator, purposes, expires_at)
            return handle  # Protected local reference, never returned by report().

    def _inspect(self, handle, purpose, target_id, target_trust):
        if type(handle) is not str or not re.fullmatch(r"cr_[0-9a-f]{32}", handle):
            return None, Inspection(Outcome.ABSENT)
        binding = self._bindings.get(handle)
        if binding is None:
            return None, Inspection(Outcome.ABSENT)
        if (not identity(target_id) or type(target_trust) is not str
                or binding.installation_id != self._installation_id or not same_store(self._store, self._installation_id)
                or target_id != binding.target_id or target_trust != binding.target_trust):
            return binding, Inspection(Outcome.MISMATCHED)
        if type(purpose) is not Purpose or purpose not in binding.purposes:
            return binding, Inspection(Outcome.DENIED)
        if binding.revoked:
            return binding, Inspection(Outcome.REVOKED)
        try:
            now = self._clock()
            if type(now) is not int or not 0 <= now <= 10**12:
                return binding, Inspection(Outcome.STORE_UNAVAILABLE)
            if now >= binding.expires_at:
                return binding, Inspection(Outcome.EXPIRED)
            inspection = self._store.inspect(binding)
            if type(inspection) is not Inspection or type(inspection.outcome) is not Outcome:
                return binding, Inspection(Outcome.STORE_UNAVAILABLE)
            if inspection.outcome not in {Outcome.READY, Outcome.ABSENT, Outcome.LOCKED, Outcome.EXPIRED,
                                          Outcome.REVOKED, Outcome.DENIED, Outcome.STORE_UNAVAILABLE}:
                return binding, Inspection(Outcome.STORE_UNAVAILABLE)
            if inspection.outcome is Outcome.READY and (inspection.approved_store is not True
                    or inspection.permissions_verified is not True or type(inspection.version) is not int
                    or inspection.version < 1):
                return binding, Inspection(Outcome.DENIED)
            return binding, inspection
        except Exception:
            return binding, Inspection(Outcome.STORE_UNAVAILABLE)

    def capability(self, handle, *, purpose, target_id, target_trust):
        with self._lock:
            binding, inspection = self._inspect(handle, purpose, target_id, target_trust)
            configured = binding is not None and inspection.outcome not in {Outcome.ABSENT, Outcome.MISMATCHED, Outcome.REVOKED}
            return Capability(configured, inspection.outcome is Outcome.READY, inspection.outcome)

    def invoke(self, handle, *, purpose, target_id, target_trust):
        with self._lock:
            binding, inspection = self._inspect(handle, purpose, target_id, target_trust)
            if inspection.outcome is not Outcome.READY:
                return UseResult(inspection.outcome)
            try:
                result = self._store.use_fixed(binding, purpose, expected_version=inspection.version)
                if type(result) is Outcome and result in {Outcome.SUCCEEDED, Outcome.DENIED, Outcome.LOCKED,
                                                          Outcome.EXPIRED, Outcome.REVOKED, Outcome.UNKNOWN}:
                    return UseResult(result)
                return UseResult(Outcome.UNKNOWN)
            except Exception:
                # A fixed start might already have happened. No implicit retry.
                return UseResult(Outcome.UNKNOWN)

    def revoke(self, handle, *, owner_authorized):
        require(owner_authorized is True, "REVOCATION_NOT_AUTHORIZED")
        with self._lock:
            require(type(handle) is str and handle in self._bindings, "BINDING_ABSENT")
            self._bindings[handle] = replace(self._bindings[handle], revoked=True)

    def rotate(self, handle, *, new_store_locator, expires_at, owner_authorized):
        require(owner_authorized is True, "ROTATION_NOT_AUTHORIZED")
        with self._lock:
            require(type(handle) is str and handle in self._bindings and not self._bindings[handle].revoked, "BINDING_ABSENT_OR_REVOKED")
            previous = self._bindings[handle]
            new = self.enroll(target_id=previous.target_id, target_trust=previous.target_trust,
                              store_locator=new_store_locator, purposes=previous.purposes, expires_at=expires_at,
                              owner_authorized=True)
            _, inspected = self._inspect(new, next(iter(previous.purposes)), previous.target_id, previous.target_trust)
            if inspected.outcome is not Outcome.READY:
                del self._bindings[new]  # Only this uncommitted candidate binding.
                raise CredentialContractError("ROTATION_CANDIDATE_UNAVAILABLE")
            self._bindings[new] = replace(self._bindings[new], generation=previous.generation + 1)
            self._bindings[handle] = replace(previous, revoked=True)
            return new
