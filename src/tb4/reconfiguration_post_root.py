"""Actual first-run candidate after qualified same-Docs root rebind.

Separate protected staging only. No remote mutation, active profile replacement,
ACTIVE publication, runtime activation or saved readiness grant.
"""
from dataclasses import asdict, dataclass
import copy
import hashlib

from .ballpark_setup import pin_record, validate_pin
from .commissioning_checks import CommissionedStorage, Prerequisites
from .commissioning_state import Setup, storage_spec, validated
from .configuration_contract import configuration, require
from .drive.commissioning_native import NativeCommissioning
from .exchange_layout import MAX_GENERATION
from .private_settings import PrivateSettings, encoded
from .reconfiguration_candidate import DERIVED, SCHEMA, seed, native_binding
from .reconfiguration_effects import SLOT
from .reconfiguration_maintenance import hex64, sha
from .reconfiguration_rebind import RemoteRebind
from .reconfiguration_root_plan import stable_records

# Same immutable candidate-schema closure, selected named schema. The legacy
# top-level candidate remains closed and its meaning is unchanged.
SCHEMA_DEFINITION = "postRootCandidate"
SCHEMA_SHA256 = "93c9bfa184438306e12539d981e4395d76d7807b357403cacde1968918fa1ef0"
STATE_FIELDS = frozenset({"schema_version", "kind", "installation_id", "transition_id",
    "configuration_revision", "base_setup_revision", "base_setup_sha256", "seed_sha256",
    "authority", "bindings", "pin", "phase", "storage", "epoch", "records_sha256", "summary_sha256"})


@dataclass(frozen=True, repr=False)
class PostRootContext:
    rebind: RemoteRebind
    profile: PrivateSettings
    archive: PrivateSettings
    transaction: PrivateSettings


@dataclass(frozen=True, repr=False)
class PostRootValidation:
    transition_id: str
    configuration_revision: int
    epoch: int
    revision: int
    setup_sha256: str
    storage: dict
    validation: object
    _origin: object


