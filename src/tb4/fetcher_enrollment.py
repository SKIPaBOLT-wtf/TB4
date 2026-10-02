"""Distinct protected FETCHER installation selection and actual local announcements."""
from __future__ import annotations

import copy
import re
import secrets

from .commissioning_state import Setup, storage_spec
from .commissioning_checks import CommissionedStorage
from .credential_contract import identity
from .enrollment_records import enrollment, target
from .fetcher_profile import require, integer, validate, report, RuntimeSnapshot
from .timing_contract import TimingProfile, ActivityClock


def announcement(value):
    require(type(value) is dict and set(value) == {"installation_id", "device_id", "slot", "nonce",
        "expected_enrollment_revision", "profile"} and identity(value["installation_id"])
        and identity(value["device_id"]) and value["installation_id"] != value["device_id"]
        and integer(value["slot"], 0, 63) and type(value["nonce"]) is str
        and re.fullmatch(r"[0-9a-f]{32}", value["nonce"])
        and integer(value["expected_enrollment_revision"], 0, 2**63-1), "ENROLLMENT_ANNOUNCEMENT")
    validate(value["profile"])
    return copy.deepcopy(value)


def package(value, payload):
    require(type(value) is dict and set(value) == {
        "authority", "slot", "device_id", "nonce", "last_report", "active"}, "ENROLLMENT_LOCAL")
    choices = payload["choices"]
    spec, handle = storage_spec(choices["storage"])
    require(choices["role"] == "fetcher" and value["authority"] == handle.record()
            and integer(value["slot"], 0, spec.capacity.devices-1) and identity(value["device_id"])
            and value["device_id"] != payload["installation_id"]
            and type(value["nonce"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["nonce"]),
            "ENROLLMENT_LOCAL")
    if value["last_report"] is not None:
        request = announcement(value["last_report"])
        require(request["installation_id"] == payload["installation_id"]
                and all(request[k] == value[k] for k in ("slot", "device_id", "nonce")), "ENROLLMENT_LOCAL")
    active = value["active"]
    if active is not None:
        require(type(active) is dict and set(active) == {"enrollment", "profile_revision"}, "ENROLLMENT_LOCAL")
        bound = enrollment(active["enrollment"])
        require(bound is not None and bound["installation_id"] == payload["installation_id"]
                and bound["nonce"] == value["nonce"] and integer(active["profile_revision"], 1, 2**63-1),
                "ENROLLMENT_LOCAL")
    return copy.deepcopy(value)


class FetcherEnrollment:
    def __init__(self, setup, storage_port, *, runtime, activity):
        require(type(setup) is Setup and callable(runtime) and type(activity) is ActivityClock,
                "ENROLLMENT_FETCHER_CONTEXT")
        self.setup, self.port, self.runtime, self.activity = setup, storage_port, runtime, activity

    def _document(self, *, cancelled=False):
        self.setup._fresh()
        choices = self.setup.private_choices()
        require(choices["role"] == "fetcher" and (cancelled or self.setup._payload["state"] != "CANCELLED"),
                "ENROLLMENT_FETCHER_CONTEXT")
        spec, handle = storage_spec(choices["storage"])
        require(self.port.authority(handle).binding.domain_id == spec.domain_id, "ENROLLMENT_AUTHORITY")
        return CommissionedStorage(self.port).verify(choices["storage"])

    def _save(self, state):
        self.setup._fresh()
        package(state, self.setup._payload)
        self.setup._save({**self.setup._payload, "fetcher_enrollment": state})

    def select(self, slot, *, device_id, owner_authorized=False):
        require(owner_authorized is True, "ENROLLMENT_OWNER_REQUIRED")
        document = self._document()
        _, _, approved, binding, _ = target(document, slot)
        require(approved["device_id"] == device_id, "ENROLLMENT_DEVICE_CHANGED")
        _, handle = storage_spec(self.setup.private_choices()["storage"])
        prior = self.setup._payload.get("fetcher_enrollment")
        if prior is not None:
            require(prior["slot"] == slot and prior["device_id"] == device_id, "ENROLLMENT_MAINTENANCE_REQUIRED")
            return self.status()
        require(binding is None, "ENROLLMENT_REINSTALL_MAINTENANCE")
        self._save(dict(authority=handle.record(), slot=slot, device_id=device_id,
                        nonce=secrets.token_hex(16), last_report=None, active=None))
        return self.status()

    def capture(self, *, observed_at, holds=None):
        self._document()
        state = package(self.setup._payload.get("fetcher_enrollment"), self.setup._payload)
        active = state["active"]
        if active is not None:
            require(enrollment(active["enrollment"])["state"] == "ENROLLED", "ENROLLMENT_REVOKED")
        revision = 1 if active is None else active["profile_revision"]+1
        expected = 0 if active is None else enrollment(active["enrollment"])["revision"]
        snapshot = self.runtime()
        require(type(snapshot) is RuntimeSnapshot, "PROFILE_CONTEXT")
        profile = report(snapshot, snapshot.timing, self.activity,
                         revision=revision, observed_at=observed_at, holds=holds)
        value = announcement(dict(installation_id=self.setup.installation_id, device_id=state["device_id"],
            slot=state["slot"], nonce=state["nonce"], expected_enrollment_revision=expected, profile=profile))
        self._save({**state, "last_report": value})
        return value  # Private authenticated transport only; not an LLM/public log.

    def inspect(self):
        document = self._document(cancelled=True)
        state = package(self.setup._payload.get("fetcher_enrollment"), self.setup._payload)
        _, body, approved, binding, profile = target(document, state["slot"])
        if (approved["device_id"] != state["device_id"] or binding is None
                or binding["installation_id"] != self.setup.installation_id or binding["nonce"] != state["nonce"]):
            return "UNKNOWN"
        # Confirm binding from the authority even after a newer local sample.
        # It does not assert that an unpublished newer sample has been applied.
        self._save({**state, "active": dict(enrollment=body["enrollment"], profile_revision=profile["revision"])})
        return "REVOKED" if binding["state"] == "REVOKED" else "CONFIRMED"

    def status(self):
        self.setup._fresh()
        state = self.setup._payload.get("fetcher_enrollment")
        active = None if state is None else state["active"]
        return dict(selected=state is not None, enrolled=active is not None
                    and enrollment(active["enrollment"])["state"] == "ENROLLED",
                    profile_confirmed_revision=None if active is None else active["profile_revision"],
                    runtime_active=False, execution_authorized=False)
