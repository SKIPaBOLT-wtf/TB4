"""Resumable R2 first-run settings; no network or runtime authority by itself."""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from enum import StrEnum
import ipaddress
import re
import secrets
from uuid import uuid4

from .ballpark import validate as validate_ballpark
from .credential_contract import identity, Purpose
from .credential_persistence import export_private, restore_private, validate_image, preserve_prior_authority
from .drive.commissioning import SetupSpec
from .drive.commissioning_bootstrap import AuthorityHandle
from .exchange_layout import Capacity
from .private_settings import PrivateSettings, SettingsError, encoded, require
from .timing_contract import TimingProfile

STATES = {"INCOMPLETE", "BLOCKED", "CANCELLED", "SETTINGS_READY"}
REASONS = {"MISSING_CHOICES", "REVALIDATION_REQUIRED", "CANCELLED", "UNKNOWN_OPERATION",
           "ENVIRONMENT_UNAVAILABLE", "STORAGE_UNAVAILABLE", "CREDENTIAL_UNAVAILABLE",
           "DESCRIPTOR_REQUIRED", "DESCRIPTOR_INVALID", "INSTRUCTIONS_UNAVAILABLE",
           "SETTINGS_VALIDATED", "ACTIVATION_NOT_AUTHORIZED", "ACTIVATION_UNKNOWN"}
CHOICES = {"role", "storage", "storage_request", "network_scope", "credentials", "descriptor", "timing"}


def match(pattern, value):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def storage_spec(value):
    require(type(value) is dict and set(value) in ({"spec", "authority"},
            {"spec", "authority", "root_transition"}), "SETUP_STORAGE_SHAPE")
    spec = value["spec"]
    require(type(spec) is dict and set(spec) == {
        "root_id", "domain_id", "setup_id", "bootstrap_actor", "mode", "capacity"},
        "SETUP_STORAGE_SHAPE")
    parsed = SetupSpec(**{**spec, "capacity": Capacity.parse(spec["capacity"])})
    if "root_transition" in value:
        require(parsed.mode == "NATIVE_DOCS" and match(r"[0-9a-f]{64}",value["root_transition"]),
                "SETUP_ROOT_TRANSITION")
    return parsed, AuthorityHandle.parse(value["authority"])


def validate_choices(choices, installation):
    require(type(choices) is dict and set(choices) in (CHOICES, CHOICES - {"storage_request"}),
            "SETUP_CHOICES_SHAPE")
    request = choices.get("storage_request")
    if request is not None:
        require(type(request) is dict and set(request) == {"mode", "location"}
                and type(request["mode"]) is str and request["mode"] in {"NATIVE_DOCS", "FOLDER_SQLITE_V1"}
                and type(request["location"]) is str and 0 < len(request["location"]) <= 4096
                and request["location"] == request["location"].strip()
                and not any(ord(c) < 32 for c in request["location"]), "SETUP_STORAGE_REQUEST")
    require(choices["role"] is None or type(choices["role"]) is str and
            choices["role"] in {"watchdog", "fetcher"}, "SETUP_ROLE")
    if choices["storage"] is not None:
        storage_spec(choices["storage"])
    scope = choices["network_scope"]
    if scope is not None:
        require(type(scope) is list and len(scope) <= 32 and
                all(type(x) is str and len(x) <= 64 for x in scope), "SETUP_SCOPE")
        require(len(set(scope)) == len(scope), "SETUP_SCOPE")
        for item in scope:
            try:
                network = ipaddress.ip_network(item, strict=True)
                require(str(network) == item and "%" not in item, "SETUP_SCOPE")
            except ValueError:
                raise SettingsError("SETUP_SCOPE") from None
    credentials = choices["credentials"]
    require(type(credentials) is list and len(credentials) <= 64, "SETUP_CREDENTIALS")
    seen = set()
    for value in credentials:
        require(type(value) is dict and set(value) == {
            "handle", "target_id", "target_trust", "purposes"}, "SETUP_CREDENTIALS")
        require(match(r"cr_[0-9a-f]{32}", value["handle"]) and identity(value["target_id"])
                and match(r"[0-9a-f]{64}", value["target_trust"]), "SETUP_CREDENTIALS")
        purposes = value["purposes"]
        require(type(purposes) is list and 1 <= len(purposes) <= len(Purpose)
                and all(type(p) is str and p in {x.value for x in Purpose} for p in purposes)
                and len(set(purposes)) == len(purposes), "SETUP_CREDENTIALS")
        require(value["handle"] not in seen, "SETUP_CREDENTIALS")
        seen.add(value["handle"])
    TimingProfile.parse(choices["timing"])
    if choices["descriptor"] is not None:
        local = validate_ballpark(choices["descriptor"])
        require(local["installation_id"] == installation, "SETUP_DESCRIPTOR_BINDING")
        if choices["storage"] is not None:
            spec, _ = storage_spec(choices["storage"])
            require(local["domain_id"] == spec.domain_id, "SETUP_DESCRIPTOR_BINDING")


