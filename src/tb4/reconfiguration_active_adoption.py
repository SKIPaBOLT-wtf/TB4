"""Current-role adoption of one already ACTIVE fixed native Docs authority.

Only this installation's protected profiles change. No former host/store, remote
mutation, effect replay, ACK barrier or saved readiness grant is an input.
"""
from dataclasses import asdict, dataclass
import copy
import hashlib

from .ballpark import catalogue, DEVICE_PROPERTIES, validate
from .ballpark_records import receipt, shared, validate_receipt
from .ballpark_setup import pin_record, restore_pin, validate_pin
from .commissioning_checks import CommissionedStorage, Prerequisites
from .commissioning_records import current_record
from .commissioning_state import Setup, storage_spec, validated
from .configuration_contract import configuration, require
from .drive.commissioning import SetupSpec, digest
from .drive.commissioning_bootstrap import AuthorityHandle
from .drive.commissioning_native import NativeCommissioning
from .exchange_layout import MAX_GENERATION, encoded
from .instructions import check_boundary, select
from .private_settings import MAX_BYTES, PrivateSettings
from .reconfiguration_admission import AdmissionContext, ConfigurationAdmission
from .reconfiguration_candidate import DERIVED, native_binding, seed, SCHEMA, SCHEMA_SHA256
from .reconfiguration_effects import covered, ledger, SLOT, SCHEMA as EFFECT_SCHEMA, SCHEMA_SHA256 as EFFECT_SHA
from .reconfiguration_inspection import inspect
from .reconfiguration_maintenance import hex64, sha, WAL_SCHEMA, WAL_SCHEMA_SHA256
from .watchdog.checkpoint_store import SCHEMA as CP_SCHEMA, SCHEMA_SHA256 as CP_SHA
from .watchdog.leadership_runtime import Action, Capabilities
from .drive.leadership import ClockSample, Grant

SCHEMA_DEFINITION = "activeAdoption"
FIELDS = frozenset({"schema_version", "kind", "installation_id", "configuration",
    "base_revision", "base_sha256", "seed_sha256", "storage", "authority", "bindings",
    "pin", "epoch", "controls_sha256", "phase", "promotion"})


@dataclass(frozen=True, repr=False)
class ActiveAdoptionContext:
    local: AdmissionContext
    profile: PrivateSettings
    archive: PrivateSettings
    transaction: PrivateSettings


def current_admission(local):
    """Restart from this current protected profile; adoption WAL is not a grant."""
    from dataclasses import replace
    require(type(local) is AdmissionContext and type(local.checker.storage.port) is NativeCommissioning,
            "ACTIVE_ADOPTION_CONTEXT")
    ConfigurationAdmission(local)
    frame = local.profile.read()
    require(frame is not None, "ACTIVE_ADOPTION_PROFILE")
    payload = validated(frame.payload)
    spec,_ = storage_spec(payload["choices"]["storage"])
    old = local.checker
    port = NativeCommissioning(old.storage.port.drive,old.storage.port.docs,spec,llm_authorized=True,
        root_transition=payload["choices"]["storage"].get("root_transition"))
    checker = Prerequisites(environment=old.environment,storage=CommissionedStorage(port),credentials=old.credentials,
        source=old.source,runtime=old.runtime,clock=old.clock)
    return ConfigurationAdmission(replace(local,checker=checker))