class PostRootCandidate:
    def __init__(self, context):
        require(type(context) is PostRootContext and type(context.rebind) is RemoteRebind
                and all(type(s) is PrivateSettings for s in (
                    context.profile, context.archive, context.transaction)), "POST_ROOT_CONTEXT")
        self.context, self._reviewed_revision = context, None
        self._bindings()

    @property
    def original(self):
        return self.context.rebind.ctx.setup

    def _bindings(self):
        ctx = self.context.rebind.ctx
        stores = {"original":self.original.store, "profile":self.context.profile,
            "archive":self.context.archive, "transaction":self.context.transaction,
            "rebind":self.context.rebind.context.store, "checkpoint":ctx.checkpoint.store,
            "effects":ctx.effects.store, "maintenance":ctx.store, "baseline":ctx.baseline.store}
        result = {name:native_binding(store) for name,store in stores.items()}
        require(len(set(result.values())) == len(result), "POST_ROOT_STORE_ALIAS")
        return result

    def _current(self):
        rebind = self.context.rebind
        proof = rebind.verify_current(owner_authorized=True)
        snapshot, cp, pin = rebind._role(owner=True)
        require(hashlib.sha256(snapshot.raw).hexdigest() == proof.document_sha256,
                "POST_ROOT_CHANGED")
        require(hashlib.sha256(pin.read(SCHEMA)).hexdigest() == SCHEMA_SHA256,
                "POST_ROOT_INSTRUCTIONS")
        return snapshot, cp, pin, proof.storage

    def _schema(self, value):
        require(type(value) is dict and set(value) == STATE_FIELDS
                and type(value["schema_version"]) is int and value["schema_version"] == 1
                and value["kind"] == "RECONFIGURATION_POST_ROOT_CANDIDATE"
                and value["installation_id"] == self.original.installation_id
                and hex64(value["transition_id"])
                and type(value["phase"]) is str and value["phase"] in {"STAGING", "STAGED"}
                and all(type(value[k]) is int and 1 <= value[k] <= MAX_GENERATION for k in (
                    "configuration_revision", "base_setup_revision", "epoch"))
                and all(hex64(value[k]) for k in (
                    "base_setup_sha256", "seed_sha256", "records_sha256", "summary_sha256")),
                "POST_ROOT_SCHEMA")
        target, handle = storage_spec(value["storage"])
        source, before = storage_spec(self.original.private_choices()["storage"])
        require(target.mode == source.mode == "NATIVE_DOCS" and target.root_id != source.root_id
                and target.domain_id == source.domain_id and target.capacity == source.capacity
                and target.setup_id == source.setup_id and target.bootstrap_actor == source.bootstrap_actor
                and handle.object_id == before.object_id and handle.tab_id == before.tab_id
                and value["storage"].get("root_transition") == value["transition_id"]
                and value["authority"] == dict(mode="NATIVE_DOCS",
                    binding=asdict(self.context.rebind.ctx.leadership.backend.binding))
                and value["bindings"] == self._bindings(), "POST_ROOT_BINDING")
        validate_pin(value["pin"])
        require(len(encoded(value)) <= 64*1024, "POST_ROOT_SIZE")
        return copy.deepcopy(value)

    def _seed(self, base, storage):
        value = seed(base)
        value["choices"]["storage"] = copy.deepcopy(storage)
        if value["choices"].get("storage_request") is not None:
            value["choices"]["storage_request"] = dict(mode=storage["spec"]["mode"],
                location=storage["spec"]["root_id"])
        return validated(value)

    def _proof(self, state):
        self._schema(state)
        snapshot, cp, pin, storage = self._current()
        config = configuration(snapshot.document())
        require(cp.maintenance == state["transition_id"] and cp.grant.epoch == state["epoch"]
                and config["transition_id"] == state["transition_id"]
                and config["revision"] == state["configuration_revision"]
                and self.original.snapshot.revision == state["base_setup_revision"]
                and sha(self.original._payload) == state["base_setup_sha256"]
                and sha(self._seed(self.original._payload,storage)) == state["seed_sha256"]
                and storage == state["storage"] and pin_record(pin) == state["pin"]
                and stable_records(snapshot.document()) == state["records_sha256"]
                and sha(snapshot.document()["records"][SLOT]) == state["summary_sha256"],
                "POST_ROOT_CHANGED")
        return snapshot, cp, pin

    def _state(self):
        current = self.context.transaction.read()
        return (None,0) if current is None else (self._schema(current.payload),current.revision)

    def _save(self, state, revision):
        state = self._schema(state)
        self.context.transaction.save(state,expected_revision=revision)
        require(self._state() == (state,revision+1), "POST_ROOT_UNCONFIRMED")
        return state

    def _archive_value(self, state):
        self.original._fresh()
        require(self.original.snapshot.revision == state["base_setup_revision"]
                and sha(self.original._payload) == state["base_setup_sha256"], "POST_ROOT_CHANGED")
        return dict(schema_version=1,kind="RECONFIGURATION_POST_ROOT_ORIGINAL_PROFILE",
            installation_id=self.original.installation_id,transition_id=state["transition_id"],
            base_setup_revision=state["base_setup_revision"],base_setup_sha256=state["base_setup_sha256"],
            profile=validated(self.original._payload))

    def _archive(self, state):
        current = self.context.archive.read()
        require(current is not None and current.revision == 1 and current.previous is None
                and current.payload == self._archive_value(state), "POST_ROOT_ARCHIVE")
        return validated(current.payload["profile"])

    def _profile(self, payload, base, state):
        value = validated(payload)
        expected = self._seed(base,state["storage"])
        require(all(value[k] == expected[k] for k in ("schema_version","installation_id","setup_nonce","operations"))
                and all(value["choices"].get(k) == expected["choices"].get(k)
                    for k in ("role","storage","storage_request"))
                and not (set(value) & DERIVED) and len(encoded(value)) <= 384*1024,
                "POST_ROOT_PROFILE")
        return value

    def _setup(self, state):
        require(state["phase"] == "STAGED", "POST_ROOT_INSPECT_REQUIRED")
        model = Setup(self.context.profile)
        self._profile(model._payload,self._archive(state),state)
        return model

    def _continue(self, state, revision):
        self._proof(state)
        require(state["phase"] == "STAGING", "POST_ROOT_INSPECT_REQUIRED")
        if self.context.archive.read() is None:
            self._proof(state)
            self.context.archive.save(self._archive_value(state),expected_revision=0)
        base = self._archive(state); initial = self._seed(base,state["storage"])
        self._profile(initial,base,state)
        self._proof(state)
        current = self.context.profile.read()
        if current is None:
            self.context.profile.save(initial,expected_revision=0)
            current = self.context.profile.read()
        require(current is not None and current.revision == 1 and current.previous is None
                and current.payload == initial, "POST_ROOT_INSPECT_REQUIRED")
        self._proof(state)
        self._save({**state,"phase":"STAGED"},revision)
        return self.view()

    def begin(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        require(self._state()[0] is None and self.context.profile.read() is None
                and self.context.archive.read() is None, "POST_ROOT_INSPECT_REQUIRED")
        snapshot,cp,pin,storage = self._current()
        config = configuration(snapshot.document())
        self.context.rebind.ctx.checkpoint.reserve(config["transition_id"],owner_authorized=True)
        snapshot,cp,pin,storage = self._current(); base = self.original._payload
        state = dict(schema_version=1,kind="RECONFIGURATION_POST_ROOT_CANDIDATE",
            installation_id=self.original.installation_id,transition_id=config["transition_id"],
            configuration_revision=config["revision"],base_setup_revision=self.original.snapshot.revision,
            base_setup_sha256=sha(base),seed_sha256=sha(self._seed(base,storage)),
            authority=dict(mode="NATIVE_DOCS",binding=asdict(snapshot.binding)),bindings=self._bindings(),
            pin=pin_record(pin),phase="STAGING",storage=storage,epoch=cp.grant.epoch,
            records_sha256=stable_records(snapshot.document()),summary_sha256=sha(snapshot.document()["records"][SLOT]))
        self._proof(state)
        return self._continue(self._save(state,0),1)

    def resume_staging(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        state,revision = self._state(); require(state is not None,"POST_ROOT_NOT_STARTED")
        return self._continue(state,revision)

    def view(self):
        state,_ = self._state()
        ready = False
        if state is not None and state["phase"] == "STAGED":
            self._proof(state)
            ready = self._reviewed_revision == self._setup(state).snapshot.revision
        return dict(phase="NOT_STARTED" if state is None else state["phase"],
            settings_validated=ready,runtime_active=False,automatic_replay=False)

    def choose(self, patch, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        state,_ = self._state(); require(state is not None,"POST_ROOT_NOT_STARTED")
        self._proof(state); model = self._setup(state)
        require(type(patch) is dict and set(patch) <= {"network_scope","credentials","descriptor","timing"},
                "POST_ROOT_PROFILE")
        value = copy.deepcopy(model._payload); value["choices"].update(copy.deepcopy(patch))
        self._profile(value,self._archive(state),state)
        model.choose(patch); self._reviewed_revision = None
        return self.view()

    def persist_credentials(self, store, resolver, selected, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        state,_ = self._state(); require(state is not None,"POST_ROOT_NOT_STARTED")
        self._proof(state); model = self._setup(state)
        model.persist_credentials(store,resolver,selected)
        self._profile(model._payload,self._archive(state),state)
        self._reviewed_revision = None
        return self.view()

    def _checker(self, checker, state):
        ctx = self.context.rebind.ctx
        require(type(checker) is Prerequisites and type(checker.storage) is CommissionedStorage
                and type(checker.storage.port) is NativeCommissioning
                and checker.source is ctx.source and checker.runtime == ctx.runtime
                and checker.storage.port.drive is ctx.storage_port.drive
                and checker.storage.port.docs is ctx.storage_port.docs
                and checker.storage.port.spec == storage_spec(state["storage"])[0]
                and checker.storage.port.root_transition == state["transition_id"], "POST_ROOT_CHECKER")
        return checker

    def review(self, checker):
        self._reviewed_revision = None
        state,_ = self._state(); require(state is not None,"POST_ROOT_NOT_STARTED")
        self._proof(state); model = self._setup(state)
        result = model.review(self._checker(checker,state))
        self._profile(model._payload,self._archive(state),state); self._proof(state)
        if result["settings_validated"]:
            self._reviewed_revision = model.snapshot.revision
        return {**result,**self.view()}

    def require_validated(self, checker):
        require(self.review(checker)["settings_validated"], "POST_ROOT_REVALIDATION_REQUIRED")
        state,_ = self._state(); self._proof(state); model = self._setup(state)
        revision, setup_sha256 = model.snapshot.revision, sha(model._payload)
        validation = self._checker(checker,state).validate(copy.deepcopy(model._payload))
        require(pin_record(validation.pin) == state["pin"], "POST_ROOT_PIN_CHANGED")
        self._proof(state); model._fresh()
        require(model.snapshot.revision == revision and sha(model._payload) == setup_sha256,
                "POST_ROOT_CHANGED")
        return PostRootValidation(state["transition_id"],state["configuration_revision"],state["epoch"],
            revision,setup_sha256,copy.deepcopy(state["storage"]),validation,self)

    def require_current(self, proof, checker):
        require(type(proof) is PostRootValidation and proof._origin is self,"POST_ROOT_REVALIDATION_REQUIRED")
        state,_ = self._state(); require(state is not None,"POST_ROOT_NOT_STARTED")
        self._proof(state); model = self._setup(state)
        require(proof.transition_id == state["transition_id"]
                and proof.configuration_revision == state["configuration_revision"] and proof.epoch == state["epoch"]
                and proof.storage == state["storage"] and proof.revision == model.snapshot.revision
                and proof.setup_sha256 == sha(model._payload), "POST_ROOT_CHANGED")
        validation = self._checker(checker,state).validate(copy.deepcopy(model._payload))
        require(pin_record(validation.pin) == state["pin"],"POST_ROOT_PIN_CHANGED")
        self._proof(state); model._fresh()
        require(model.snapshot.revision == proof.revision and sha(model._payload) == proof.setup_sha256,
                "POST_ROOT_CHANGED")
        return proof

    def recover_local(self, which, *, owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        require(which in {"transaction","archive","profile"},"POST_ROOT_RECOVERY")
        state = None if which == "transaction" else self._state()[0]
        require(which == "transaction" or state is not None,"POST_ROOT_NOT_STARTED")
        store = getattr(self.context,which)
        with store.native.locked() as port:
            pending,raw = port.read("settings.pending"),port.read("settings.json")
            if pending is None:return "NO_PENDING"
            candidate = store._decode(pending,port.binding)
            current = None if raw is None else store._decode(raw,port.binding)
            require(candidate.revision == (0 if current is None else current.revision)+1
                    and candidate.previous == (None if current is None else current.payload),"POST_ROOT_RECOVERY")
        if which == "transaction":state = self._schema(candidate.payload)
        self._proof(state)
        if which == "archive":
            require(candidate.revision == 1 and candidate.previous is None
                    and candidate.payload == self._archive_value(state),"POST_ROOT_ARCHIVE")
        elif which == "profile":
            base = self._archive(state); self._profile(candidate.payload,base,state)
            if state["phase"] == "STAGING":
                require(candidate.revision == 1 and candidate.payload == self._seed(base,state["storage"]),
                        "POST_ROOT_RECOVERY")
        with store.native.locked() as port:
            require(port.read("settings.pending") == pending and port.read("settings.json") == raw,
                    "POST_ROOT_RECOVERY")
            port.promote(); require(port.read("settings.json") == pending,"POST_ROOT_UNCONFIRMED")
        self._reviewed_revision = None
        return "INSPECT_REQUIRED"