def validated(payload):
    try:
        fields = {"schema_version", "installation_id", "setup_nonce", "state", "reason", "choices", "operations"}
        require(type(payload) is dict and fields <= set(payload)
                and set(payload) <= fields | {"credential_image", "discovery", "ballpark_draft", "ballpark_publication",
                                             "enrollments", "fetcher_enrollment", "network_table", "folder_endpoint"},
            "SETUP_SCHEMA")
        require(type(payload["schema_version"]) is int and payload["schema_version"] == 1
                and identity(payload["installation_id"])
                and match(r"[0-9a-f]{64}", payload["setup_nonce"]), "SETUP_SCHEMA")
        require(type(payload["state"]) is str and payload["state"] in STATES
                and type(payload["reason"]) is str and payload["reason"] in REASONS, "SETUP_STATE")
        validate_choices(payload["choices"], payload["installation_id"])
        if payload.get("folder_endpoint") is not None:
            from .drive.folder_endpoint_selection import selection as endpoint_selection
            endpoint_selection(payload["folder_endpoint"])
        if payload.get("network_table") is not None:
            from .network_table_store import selection
            selection(payload["network_table"], payload)
        if payload.get("discovery") is not None:
            from .discovery_state import validated_package
            spec, authority = storage_spec(payload["choices"]["storage"])
            require(payload["choices"]["role"] == "watchdog", "SETUP_DISCOVERY_BINDING")
            validated_package(payload["discovery"], installation=payload["installation_id"],
                              spec=spec, authority=authority, networks=payload["choices"]["network_scope"])
        if payload.get("ballpark_draft") is not None:
            from .ballpark_setup import package
            package(payload["ballpark_draft"], payload)
        if payload.get("ballpark_publication") is not None:
            from .ballpark_publication import package
            package(payload["ballpark_publication"], payload)
        if payload.get("enrollments") is not None:
            from .enrollment_workflow import package
            package(payload["enrollments"], payload)
        if payload.get("fetcher_enrollment") is not None:
            from .fetcher_enrollment import package
            package(payload["fetcher_enrollment"], payload)
        image = payload.get("credential_image")
        if image is not None:
            image = validate_image(image, payload["installation_id"])
            for selected in payload["choices"]["credentials"]:
                binding = image["bindings"].get(selected["handle"])
                require(binding is not None and selected["target_id"] == binding["target_id"]
                        and selected["target_trust"] == binding["target_trust"]
                        and set(selected["purposes"]) <= set(binding["purposes"]), "SETUP_CREDENTIALS")
        operations = payload["operations"]
        require(type(operations) is dict and len(operations) <= 64, "SETUP_OPERATIONS")
        require(all(match(r"[0-9a-f]{64}", key) and type(value) is str
                    and value in {"UNKNOWN", "CONFIRMED", "REJECTED"} for key, value in operations.items()),
                "SETUP_OPERATIONS")
        encoded(payload)
        return copy.deepcopy(payload)
    except SettingsError:
        raise
    except Exception:
        raise SettingsError("SETUP_SCHEMA") from None


