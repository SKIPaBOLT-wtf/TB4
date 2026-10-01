"""Read-only existing-key policy for RP006. No discovery, import or key writes."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, replace
import re
import secrets
import threading

from .credential_contract import Binding, Inspection, Outcome, Purpose, identity, require


class KeyAccessError(Exception):
    """Closed local outcome; never wrap provider text or a protected path."""
    def __init__(self, outcome=Outcome.STORE_UNAVAILABLE):
        self.outcome = outcome if type(outcome) is Outcome else Outcome.STORE_UNAVAILABLE
        super().__init__(self.outcome.value)


@dataclass(frozen=True, repr=False)
class UserSession:
    sid: str
    session: int
    logon: tuple[int, int]


@dataclass(frozen=True, repr=False)
class Selection:
    path: str
    user: UserSession
    target: str
    trust: str
    purposes: frozenset[Purpose]
    expires: int
    version: int
    interactive: bool
    revoked: bool = False


class WindowsKeyStore:
    """Only trusted commissioning may select; ports are trusted local code.

    native holds/verifies the actual file, runner.verify_target checks the protected
    current endpoint pin and maps exactly two methods to fixed helpers. No remote
    JSON can construct these ports. READY describes local resolver availability,
    not a successful authenticated connection or FETCHER readiness.
    """
    def __init__(self, installation_id, *, native, runner, clock):
        require(identity(installation_id), "INSTALLATION_ID_INVALID")
        self.installation_id = installation_id
        self._native, self._runner, self._clock = native, runner, clock
        self._selections = {}
        self._lock = threading.RLock()

    def _now(self):
        now = self._clock()
        if type(now) is not int or not 0 <= now <= 10**12:
            raise KeyAccessError()
        return now

    def select(self, *, path, target_id, target_trust, purposes, expires_at,
               interactive_required, owner_authorized):
        require(owner_authorized is True, "SELECTION_NOT_AUTHORIZED")
        require(identity(target_id), "TARGET_ID_INVALID")
        require(type(target_trust) is str and re.fullmatch(r"[0-9a-f]{64}", target_trust),
                "TARGET_TRUST_INVALID")
        require(type(purposes) is frozenset and purposes and
                all(type(p) is Purpose for p in purposes), "PURPOSE_INVALID")
        require(type(expires_at) is int and 0 <= expires_at <= 10**12, "EXPIRY_INVALID")
        require(type(interactive_required) is bool, "SESSION_POLICY_INVALID")
        with self._lock:
            try:
                if self._now() >= expires_at:
                    raise KeyAccessError(Outcome.EXPIRED)
                user = self._native.identity()
                if type(user) is not UserSession:
                    raise KeyAccessError()
                self._session(user, interactive_required)
                with self._native.open_key(path, user.sid) as key:
                    if type(key.version) is not int or key.version < 1:
                        raise KeyAccessError()
                    selection = Selection(path, user, target_id, target_trust, purposes,
                                          expires_at, key.version, interactive_required)
                ref = "wk_" + secrets.token_hex(16)
                require(ref not in self._selections, "SELECTION_COLLISION")
                self._selections[ref] = selection
                return ref
            except KeyAccessError:
                raise
            except Exception:
                raise KeyAccessError() from None

    def revoke_selection(self, reference, *, owner_authorized):
        require(owner_authorized is True, "REVOCATION_NOT_AUTHORIZED")
        with self._lock:
            require(type(reference) is str and reference in self._selections,
                    "SELECTION_ABSENT")
            self._selections[reference] = replace(self._selections[reference], revoked=True)

    def _session(self, expected, interactive):
        if self._native.identity() != expected:
            raise KeyAccessError(Outcome.DENIED)
        if interactive and self._native.interactive(expected.session) is not True:
            raise KeyAccessError(Outcome.LOCKED)

    def _check(self, binding, purpose=None):
        if (type(binding) is not Binding or binding.installation_id != self.installation_id
                or type(binding.store_locator) is not str):
            raise KeyAccessError(Outcome.DENIED)
        selection = self._selections.get(binding.store_locator)
        if selection is None:
            raise KeyAccessError(Outcome.ABSENT)
        if selection.revoked or binding.revoked:
            raise KeyAccessError(Outcome.REVOKED)
        if (binding.target_id != selection.target or binding.target_trust != selection.trust
                or not binding.purposes or not binding.purposes <= selection.purposes
                or binding.expires_at > selection.expires):
            raise KeyAccessError(Outcome.DENIED)
        if purpose is not None and (type(purpose) is not Purpose or purpose not in binding.purposes):
            raise KeyAccessError(Outcome.DENIED)
        if self._now() >= min(binding.expires_at, selection.expires):
            raise KeyAccessError(Outcome.EXPIRED)
        self._session(selection.user, selection.interactive)
        if self._runner.verify_target(selection.target, selection.trust) is not True:
            raise KeyAccessError(Outcome.DENIED)
        return selection

    @contextmanager
    def _held(self, binding, purpose=None, expected_version=None):
        selection = self._check(binding, purpose)
        with self._native.open_key(selection.path, selection.user.sid) as key:
            if (type(key.version) is not int or key.version != selection.version
                    or (expected_version is not None and key.version != expected_version)):
                raise KeyAccessError(Outcome.REVOKED)
            # Local changes, expiry, session and trust are checked again with the
            # protected handle held, immediately before exposing it to a helper.
            if self._check(binding, purpose) is not selection:
                raise KeyAccessError(Outcome.REVOKED)
            key.recheck()
            yield key

    def inspect(self, binding):
        with self._lock:
            try:
                with self._held(binding) as key:
                    return Inspection(Outcome.READY, key.version, True, True)
            except KeyAccessError as exc:
                return Inspection(exc.outcome)
            except Exception:
                return Inspection(Outcome.STORE_UNAVAILABLE)

    def use_fixed(self, binding, purpose, *, expected_version):
        with self._lock:
            try:
                if type(expected_version) is not int or expected_version < 1:
                    return Outcome.DENIED
                with self._held(binding, purpose, expected_version) as key:
                    # A callback may have an effect before it raises/loses a reply.
                    try:
                        call = (self._runner.fetcher_status if purpose is Purpose.FETCHER_STATUS
                                else self._runner.fetcher_start)
                        result = call(key, binding.target_id, binding.target_trust)
                    except Exception:
                        return Outcome.UNKNOWN
                    allowed = {Outcome.SUCCEEDED, Outcome.DENIED, Outcome.LOCKED,
                               Outcome.EXPIRED, Outcome.REVOKED, Outcome.UNKNOWN}
                    return result if type(result) is Outcome and result in allowed else Outcome.UNKNOWN
            except KeyAccessError as exc:
                # RP006's use contract has no ABSENT/STORE_UNAVAILABLE result.
                return exc.outcome if exc.outcome in {Outcome.LOCKED, Outcome.EXPIRED,
                        Outcome.REVOKED, Outcome.DENIED} else Outcome.DENIED
            except Exception:
                return Outcome.DENIED