class ActiveAdoption:
    def __init__(self, context):
        require(type(context) is ActiveAdoptionContext and type(context.local) is AdmissionContext
                and type(context.local.checker.storage.port) is NativeCommissioning
                and all(type(s) is PrivateSettings for s in (
                    context.profile, context.archive, context.transaction)), "ACTIVE_ADOPTION_CONTEXT")
        # Reuse actual native profile/checkpoint/leadership port validation.
        ConfigurationAdmission(context.local)
        self.context = context
        self._bindings()

    def _bindings(self, *, held=None):
        held = {} if held is None else held
        stores = {"original":self.context.local.profile, "checkpoint":self.context.local.checkpoint.store,
            "profile":self.context.profile, "archive":self.context.archive, "transaction":self.context.transaction}
        value = {k:held[k] if k in held else native_binding(v) for k,v in stores.items()}
        require(len(set(value.values())) == len(stores), "ACTIVE_ADOPTION_STORE_ALIAS")
        return value

    def _schema(self, value, *, held=None):
        require(type(value) is dict and set(value) == FIELDS
                and type(value["schema_version"]) is int and value["schema_version"] == 1
                and value["kind"] == "RECONFIGURATION_ACTIVE_ADOPTION"
                and value["installation_id"] == self.context.local.leadership.actor
                and all(type(value[k]) is int and 1 <= value[k] <= MAX_GENERATION for k in ("base_revision","epoch"))
                and value["base_revision"] < MAX_GENERATION
                and all(hex64(value[k]) for k in ("base_sha256","seed_sha256","controls_sha256"))
                and value["bindings"] == self._bindings(held=held)
                and type(value["phase"]) is str and value["phase"] in {"STAGING","STAGED","PREPARED","PROMOTED"},
                "ACTIVE_ADOPTION_SCHEMA")
        from .configuration_contract import marker
        require(marker(value["configuration"])["phase"] == "ACTIVE", "ACTIVE_ADOPTION_SCHEMA")
        spec,handle = storage_spec(value["storage"])
        binding = self.context.local.leadership.backend.binding
        require(spec.mode == "NATIVE_DOCS" and spec.domain_id == binding.domain_id
                and handle.object_id == binding.document_id and handle.tab_id == binding.tab_id
                and value["authority"] == dict(mode="NATIVE_DOCS",binding=asdict(binding)), "ACTIVE_ADOPTION_BINDING")
        validate_pin(value["pin"])
        p = value["promotion"]
        require((value["phase"] in {"STAGING","STAGED"} and p is None)
                or (value["phase"] in {"PREPARED","PROMOTED"} and type(p) is dict
                    and set(p) == {"stage_revision","stage_sha256","payload_sha256","decision"}
                    and type(p["stage_revision"]) is int and 1 <= p["stage_revision"] <= MAX_GENERATION
                    and hex64(p["stage_sha256"]) and hex64(p["payload_sha256"])), "ACTIVE_ADOPTION_SCHEMA")
        if p is not None:
            decision = p["decision"]
            require(type(decision) is dict and set(decision) == {"id","at","kind","candidate_digest"}
                    and hex64(decision["id"]) and hex64(decision["candidate_digest"])
                    and type(decision["at"]) is int and 0 <= decision["at"] <= 10**12
                    and decision["kind"] == "LOCAL_OWNER_CONFIRMATION", "ACTIVE_ADOPTION_SCHEMA")
        require(len(encoded(value)) <= 64*1024, "ACTIVE_ADOPTION_SIZE")
        return copy.deepcopy(value)

    def _state(self):
        frame = self.context.transaction.read()
        return (None,0) if frame is None else (self._schema(frame.payload),frame.revision)

    def _save(self, state, revision):
        self.context.transaction.save(self._schema(state),expected_revision=revision)
        require(self._state() == (state,revision+1), "ACTIVE_ADOPTION_UNCONFIRMED")

    def _current(self, payload, *, state=None, checkpoint=None):
        ctx = self.context.local
        require(payload["installation_id"] == ctx.leadership.actor
                and payload["choices"]["role"] == "watchdog" and payload["state"] != "CANCELLED",
                "ACTIVE_ADOPTION_PROFILE")
        cp = ctx.checkpoint.read() if checkpoint is None else checkpoint
        require(type(cp.grant) is Grant and cp.election is None, "ACTIVE_ADOPTION_LOCAL_UNRESOLVED")
        caps,sample = ctx.capabilities(),ctx.clock()
        require(type(caps) is Capabilities and caps.installation_id == payload["installation_id"]
                and caps.observe is True and caps.coordinate is True and type(caps.actions) is frozenset
                and all(type(a) is Action for a in caps.actions) and Action.IDENTITY in caps.actions,
                "ACTIVE_ADOPTION_CAPABILITIES")
        require(type(sample) is ClockSample and sample.wall_trusted and sample.monotonic_trusted,
                "ACTIVE_ADOPTION_CLOCK")
        observed = ctx.leadership.observe(sample)
        require(ctx.leadership._owns(observed.leader,observed.request,cp.grant), "OWNER_SUPERSEDED")
        doc = observed.snapshot.document()
        config = configuration(doc)
        require(config is not None and config["phase"] == "ACTIVE"
                and cp.maintenance in {None,config["transition_id"]}, "ACTIVE_ADOPTION_CONFIGURATION")
        # A new owner adopts committed routing, not an unresolved root plan.
        effects = ledger(doc["records"][SLOT])
        require(effects is not None and covered(doc,config["transition_id"])
                and "root_plan" not in effects and "folder_plan" not in effects, "ACTIVE_ADOPTION_RESOLUTION")
        require(not any(b.kind.startswith("LOCAL_") for b in inspect(
            observed.snapshot,setup_payload=payload,checkpoint=cp).blockers), "ACTIVE_ADOPTION_LOCAL_UNRESOLVED")
        current_shared = shared(doc)
        source,_ = storage_spec(payload["choices"]["storage"])
        body = doc["records"]["global.commissioning"]["body"]
        require(type(body) is dict, "ACTIVE_ADOPTION_STORAGE")
        target = SetupSpec(body.get("root_id"),doc["domain_id"],body.get("setup_id"),
            body.get("bootstrap_actor"),body.get("mode"),source.capacity)
        require(target.mode == source.mode == "NATIVE_DOCS"
                and target.domain_id == source.domain_id and target.setup_id == source.setup_id
                and target.bootstrap_actor == source.bootstrap_actor, "ACTIVE_ADOPTION_STORAGE")
        proof = body.get("reconfiguration")
        transition = None if proof is None else proof.get("transition_id")
        current_record(doc,target,root_transition=transition)
        binding = observed.snapshot.binding
        old_handle = storage_spec(payload["choices"]["storage"])[1]
        require(old_handle.object_id == binding.document_id and old_handle.tab_id == binding.tab_id
                and ctx.checker.storage.port.authority(old_handle).binding == binding, "ACTIVE_ADOPTION_AUTHORITY")
        handle = AuthorityHandle(binding.document_id,digest([
            target.mode,target.root_id,target.domain_id,binding.document_id,binding.tab_id]),binding.tab_id)
        storage = dict(spec=asdict(target),authority=handle.record())
        if transition is not None:storage["root_transition"] = transition
        controls = sha({k:doc["records"][k] for k in (
            "global.settings","global.registry","global.commissioning")})
        pin = select(ctx.checker.source,ctx.checker.runtime) if state is None else restore_pin(
            ctx.checker.source,state["pin"],ctx.checker.runtime)
        require(all(hashlib.sha256(pin.read(path)).hexdigest() == expected for path,expected in (
            (SCHEMA,SCHEMA_SHA256),(EFFECT_SCHEMA,EFFECT_SHA),(WAL_SCHEMA,WAL_SCHEMA_SHA256),(CP_SCHEMA,CP_SHA))),
            "ACTIVE_ADOPTION_INSTRUCTIONS")
        if state is not None:
            require(config == state["configuration"] and storage == state["storage"]
                    and cp.maintenance == config["transition_id"] and cp.grant.epoch == state["epoch"]
                    and controls == state["controls_sha256"] and pin_record(pin) == state["pin"],
                    "ACTIVE_ADOPTION_CHANGED")
        return observed.snapshot,cp,pin,storage,controls,current_shared

    def _seed(self, base, state, current_shared):
        value = seed(base)
        local = validate(value["choices"]["descriptor"])
        require([(d["device_id"],d["alias"]) for d in local["devices"]] == [
            (d["device_id"],d["alias"]) for d in current_shared["devices"]], "ACTIVE_ADOPTION_IDENTITIES")
        for own,current in zip(local["devices"],current_shared["devices"]):
            own.update({k:copy.deepcopy(current[k]) for k in DEVICE_PROPERTIES})
        local["revision"] = current_shared["revision"]
        value["choices"]["descriptor"] = validate(local)
        value["choices"]["storage"] = copy.deepcopy(state["storage"])
        if value["choices"].get("storage_request") is not None:
            value["choices"]["storage_request"] = dict(mode="NATIVE_DOCS",location=state["storage"]["spec"]["root_id"])
        return validated(value)

    def _archive_value(self, state, base):
        require(sha(base) == state["base_sha256"], "ACTIVE_ADOPTION_PROFILE_CHANGED")
        return dict(schema_version=1,kind="RECONFIGURATION_ACTIVE_ADOPTION_ORIGINAL",
            installation_id=state["installation_id"],configuration=state["configuration"],
            base_revision=state["base_revision"],base_sha256=state["base_sha256"],profile=validated(base))

    def _base(self, state, snapshot, *, archive_snapshot=None):
        archive = self.context.archive.read() if archive_snapshot is None else archive_snapshot
        if archive is None:
            require(snapshot is not None and snapshot.revision == state["base_revision"]
                    and sha(snapshot.payload) == state["base_sha256"], "ACTIVE_ADOPTION_PROFILE_CHANGED")
            return validated(snapshot.payload)
        require(archive.revision == 1 and archive.previous is None
                and archive.payload == self._archive_value(state,archive.payload["profile"]), "ACTIVE_ADOPTION_ARCHIVE")
        return validated(archive.payload["profile"])

    def _proof(self, state, *, held=None, original_snapshot=None, archive_snapshot=None):
        self._schema(state,held=held)
        snapshot = self.context.local.profile.read() if original_snapshot is None else original_snapshot
        base = self._base(state,snapshot,archive_snapshot=archive_snapshot)
        observed,cp,pin,storage,controls,current_shared = self._current(base,state=state)
        initial = self._seed(base,state,current_shared)
        # Timing belongs to the coherent shared configuration.
        initial["choices"]["timing"] = copy.deepcopy(observed.document()["records"]["global.settings"]["body"]["timing"])
        initial = validated(initial)
        require(sha(initial) == state["seed_sha256"], "ACTIVE_ADOPTION_CHANGED")
        promoted = None
        if state["promotion"] is not None:
            stage = self.context.profile.read()
            require(stage is not None and stage.revision == state["promotion"]["stage_revision"]
                    and sha(stage.payload) == state["promotion"]["stage_sha256"], "ACTIVE_ADOPTION_STAGE_CHANGED")
            value = self._profile(stage.payload,base,state,current_shared)
            promoted = copy.deepcopy(value)
            draft = dict(pin=state["pin"],decision=state["promotion"]["decision"],candidate=value["choices"]["descriptor"])
            active = receipt(draft,value["choices"]["timing"])
            active["adoption"] = dict(schema_version=1,kind="CURRENT_ACTIVE_ADOPTION",
                configuration=copy.deepcopy(state["configuration"]),authority=copy.deepcopy(state["authority"]),
                provenance=copy.deepcopy(observed.document()["records"]["global.registry"]["body"]["provenance"]))
            validate_receipt(active,value["choices"])
            promoted["ballpark_publication"] = dict(active=active,pending=None)
            promoted.update(state="INCOMPLETE",reason="REVALIDATION_REQUIRED")
            promoted = validated(promoted)
            require(sha(promoted) == state["promotion"]["payload_sha256"], "ACTIVE_ADOPTION_CHANGED")
        require(snapshot is not None, "ACTIVE_ADOPTION_PROFILE")
        if snapshot.revision == state["base_revision"] and snapshot.payload == base:status = "ORIGINAL"
        else:
            require(promoted is not None and snapshot.revision == state["base_revision"]+1
                    and snapshot.payload == promoted and snapshot.previous == base, "ACTIVE_ADOPTION_PROFILE_CHANGED")
            status = "PROMOTED"
        if original_snapshot is None:
            require(self.context.local.profile.read() == snapshot, "ACTIVE_ADOPTION_PROFILE_CHANGED")
        return initial,promoted,status,base,observed,cp,pin

    def _profile(self, payload, base, state, current_shared):
        value = validated(payload)
        expected = self._seed(base,state,current_shared)
        require(not set(value)&DERIVED and len(encoded(value)) <= 384*1024
                and value["state"] != "CANCELLED"
                and all(value[k] == expected[k] for k in (
                    "schema_version","installation_id","setup_nonce","operations"))
                and all(value.get(k) == expected.get(k) for k in ("credential_image","network_table"))
                and all(value["choices"].get(k) == expected["choices"].get(k) for k in ("role","storage","storage_request"))
                and catalogue(value["choices"]["descriptor"]) == current_shared, "ACTIVE_ADOPTION_PROFILE")
        return value

    def _checker(self, state):
        old = self.context.local.checker
        spec,_ = storage_spec(state["storage"])
        port = NativeCommissioning(old.storage.port.drive,old.storage.port.docs,spec,llm_authorized=True,
            root_transition=state["storage"].get("root_transition"))
        return Prerequisites(environment=old.environment,storage=CommissionedStorage(port),credentials=old.credentials,
            source=old.source,runtime=old.runtime,clock=old.clock)

    def _qualified(self, state, *, held=None, original_snapshot=None):
        before = self._proof(state,held=held,original_snapshot=original_snapshot)
        stage = self.context.profile.read()
        require(stage is not None, "ACTIVE_ADOPTION_STAGE")
        self._profile(stage.payload,before[3],state,shared(before[4].document()))
        require(stage.payload["choices"]["timing"] == before[4].document()["records"]["global.settings"]["body"]["timing"],
                "ACTIVE_ADOPTION_TIMING")
        validation = self._checker(state).validate(copy.deepcopy(stage.payload))
        require(pin_record(validation.pin) == state["pin"], "ACTIVE_ADOPTION_INSTRUCTIONS")
        check_boundary(self.context.local.checker.source,validation.pin,self.context.local.checker.runtime)
        after = self._proof(state,held=held,original_snapshot=original_snapshot)
        require(self.context.profile.read() == stage and before[:4] == after[:4] and before[5] == after[5],
                "ACTIVE_ADOPTION_CHANGED")
        return after,stage

    def _continue(self, state, revision):
        require(state["phase"] == "STAGING", "ACTIVE_ADOPTION_INSPECT_REQUIRED")
        initial,_,status,base,*_ = self._proof(state)
        require(status == "ORIGINAL", "ACTIVE_ADOPTION_INSPECT_REQUIRED")
        if self.context.archive.read() is None:
            self._proof(state);self.context.archive.save(self._archive_value(state,base),expected_revision=0)
        self._proof(state)
        if self.context.profile.read() is None:self.context.profile.save(initial,expected_revision=0)
        stage = self.context.profile.read()
        require(stage.revision == 1 and stage.previous is None and stage.payload == initial, "ACTIVE_ADOPTION_INSPECT_REQUIRED")
        self._proof(state);self._save({**state,"phase":"STAGED"},revision)
        return self.view()

    def begin(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        require(self._state()[0] is None and self.context.profile.read() is None
                and self.context.archive.read() is None, "ACTIVE_ADOPTION_INSPECT_REQUIRED")
        original = self.context.local.profile.read()
        require(original is not None, "ACTIVE_ADOPTION_PROFILE")
        base = validated(original.payload)
        snap,cp,pin,storage,controls,current_shared = self._current(base)
        config = configuration(snap.document())
        state = dict(schema_version=1,kind="RECONFIGURATION_ACTIVE_ADOPTION",installation_id=base["installation_id"],
            configuration=config,base_revision=original.revision,base_sha256=sha(base),seed_sha256="0"*64,
            storage=storage,authority=dict(mode="NATIVE_DOCS",binding=asdict(snap.binding)),
            bindings=self._bindings(),pin=pin_record(pin),epoch=cp.grant.epoch,controls_sha256=controls,
            phase="STAGING",promotion=None)
        initial = self._seed(base,state,current_shared)
        initial["choices"]["timing"] = copy.deepcopy(snap.document()["records"]["global.settings"]["body"]["timing"])
        state["seed_sha256"] = sha(validated(initial))
        # The protected transaction precedes the local runtime reservation and profiles.
        self._save(state,0)
        self.context.local.checkpoint.reserve(config["transition_id"],owner_authorized=True)
        return self._continue(state,1)

    def resume_staging(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        state,revision = self._state();require(state is not None and state["phase"] == "STAGING", "ACTIVE_ADOPTION_INSPECT_REQUIRED")
        base = self._base(state,self.context.local.profile.read())
        self._current(base)  # Fresh role/controls before reserving own checkpoint.
        self.context.local.checkpoint.reserve(state["configuration"]["transition_id"],owner_authorized=True)
        return self._continue(state,revision)

    def choose(self, patch, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        state,_ = self._state();require(state is not None and state["phase"] == "STAGED", "ACTIVE_ADOPTION_INSPECT_REQUIRED")
        proof = self._proof(state);model = Setup(self.context.profile)
        require(type(patch) is dict and set(patch) <= {"network_scope","descriptor"}, "ACTIVE_ADOPTION_PROFILE")
        value = copy.deepcopy(model._payload);value["choices"].update(copy.deepcopy(patch))
        self._profile(value,proof[3],state,shared(proof[4].document()))
        model.choose(patch)
        return self.view()

    def prepare(self, *, owner_authorized=False, decided_at):
        require(owner_authorized is True and type(decided_at) is int and 0 <= decided_at <= 10**12,
                "CONFIGURATION_OWNER_REQUIRED")
        state,revision = self._state();require(state is not None and state["phase"] == "STAGED", "ACTIVE_ADOPTION_INSPECT_REQUIRED")
        proof,stage = self._qualified(state)
        require(self.context.local.clock().utc == decided_at, "ACTIVE_ADOPTION_CLOCK")
        decision = dict(id=sha(["active-adoption",state["installation_id"],state["configuration"],
            state["epoch"],stage.revision,sha(stage.payload),decided_at]),at=decided_at,kind="LOCAL_OWNER_CONFIRMATION",
            candidate_digest=sha(stage.payload["choices"]["descriptor"]))
        draft = dict(pin=state["pin"],decision=decision,candidate=stage.payload["choices"]["descriptor"])
        active = receipt(draft,stage.payload["choices"]["timing"])
        active["adoption"] = dict(schema_version=1,kind="CURRENT_ACTIVE_ADOPTION",configuration=state["configuration"],
            authority=state["authority"],provenance=proof[4].document()["records"]["global.registry"]["body"]["provenance"])
        promoted = validated({**stage.payload,"ballpark_publication":dict(active=active,pending=None),
            "state":"INCOMPLETE","reason":"REVALIDATION_REQUIRED"})
        prepared = {**state,"phase":"PREPARED","promotion":dict(stage_revision=stage.revision,
            stage_sha256=sha(stage.payload),payload_sha256=sha(promoted),decision=decision)}
        self._qualified(prepared);self._budget(promoted,proof[3],state["base_revision"])
        self._save(prepared,revision)
        return "PREPARED"

    def _budget(self, payload, base, revision):
        with self.context.local.profile.native.locked() as port:
            frame = dict(schema_version=1,binding=port.binding,revision=revision+1,payload=payload,previous=base,digest="0"*64)
            require(len(encoded(frame)) <= MAX_BYTES, "ACTIVE_ADOPTION_NATIVE_SIZE")

    def advance(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        state,revision = self._state();require(state is not None and state["phase"] in {"PREPARED","PROMOTED"},
                "ACTIVE_ADOPTION_INSPECT_REQUIRED")
        self._qualified(state)
        if state["phase"] == "PROMOTED":return self.inspect()
        store = self.context.transaction
        with store.native.locked() as port:
            current = store._decode(port.read("settings.json"),port.binding)
            require(port.read("settings.pending") is None and current.payload == state and current.revision == revision,
                    "ACTIVE_ADOPTION_CHANGED")
            held = {"transaction":sha(port.binding)}
            proof,_ = self._qualified(state,held=held)
            if proof[2] == "ORIGINAL":
                self._budget(proof[1],proof[3],state["base_revision"])
                self.context.local.profile.save(proof[1],expected_revision=state["base_revision"])
            require(self._qualified(state,held=held)[0][2] == "PROMOTED", "ACTIVE_ADOPTION_UNCONFIRMED")
            desired = {**state,"phase":"PROMOTED"}
            require(store._save_locked(port,desired,expected_revision=revision).payload == desired, "ACTIVE_ADOPTION_UNCONFIRMED")
        return self.inspect()

    def inspect(self):
        state,_ = self._state();require(state is not None and state["phase"] in {"PREPARED","PROMOTED"},
                "ACTIVE_ADOPTION_INSPECT_REQUIRED")
        proof,_ = self._qualified(state)
        return "PROFILE_PROMOTED" if proof[2] == "PROMOTED" else "PREPARED"

    def admission(self):
        state,_ = self._state();require(state is not None and state["phase"] in {"PREPARED","PROMOTED"},
                "ACTIVE_ADOPTION_INSPECT_REQUIRED")
        require(self.inspect() == "PROFILE_PROMOTED", "ACTIVE_ADOPTION_INSPECT_REQUIRED")
        return current_admission(self.context.local)

    def recover_local(self, which, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        require(which in {"transaction","archive","profile","original"}, "ACTIVE_ADOPTION_RECOVERY")
        store = self.context.local.profile if which == "original" else getattr(self.context,which)
        with store.native.locked() as port:
            pending,raw = port.read("settings.pending"),port.read("settings.json")
            if pending is None:return "NO_PENDING"
            candidate = store._decode(pending,port.binding)
            current = None if raw is None else store._decode(raw,port.binding)
            require(candidate.revision == (0 if current is None else current.revision)+1
                    and candidate.previous == (None if current is None else current.payload), "ACTIVE_ADOPTION_RECOVERY")
        state = self._schema(candidate.payload) if which == "transaction" else self._state()[0]
        require(state is not None, "ACTIVE_ADOPTION_RECOVERY")
        # STAGING may have persisted before its same local reservation.
        if state["phase"] == "STAGING":
            base = self._base(state,self.context.local.profile.read(),
                archive_snapshot=candidate if which == "archive" else None)
            snap,cp,pin,storage,controls,_ = self._current(base)
            require(configuration(snap.document()) == state["configuration"] and storage == state["storage"]
                    and controls == state["controls_sha256"] and cp.grant.epoch == state["epoch"]
                    and pin_record(pin) == state["pin"], "ACTIVE_ADOPTION_CHANGED")
            self.context.local.checkpoint.reserve(state["configuration"]["transition_id"],owner_authorized=True)
        proof = self._proof(state,original_snapshot=current if which == "original" else None,
            archive_snapshot=candidate if which == "archive" else None)
        if which == "original":
            proof,_ = self._qualified(state,original_snapshot=current)
            require(proof[2] == "ORIGINAL" and candidate.revision == state["base_revision"]+1
                    and candidate.payload == proof[1], "ACTIVE_ADOPTION_RECOVERY")
        elif which == "archive":
            require(candidate.revision == 1 and candidate.previous is None
                    and candidate.payload == self._archive_value(state,proof[3]), "ACTIVE_ADOPTION_ARCHIVE")
        elif which == "profile":
            self._profile(candidate.payload,proof[3],state,shared(proof[4].document()))
            require(state["phase"] == "STAGING" and candidate.revision == 1 and candidate.payload == proof[0],
                    "ACTIVE_ADOPTION_RECOVERY")
        elif state["phase"] in {"PREPARED","PROMOTED"}:
            qualified,_ = self._qualified(state)
            require(state["phase"] != "PROMOTED" or qualified[2] == "PROMOTED", "ACTIVE_ADOPTION_RECOVERY")
        with store.native.locked() as port:
            require(port.read("settings.pending") == pending and port.read("settings.json") == raw, "ACTIVE_ADOPTION_RECOVERY")
            port.promote();require(port.read("settings.json") == pending, "ACTIVE_ADOPTION_UNCONFIRMED")
        return "INSPECT_REQUIRED"

    def view(self):
        state,_ = self._state()
        return dict(phase="NOT_STARTED" if state is None else state["phase"],runtime_active=False,automatic_replay=False)