class Reconciliation(StrEnum):
    UNKNOWN = "UNKNOWN"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, repr=False)
class Validation:
    # A trusted code result, never loaded from JSON or accepted as a READY flag.
    pin: object
    environment: object


class Setup:
    def __init__(self, store: PrivateSettings, *, create=False):
        require(type(store) is PrivateSettings and type(create) is bool, "SETUP_STORE")
        self.store, self._validation, self._ready_revision = store, None, None
        snapshot = store.read()
        if snapshot is None:
            require(create, "SETUP_NOT_CREATED")
            payload = dict(schema_version=1, installation_id=str(uuid4()),
                           setup_nonce=secrets.token_hex(32), state="INCOMPLETE", reason="MISSING_CHOICES",
                           choices=dict(role=None, storage=None, storage_request=None, network_scope=None, credentials=[],
                                        descriptor=None, timing=asdict(TimingProfile())), operations={},
                           credential_image=None)
            snapshot = store.save(validated(payload), expected_revision=0)
        self.snapshot = snapshot
        self._payload = validated(snapshot.payload)

    @property
    def installation_id(self):
        """Protected local identity; never included in status()."""
        return self._payload["installation_id"]

    def private_choices(self):
        """Only for the local setup UI/trusted adapters, never reports."""
        return copy.deepcopy(self._payload["choices"])

    def _fresh(self):
        actual = self.store.read()
        require(actual is not None and actual.revision == self.snapshot.revision
                and actual.payload == self._payload, "SETTINGS_CHANGED_RELOAD_REQUIRED")

    def _save(self, payload):
        self._validation = self._ready_revision = None
        payload = validated(payload)
        snapshot = self.store.save(payload, expected_revision=self.snapshot.revision)
        self.snapshot, self._payload = snapshot, payload

    def missing_choices(self):
        choices = self._payload["choices"]
        return tuple(key for key in ("role", "storage", "network_scope") if choices[key] is None
                     and not (key == "storage" and choices.get("storage_request") is not None))

    def status(self):
        state, reason = self._payload["state"], self._payload["reason"]
        current = self._ready_revision == self.snapshot.revision
        if current:
            try:
                self._fresh()
            except Exception:
                current = False
        if state == "SETTINGS_READY" and not current:
            state, reason = "INCOMPLETE", "REVALIDATION_REQUIRED"
        return dict(state=state, reason=reason, missing_choices=list(self.missing_choices()),
                    settings_validated=current,
                    runtime_active=False, automatic_replay=False)

    def choose(self, patch):
        self._fresh()
        require(type(patch) is dict and set(patch) <= CHOICES, "SETUP_CHOICES_SHAPE")
        value = copy.deepcopy(self._payload)
        if value.get("enrollments") is not None or value.get("fetcher_enrollment") is not None:
            require(all(patch[k] == value["choices"].get(k) for k in set(patch) & {
                "role", "storage", "storage_request", "network_scope", "descriptor"}),
                    "SETUP_ENROLLMENT_BINDING_FROZEN")
        if value.get("ballpark_draft") is not None or value.get("ballpark_publication") is not None:
            require(all(patch[k] == value["choices"].get(k) for k in set(patch) & {
                "role", "storage", "storage_request", "network_scope", "descriptor", "timing"}),
                    "SETUP_BALLPARK_BINDING_FROZEN")
        if value.get("discovery") is not None:
            require(all(patch[k] == value["choices"].get(k)
                        for k in set(patch) & {"role", "storage", "storage_request", "network_scope"}),
                    "SETUP_DISCOVERY_BINDING_FROZEN")
        # Once any external operation is recorded the exact domain/root remains
        # fixed, even when its result is confirmed. This is not a migration API.
        if value["operations"] and "storage" in patch:
            require(patch["storage"] == value["choices"]["storage"], "SETUP_BINDING_FROZEN")
        if "storage_request" in patch and patch["storage_request"] != value["choices"].get("storage_request"):
            require(not value["operations"], "SETUP_BINDING_FROZEN")
            require("storage" not in patch, "SETUP_BINDING_UNVERIFIED")
            value["choices"]["storage"] = None
        value["choices"].update(copy.deepcopy(patch))
        require("UNKNOWN" not in value["operations"].values()
                or value["choices"] == self._payload["choices"], "SETUP_INSPECT_REQUIRED")
        value.update(state="INCOMPLETE", reason="REVALIDATION_REQUIRED")
        self._save(value)
        return self.status()

    def cancel(self):
        self._fresh()
        self._save({**self._payload, "state": "CANCELLED", "reason": "CANCELLED"})
        return self.status()

    def persist_credentials(self, store, resolver, selected):
        """Commit exact refs and protected metadata together, never key bytes."""
        self._fresh()
        image = export_private(store, resolver)
        require(image["installation_id"] == self.installation_id, "SETUP_CREDENTIALS")
        previous = self._payload.get("credential_image")
        preserve_prior_authority(previous, image)
        unknown = "UNKNOWN" in self._payload["operations"].values()
        if unknown:
            # Revocation is allowed during UNKNOWN; adding/rebinding authority
            # or changing selected capabilities remains forbidden.
            require(previous is not None and selected == self._payload["choices"]["credentials"]
                    and all(set(previous[k]) == set(image[k]) for k in ("selections", "bindings")),
                    "SETUP_INSPECT_REQUIRED")
        value = copy.deepcopy(self._payload)
        value["choices"]["credentials"] = copy.deepcopy(selected)
        value.update(credential_image=image, state="BLOCKED" if unknown else "INCOMPLETE",
                     reason="UNKNOWN_OPERATION" if unknown else "REVALIDATION_REQUIRED")
        self._save(value)
        return self.status()

    def restore_credentials(self, store, resolver):
        """Read the same protected frame immediately before fresh-pair restore."""
        self._fresh()
        image = self._payload.get("credential_image")
        require(image is not None, "SETUP_CREDENTIAL_IMAGE_ABSENT")
        require(store.installation_id == self.installation_id, "SETUP_CREDENTIALS")
        restore_private(image, store, resolver)

    def resume(self):
        self._fresh()
        self._save({**self._payload, "state": "INCOMPLETE", "reason": "REVALIDATION_REQUIRED"})
        return self.status()

    def block(self, reason):
        self._fresh()
        require(type(reason) is str and reason in REASONS, "SETUP_STATE")
        if self._payload["state"] != "CANCELLED":
            self._save({**self._payload, "state":"BLOCKED", "reason":reason})
        return self.status()

    def review(self, checker):
        self._fresh()
        if self._payload["state"] == "CANCELLED":
            return self.status()
        value = copy.deepcopy(self._payload)
        validation = None
        if self.missing_choices():
            state, reason = "INCOMPLETE", "MISSING_CHOICES"
        elif "UNKNOWN" in value["operations"].values():
            state, reason = "BLOCKED", "UNKNOWN_OPERATION"
        else:
            try:
                validation = checker.validate(copy.deepcopy(value))
                require(type(validation) is Validation, "SETUP_VALIDATION")
                state, reason = "SETTINGS_READY", "SETTINGS_VALIDATED"
            except Exception as exc:
                code = str(exc) if type(exc) is SettingsError else ""
                state, reason = "BLOCKED", code if code in REASONS else "ENVIRONMENT_UNAVAILABLE"
        self._save({**value, "state": state, "reason": reason})
        if validation is not None and state == "SETTINGS_READY":
            self._validation, self._ready_revision = validation, self.snapshot.revision
        return self.status()

    def activate(self, checker, activation):
        """Trusted activation port owns separate release/deployment/enrollment gates.

        No persisted boolean, GUI checkbox or generic settings approval can
        construct that port. Default product entrypoints supply DenyActivation.
        Runtimes still enforce owner/operation authorization at each boundary.
        """
        if not self.review(checker)["settings_validated"]:
            return self.status()
        self._fresh()
        try:
            # The trusted port must check independent authorization and revalidate
            # its runtime context before entering. Setup readiness is not a grant.
            activation.enter(copy.deepcopy(self._payload), self._validation)
        except Exception as exc:
            code = str(exc) if type(exc) is SettingsError else ""
            reason = "ACTIVATION_NOT_AUTHORIZED" if code == "ACTIVATION_NOT_AUTHORIZED" else "ACTIVATION_UNKNOWN"
            self._save({**self._payload, "state": "BLOCKED", "reason": reason})
            return self.status()
        return {**self.status(), "runtime_active": True}

    def perform_once(self, operation_id, action, *, owner_authorized=False):
        """Trusted commissioning-only callback. Lost results always need inspection."""
        self._fresh()
        require(owner_authorized is True, "SETUP_ACTION_NOT_AUTHORIZED")
        require(match(r"[0-9a-f]{64}", operation_id), "SETUP_OPERATIONS")
        require(not self.missing_choices() and self._payload["state"] != "CANCELLED", "SETUP_INCOMPLETE")
        require(operation_id not in self._payload["operations"]
                and "UNKNOWN" not in self._payload["operations"].values(), "SETUP_INSPECT_REQUIRED")
        value = copy.deepcopy(self._payload)
        value["operations"][operation_id] = "UNKNOWN"
        value.update(state="BLOCKED", reason="UNKNOWN_OPERATION")
        self._save(value)
        # Only this live call reaches action, after durable readback. Restart
        # cannot distinguish no-call from lost reply and never repeats it.
        try:
            action()
        except Exception:
            pass
        return self.status()

    def reconcile(self, operation_id, inspector):
        self._fresh()
        require(self._payload["operations"].get(operation_id) == "UNKNOWN", "SETUP_INSPECT_REQUIRED")
        try:
            result = inspector(operation_id)
        except Exception:
            result = Reconciliation.UNKNOWN
        require(type(result) is Reconciliation, "SETUP_INSPECTION_INVALID")
        value = copy.deepcopy(self._payload)
        value["operations"][operation_id] = result.value
        value.update(state="BLOCKED" if result is Reconciliation.UNKNOWN else "INCOMPLETE",
                     reason="UNKNOWN_OPERATION" if result is Reconciliation.UNKNOWN else "REVALIDATION_REQUIRED")
        self._save(value)
        return self.status()

    def rollback_choices(self, *, stopped):
        """Append a new revision; identity, bindings and operation history survive."""
        require(stopped is True, "SETUP_ROLLBACK_REQUIRES_STOPPED")
        self._fresh()
        previous = self.snapshot.previous
        require(previous is not None, "SETUP_PREVIOUS_ABSENT")
        previous = validated(previous)
        require(previous["installation_id"] == self.installation_id
                and previous["setup_nonce"] == self._payload["setup_nonce"]
                and previous["operations"] == self._payload["operations"]
                and previous.get("credential_image") == self._payload.get("credential_image")
                and previous.get("discovery") == self._payload.get("discovery")
                and previous.get("ballpark_draft") == self._payload.get("ballpark_draft")
                and previous.get("ballpark_publication") == self._payload.get("ballpark_publication")
                and previous.get("enrollments") == self._payload.get("enrollments")
                and previous.get("fetcher_enrollment") == self._payload.get("fetcher_enrollment")
                and previous.get("folder_endpoint") == self._payload.get("folder_endpoint")
                and previous["choices"]["storage"] == self._payload["choices"]["storage"],
                "SETUP_ROLLBACK_UNSAFE")
        self._save({**previous, "state": "INCOMPLETE", "reason": "REVALIDATION_REQUIRED"})
        return self.status()


class DenyActivation:
    def enter(self, payload, validation):
        raise SettingsError("ACTIVATION_NOT_AUTHORIZED")
