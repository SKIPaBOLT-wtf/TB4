"""Protected same-authority candidate through actual first-run validation.

No active-profile promotion, provider writes, root move or activation here.
The complete original payload is immutable; derived caches in the staged profile
are intentionally absent and cannot silently become current routing evidence.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib

from .ballpark_setup import pin_record, validate_pin
from .commissioning_checks import CommissionedStorage, Prerequisites
from .commissioning_state import Setup, validated
from .configuration_contract import require
from .exchange_layout import MAX_GENERATION
from .private_settings import PrivateSettings, encoded
from .reconfiguration_evidence import ProtectedEvidence
from .reconfiguration_maintenance import Maintenance, ResolutionProposal, hex64, sha

SCHEMA = "protocol/reconfiguration-candidate-v1.schema.json"
SCHEMA_SHA256 = "e56758941bbc7907414409e04bcb0bb3a1f211e5d50cd96839e33dd34ea05e82"
DERIVED = frozenset({"discovery", "ballpark_draft", "ballpark_publication",
                     "enrollments", "fetcher_enrollment"})
STATE_FIELDS = frozenset({"schema_version", "kind", "installation_id", "transition_id",
    "configuration_revision", "base_setup_revision", "base_setup_sha256", "seed_sha256",
    "authority", "bindings", "pin", "phase"})


def native_binding(store):
    # Native identity/protection is checked afresh, never inferred from a path.
    with store.native.locked() as port:
        return sha(port.binding)


def seed(base):
    value = {k:copy.deepcopy(base[k]) for k in (
        "schema_version", "installation_id", "setup_nonce", "choices", "operations")}
    for key in ("credential_image", "network_table"):
        if key in base:
            value[key] = copy.deepcopy(base[key])
    value.update(state="INCOMPLETE", reason="REVALIDATION_REQUIRED")
    return validated(value)


@dataclass(frozen=True, repr=False)
class CandidateContext:
    maintenance: Maintenance
    resolution: ProtectedEvidence
    profile: PrivateSettings
    archive: PrivateSettings
    transaction: PrivateSettings


@dataclass(frozen=True, repr=False)
class CandidateValidation:
    """Ephemeral typed result, not a saved grant or a runtime activation port."""
    decision: ResolutionProposal
    revision: int
    setup_sha256: str
    validation: object


class Candidate:
    def __init__(self, context):
        require(type(context) is CandidateContext and type(context.maintenance) is Maintenance
                and type(context.resolution) is ProtectedEvidence
                and all(type(s) is PrivateSettings for s in (
                    context.profile, context.archive, context.transaction)), "CONFIGURATION_CANDIDATE_CONTEXT")
        self.context, self._reviewed_revision = context, None
        self._bindings()

    @property
    def original(self):
        return self.context.maintenance.context.setup

    def _bindings(self):
        ctx = self.context
        value = {name:native_binding(store) for name,store in (
            ("original",self.original.store), ("profile",ctx.profile),
            ("archive",ctx.archive), ("transaction",ctx.transaction))}
        require(len(set(value.values())) == 4, "CONFIGURATION_CANDIDATE_STORE_ALIAS")
        old = self.context.maintenance.context
        forbidden = [old.store, old.baseline.store, self.context.resolution.store]
        if old.effects is not None:
            forbidden.extend((old.effects.store, old.checkpoint.store))
        require(not ({value[k] for k in ("profile","archive","transaction")}
                     & {native_binding(s) for s in forbidden}), "CONFIGURATION_CANDIDATE_STORE_ALIAS")
        return value

    def _schema(self, value):
        require(type(value) is dict and set(value) == STATE_FIELDS
                and type(value["schema_version"]) is int and value["schema_version"] == 1
                and value["kind"] == "RECONFIGURATION_CANDIDATE"
                and value["installation_id"] == self.original.installation_id
                and value["transition_id"] == self.context.maintenance.context.baseline.transition_id
                and hex64(value["transition_id"])
                and type(value["phase"]) is str
                and value["phase"] in {"STAGING", "STAGED"}, "CONFIGURATION_CANDIDATE_SCHEMA")
        require(all(type(value[k]) is int and 1 <= value[k] <= MAX_GENERATION
                    for k in ("configuration_revision", "base_setup_revision"))
                and hex64(value["base_setup_sha256"]) and hex64(value["seed_sha256"])
                and value["bindings"] == self._bindings(), "CONFIGURATION_CANDIDATE_BINDING")
        state,_ = self.context.maintenance._state()
        require(state is not None and value["authority"] == state["authority"],
                "CONFIGURATION_CANDIDATE_BINDING")
        validate_pin(value["pin"])
        require(len(encoded(value)) <= 64 * 1024, "CONFIGURATION_CANDIDATE_SIZE")
        return copy.deepcopy(value)

    def _proof(self, state=None):
        decision = self.context.maintenance.require_resolved(self.context.resolution)
        pin = self.context.maintenance._proof()
        require(hashlib.sha256(pin.read(SCHEMA)).hexdigest() == SCHEMA_SHA256,
                "CONFIGURATION_CANDIDATE_SCHEMA_INCOMPATIBLE")
        if state is not None:
            self._schema(state)
            require(state["base_setup_revision"] == self.original.snapshot.revision
                    and state["base_setup_sha256"] == decision.setup_sha256
                    and state["configuration_revision"] == decision.revision
                    and state["transition_id"] == decision.transition_id
                    and state["pin"] == pin_record(pin), "CONFIGURATION_CANDIDATE_CHANGED")
        return decision, pin

    def _state(self):
        current = self.context.transaction.read()
        if current is None:
            return None, 0
        return self._schema(current.payload), current.revision

    def _save(self, value, revision):
        value = self._schema(value)
        self.context.transaction.save(value, expected_revision=revision)
        state, after = self._state()
        require(state == value and after == revision + 1, "CONFIGURATION_CANDIDATE_UNCONFIRMED")
        return state

    def _archive_value(self, state):
        self.original._fresh()
        base = validated(self.original._payload)
        require(sha(base) == state["base_setup_sha256"]
                and sha(seed(base)) == state["seed_sha256"], "CONFIGURATION_CANDIDATE_CHANGED")
        return dict(schema_version=1, kind="RECONFIGURATION_ORIGINAL_PROFILE",
            installation_id=self.original.installation_id, transition_id=state["transition_id"],
            base_setup_revision=state["base_setup_revision"], base_setup_sha256=state["base_setup_sha256"],
            profile=base)

    def _archive(self, state):
        saved = self.context.archive.read()
        require(saved is not None and saved.revision == 1 and saved.previous is None
                and saved.payload == self._archive_value(state), "CONFIGURATION_CANDIDATE_ARCHIVE")
        return validated(saved.payload["profile"])

    def _validate_profile(self, payload, base):
        value = validated(payload)
        require(value["installation_id"] == base["installation_id"]
                and value["setup_nonce"] == base["setup_nonce"]
                and value["operations"] == base["operations"]
                and value["choices"]["role"] == base["choices"]["role"]
                and value["choices"]["storage"] == base["choices"]["storage"]
                and value["choices"].get("storage_request") == base["choices"].get("storage_request")
                and not (set(value) & DERIVED), "CONFIGURATION_CANDIDATE_IDENTITY")
        require(len(encoded(value)) <= 384 * 1024, "CONFIGURATION_CANDIDATE_SIZE")
        return value

    def _setup(self, state):
        require(state["phase"] == "STAGED", "CONFIGURATION_CANDIDATE_INSPECT_REQUIRED")
        base = self._archive(state)
        model = Setup(self.context.profile)
        self._validate_profile(model._payload, base)
        return model

    def _continue(self, state, revision):
        self._proof(state)
        require(state["phase"] == "STAGING", "CONFIGURATION_CANDIDATE_INSPECT_REQUIRED")
        archive = self.context.archive.read()
        if archive is None:
            self.context.archive.save(self._archive_value(state), expected_revision=0)
        base = self._archive(state)
        initial = seed(base)
        self._validate_profile(initial, base)
        current = self.context.profile.read()
        if current is None:
            self.context.profile.save(initial, expected_revision=0)
            current = self.context.profile.read()
        require(current is not None and current.revision == 1 and current.previous is None
                and current.payload == initial, "CONFIGURATION_CANDIDATE_INSPECT_REQUIRED")
        self._proof(state)
        self._save({**state,"phase":"STAGED"}, revision)
        return self.view()

    def begin(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        require(self._state()[0] is None and self.context.archive.read() is None
                and self.context.profile.read() is None, "CONFIGURATION_CANDIDATE_INSPECT_REQUIRED")
        decision, pin = self._proof()
        maintenance,_ = self.context.maintenance._state()
        base = self.original._payload
        # The durable metadata precedes either new local profile. No remote send.
        state = dict(schema_version=1, kind="RECONFIGURATION_CANDIDATE",
            installation_id=self.original.installation_id, transition_id=decision.transition_id,
            configuration_revision=decision.revision, base_setup_revision=self.original.snapshot.revision,
            base_setup_sha256=decision.setup_sha256, seed_sha256=sha(seed(base)),
            authority=maintenance["authority"], bindings=self._bindings(), pin=pin_record(pin), phase="STAGING")
        state = self._save(state, 0)
        return self._continue(state, 1)

    def resume_staging(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        state, revision = self._state()
        require(state is not None, "CONFIGURATION_CANDIDATE_NOT_STARTED")
        return self._continue(state, revision)

    def view(self):
        state,_ = self._state()
        if state is None:
            return dict(phase="NOT_STARTED", settings_validated=False,
                        runtime_active=False, automatic_replay=False)
        ready = False
        if state["phase"] == "STAGED":
            model = self._setup(state)
            ready = (self._reviewed_revision == model.snapshot.revision)
        return dict(phase=state["phase"], settings_validated=ready,
                    runtime_active=False, automatic_replay=False)

    def choose(self, patch, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        state,_ = self._state()
        require(state is not None, "CONFIGURATION_CANDIDATE_NOT_STARTED")
        self._proof(state)
        model = self._setup(state)
        value = copy.deepcopy(model._payload)
        require(type(patch) is dict and set(patch) <= {"network_scope", "credentials", "descriptor", "timing"},
                "CONFIGURATION_CANDIDATE_IDENTITY")
        value["choices"].update(copy.deepcopy(patch))
        self._validate_profile(value,self._archive(state))
        model.choose(patch)
        self._reviewed_revision = None
        return self.view()

    def persist_credentials(self, store, resolver, selected, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        state,_ = self._state()
        require(state is not None, "CONFIGURATION_CANDIDATE_NOT_STARTED")
        self._proof(state)
        model = self._setup(state)
        model.persist_credentials(store,resolver,selected)
        self._validate_profile(model._payload,self._archive(state))
        self._reviewed_revision = None
        return self.view()

    def _checker(self, checker):
        require(type(checker) is Prerequisites and type(checker.storage) is CommissionedStorage
                and checker.source is self.context.maintenance.context.source
                and checker.runtime == self.context.maintenance.context.runtime,
                "CONFIGURATION_CANDIDATE_CHECKER")
        return checker

    def review(self, checker):
        state,_ = self._state()
        require(state is not None, "CONFIGURATION_CANDIDATE_NOT_STARTED")
        self._reviewed_revision = None
        self._proof(state)
        model = self._setup(state)
        result = model.review(self._checker(checker))
        self._validate_profile(model._payload,self._archive(state))
        self._proof(state)
        if result["settings_validated"]:
            self._reviewed_revision = model.snapshot.revision
        return {**result, **self.view()}

    def require_validated(self, checker):
        # Always repeat the actual first-run probes. A previously green view,
        # persisted SETTINGS_READY or deserialized certificate grants nothing.
        result = self.review(checker)
        require(result["settings_validated"], "CONFIGURATION_CANDIDATE_REVALIDATION_REQUIRED")
        state,_ = self._state()
        decision,_ = self._proof(state)
        model = self._setup(state)
        validation = self._checker(checker).validate(copy.deepcopy(model._payload))
        require(pin_record(validation.pin) == state["pin"], "CONFIGURATION_CANDIDATE_PIN_CHANGED")
        self._proof(state)
        model._fresh()
        return CandidateValidation(decision,model.snapshot.revision,sha(model._payload),validation)

    def recover_local(self, which, *, owner_authorized=False):
        """Promote only the same complete native candidate; no remote work."""
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        require(which in {"transaction","archive","profile"}, "CONFIGURATION_CANDIDATE_RECOVERY")
        state = None if which == "transaction" else self._state()[0]
        self._proof(state)
        base = self._archive(state) if which == "profile" else None
        store = getattr(self.context,which)
        with store.native.locked() as port:
            pending, raw = port.read("settings.pending"), port.read("settings.json")
            if pending is None:
                return "NO_PENDING"
            candidate = store._decode(pending,port.binding)
            current = None if raw is None else store._decode(raw,port.binding)
            require(candidate.revision == (0 if current is None else current.revision) + 1
                    and candidate.previous == (None if current is None else current.payload),
                    "CONFIGURATION_CANDIDATE_RECOVERY_CONFLICT")
        # Cross-store/schema proofs must not reacquire this same native lock.
        if which == "transaction":
            self._proof(self._schema(candidate.payload))
        elif which == "archive":
            require(candidate.revision == 1 and candidate.previous is None
                    and candidate.payload == self._archive_value(state), "CONFIGURATION_CANDIDATE_ARCHIVE")
        else:
            self._validate_profile(candidate.payload,base)
            if state["phase"] == "STAGING":
                require(candidate.revision == 1 and candidate.payload == seed(base),
                        "CONFIGURATION_CANDIDATE_RECOVERY_CONFLICT")
        with store.native.locked() as port:
            require(port.read("settings.pending") == pending and port.read("settings.json") == raw,
                    "CONFIGURATION_CANDIDATE_RECOVERY_CONFLICT")
            require(store._decode(pending,port.binding) == candidate,
                    "CONFIGURATION_CANDIDATE_RECOVERY_CONFLICT")
            port.promote()
            require(port.read("settings.json") == pending, "CONFIGURATION_CANDIDATE_UNCONFIRMED")
        self._reviewed_revision = None
        return "INSPECT_REQUIRED"
