"""Unreleased exact existing-Docs root moves; final routing promotion is separate.

Each newly sent metadata-only move has native intent and shared UNKNOWN first.
Restart/unknown paths inspect the same object; they never repeat the request.
Original profile, ordering document and workload rows are retained unchanged.
"""
from __future__ import annotations

import copy
import base64
from dataclasses import asdict, dataclass, replace
import hashlib
import json

from .ballpark_setup import pin_record, validate_pin
from .commissioning_state import storage_spec
from .configuration_contract import configuration, require
from .drive.commissioning import Allocation, RAW_LIMIT, digest, object_id
from .drive.authority_transaction import OwnerGuard
from .drive.commissioning_bootstrap import AuthorityHandle
from .drive.commissioning_native import NativeCommissioning, FIELDS
from .drive.docs_authority import AuthorityError
from .drive.leadership import ClockSample, Grant
from .exchange_layout import MAX_GENERATION
from .private_settings import PrivateSettings, encoded
from .reconfiguration_candidate import Candidate, native_binding
from .reconfiguration_effects import Effects, SLOT, ledger
from .reconfiguration_evidence import EvidenceReceipt
from .reconfiguration_maintenance import hex64, sha
from .watchdog.checkpoint_store import NativeCheckpoint
from .watchdog.leadership_runtime import Action, Capabilities

SCHEMA = "protocol/reconfiguration-root-v1.schema.json"
SCHEMA_SHA256 = "4a5ddeb905e347813189dfff9b856e0250b3021e2805f60ab0a3025b8e3e7b18"
FIELDS_STATE = frozenset({"schema_version","kind","installation_id","transition_id",
    "configuration_revision","base_revision","base_sha256","candidate_revision","candidate_sha256",
    "authority","target_root","records_sha256","objects","index","pending","phase","pin","binding"})


def stable_records(document):
    return sha({k:v for k,v in document["records"].items()
                if k not in {"global.leadership","global.force_request",SLOT}})


@dataclass(frozen=True, repr=False)
class RootContext:
    candidate: Candidate
    checker: object
    store: PrivateSettings
    target_root: str


@dataclass(frozen=True, repr=False)
class RootRevocation:
    transition_id: str
    operation_id: str
    epoch: int
    index: int
    revision: int
    payload_sha256: str
    previous_sha256: str
    binding: str
    _origin: object


class DocsRootMoves:
    def __init__(self, context):
        require(type(context) is RootContext and type(context.candidate) is Candidate
                and type(context.store) is PrivateSettings and object_id(context.target_root),
                "CONFIGURATION_ROOT_CONTEXT")
        self.context = context
        self.maintenance = context.candidate.context.maintenance
        self.ctx = self.maintenance.context
        require(type(self.ctx.storage_port) is NativeCommissioning
                and type(self.ctx.effects) is Effects and type(self.ctx.checkpoint) is NativeCheckpoint,
                "CONFIGURATION_ROOT_CONTEXT")
        self.old = self.ctx.storage_port
        require(context.target_root != self.old.root_id, "CONFIGURATION_ROOT_UNCHANGED")
        self.new = NativeCommissioning(self.old.drive,self.old.docs,
            replace(self.old.spec,root_id=context.target_root),llm_authorized=True,
            root_transition=self.ctx.baseline.transition_id)
        self._binding()

    def _binding(self):
        value = native_binding(self.context.store)
        candidate = self.context.candidate.context
        old = [self.ctx.setup.store,self.ctx.store,self.ctx.baseline.store,self.ctx.checkpoint.store,
               self.ctx.effects.store,candidate.profile,candidate.archive,candidate.transaction,candidate.resolution.store]
        require(value not in {native_binding(s) for s in old}, "CONFIGURATION_ROOT_STORE_ALIAS")
        return value

    def _profile(self):
        self.ctx.setup._fresh()
        state,_ = self.context.candidate._state()
        require(state is not None, "CONFIGURATION_ROOT_CANDIDATE")
        model = self.context.candidate._setup(state)
        return model

    def _original_document(self):
        maintenance,_ = self.maintenance._state()
        require(maintenance is not None and maintenance["resolution"] is not None,
                "CONFIGURATION_ROOT_EVIDENCE")
        receipt = EvidenceReceipt(**maintenance["resolution"]["evidence"])
        proof = self.context.candidate.context.resolution.read(receipt)
        return json.loads(base64.b64decode(proof["image"],validate=True))

    def _validate(self, value):
        require(type(value) is dict and set(value) == FIELDS_STATE
                and type(value["schema_version"]) is int and value["schema_version"] == 1
                and value["kind"] == "RECONFIGURATION_DOCS_ROOT_MOVES"
                and value["installation_id"] == self.ctx.setup.installation_id
                and value["transition_id"] == self.ctx.baseline.transition_id
                and value["target_root"] == self.context.target_root
                and value["binding"] == self._binding(), "CONFIGURATION_ROOT_WAL")
        require(all(type(value[k]) is int and 1 <= value[k] <= MAX_GENERATION
                    for k in ("configuration_revision","base_revision","candidate_revision"))
                and all(hex64(value[k]) for k in ("base_sha256","candidate_sha256","records_sha256")),
                "CONFIGURATION_ROOT_WAL")
        require(value["authority"] == asdict(self.ctx.leadership.backend.binding)
                and type(value["phase"]) is str and value["phase"] in {"MOVING","MOVED"},
                "CONFIGURATION_ROOT_WAL")
        validate_pin(value["pin"])
        objects = value["objects"]
        keys = self.old.spec.artifact_keys + ("authority",)
        require(type(objects) is list and len(objects) == len(keys) <= 129
                and type(value["index"]) is int and 0 <= value["index"] <= len(keys)
                and (value["phase"] == "MOVED") == (value["index"] == len(keys)), "CONFIGURATION_ROOT_WAL")
        refs = set()
        original = self._original_document()
        require(value["records_sha256"] == stable_records(original), "CONFIGURATION_ROOT_WAL")
        for key,item in zip(keys,objects):
            require(type(item) is dict and set(item) == {"key","id","size","before_seal","after_seal"}
                    and item["key"] == key and object_id(item["id"]) and item["id"] not in refs
                    and hex64(item["before_seal"]) and hex64(item["after_seal"]), "CONFIGURATION_ROOT_WAL")
            require(item["size"] is None if key == "authority" else
                    type(item["size"]) is int and 0 <= item["size"] <= RAW_LIMIT, "CONFIGURATION_ROOT_WAL")
            if key == "authority":
                _,handle = storage_spec(self.ctx.setup.private_choices()["storage"])
                require(item["id"] == handle.object_id and item["before_seal"] == handle.seal,
                        "CONFIGURATION_ROOT_WAL")
                expected = digest([self.new.mode,self.new.root_id,self.new.spec.domain_id,
                                   item["id"],handle.tab_id])
            else:
                _,index,kind = key.split(".")
                bound = original["records"][f"target.{index}.catalogue"]["body"]["artifacts"][kind]
                require(item["id"] == bound["id"] and item["before_seal"] == bound["seal"],
                        "CONFIGURATION_ROOT_WAL")
                expected = digest([self.new.mode,self.new.root_id,self.new.spec.domain_id,
                                   item["id"],self.new.spec.operation(key)])
                require(item["before_seal"] == digest([self.old.mode,self.old.root_id,self.old.spec.domain_id,
                    item["id"],self.old.spec.operation(key)]), "CONFIGURATION_ROOT_WAL")
            require(item["after_seal"] == expected, "CONFIGURATION_ROOT_WAL")
            refs.add(item["id"])
        pending = value["pending"]
        if pending is not None:
            require(type(pending) is dict and set(pending) in (
                        {"index","operation_id","epoch"},{"index","operation_id","epoch","dispatch"})
                    and type(pending["index"]) is int and pending["index"] == value["index"] < len(keys)
                    and type(pending["epoch"]) is int and 1 <= pending["epoch"] <= MAX_GENERATION
                    and pending["operation_id"] == self._operation(value,pending["index"])
                    and ("dispatch" not in pending or type(pending["dispatch"]) is str
                         and pending["dispatch"] in {"PREPARED","INVOKING","REVOKED"}),
                    "CONFIGURATION_ROOT_WAL")
        require(value["phase"] != "MOVED" or pending is None, "CONFIGURATION_ROOT_WAL")
        require(len(encoded(value)) <= 128 * 1024, "CONFIGURATION_ROOT_WAL_SIZE")
        return copy.deepcopy(value)

    def _operation(self, state, index):
        return digest(["reconfiguration-root",state["transition_id"],state["objects"][index]["key"]])

    def _state(self):
        current = self.context.store.read()
        return (None,0) if current is None else (self._validate(current.payload),current.revision)

    def _save(self, value, revision):
        value = self._validate(value)
        self.context.store.save(value,expected_revision=revision)
        after,n = self._state()
        require(after == value and n == revision+1, "CONFIGURATION_ROOT_UNCONFIRMED")
        return after

    def _proof(self, state, *, dispatch):
        pin = self.maintenance._proof()
        require(hashlib.sha256(pin.read(SCHEMA)).hexdigest() == SCHEMA_SHA256
                and pin_record(pin) == state["pin"], "CONFIGURATION_ROOT_INSTRUCTIONS")
        model = self._profile()
        require(self.ctx.setup.snapshot.revision == state["base_revision"]
                and sha(self.ctx.setup._payload) == state["base_sha256"]
                and model.snapshot.revision == state["candidate_revision"]
                and sha(model._payload) == state["candidate_sha256"], "CONFIGURATION_ROOT_PROFILE_CHANGED")
        sample,caps,checkpoint = self.ctx.clock(),self.ctx.capabilities(),self.ctx.checkpoint.read()
        require(type(sample) is ClockSample and sample.wall_trusted and sample.monotonic_trusted
                and type(caps) is Capabilities and caps.installation_id == self.ctx.setup.installation_id
                and caps.observe is True and checkpoint.election is None and checkpoint.mutation is None
                and type(checkpoint.grant) is Grant and checkpoint.maintenance == state["transition_id"],
                "CONFIGURATION_ROOT_NOT_AUTHORIZED")
        if dispatch:
            fresh = self.ctx.leadership.backend.read().document()
            require(OwnerGuard(checkpoint.grant.owner,checkpoint.grant.epoch).matches(fresh), "OWNER_SUPERSEDED")
            observed = self.ctx.leadership.observe(sample)
            document = observed.snapshot.document()
            owns = self.ctx.leadership._owns(observed.leader,observed.request,checkpoint.grant)
        else:
            # An old installation may not yet know the new contender's local
            # enrollment. Read-only exact-operation inspection still works;
            # an unrecognized owner never grants any write or clears UNKNOWN.
            document = self.ctx.leadership.backend.read().document()
            try:
                leader,request = self.ctx.leadership._records(document)
                owns = self.ctx.leadership._owns(leader,request,checkpoint.grant)
            except AuthorityError:
                owns = False
        require(configuration(document) == dict(schema_version=1,revision=state["configuration_revision"],
            phase="MAINTENANCE",transition_id=state["transition_id"])
            and stable_records(document) == state["records_sha256"], "CONFIGURATION_ROOT_CHANGED")
        effects = ledger(document["records"][SLOT]); pending = state["pending"]
        require(effects is not None and effects["barrier"] is not None
                and effects["barrier"]["transition_id"] == state["transition_id"]
                and effects["barrier"]["local_clear"] is True, "CONFIGURATION_ROOT_EVIDENCE")
        for action,fact in effects["entries"].items():
            if fact["outcome"] == "UNKNOWN":
                require(pending is not None and action == Action.IDENTITY.value
                    and fact["operation_id"] == pending["operation_id"]
                    and fact["owner"] == state["installation_id"] and fact["epoch"] == pending["epoch"],
                    "CONFIGURATION_ROOT_UNKNOWN")
        if dispatch:
            require(caps.coordinate is True and type(caps.actions) is frozenset
                    and all(type(a) is Action for a in caps.actions) and Action.IDENTITY in caps.actions,
                    "CONFIGURATION_ROOT_NOT_AUTHORIZED")
            require(owns, "OWNER_SUPERSEDED")
        return checkpoint, owns

    def begin(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        require(self._state()[0] is None, "CONFIGURATION_ROOT_INSPECT_REQUIRED")
        qualified = self.context.candidate.require_validated(self.context.checker)
        self.old.check_root(); self.new.check_root()
        snapshot,_ = self.maintenance._current(); document = snapshot.document()
        _,handle = storage_spec(self.ctx.setup.private_choices()["storage"])
        objects = []
        for key in self.old.spec.artifact_keys + ("authority",):
            if key == "authority":
                ref,seal = handle.object_id,handle.seal
                size = None
                require(self.old.inspect_authority(self.old.spec,handle) == handle, "CONFIGURATION_ROOT_BINDING")
                after_seal = digest([self.new.mode,self.new.root_id,self.new.spec.domain_id,ref,handle.tab_id])
            else:
                _,index,kind = key.split(".")
                bound = document["records"][f"target.{index}.catalogue"]["body"]["artifacts"][kind]
                ref,seal = bound["id"],bound["seal"]
                allocated = Allocation(ref,self.old.spec.operation(key),seal=seal)
                require(self.old.inspect(key,allocated) == allocated, "CONFIGURATION_ROOT_BINDING")
                size = int(self.old._metadata(ref)["size"])
                after_seal = digest([self.new.mode,self.new.root_id,self.new.spec.domain_id,ref,self.new.spec.operation(key)])
            objects.append(dict(key=key,id=ref,size=size,before_seal=seal,after_seal=after_seal))
        state = dict(schema_version=1,kind="RECONFIGURATION_DOCS_ROOT_MOVES",
            installation_id=self.ctx.setup.installation_id,transition_id=qualified.decision.transition_id,
            configuration_revision=qualified.decision.revision,base_revision=self.ctx.setup.snapshot.revision,
            base_sha256=sha(self.ctx.setup._payload),candidate_revision=qualified.revision,
            candidate_sha256=qualified.setup_sha256,authority=asdict(snapshot.binding),target_root=self.new.root_id,
            records_sha256=stable_records(document),objects=objects,index=0,pending=None,phase="MOVING",
            pin=pin_record(self.maintenance._proof()),binding=self._binding())
        self._proof(state,dispatch=True)
        self._save(state,0)
        return "MOVING"

    def _inspect_object(self, item):
        value = self.old._metadata(item["id"],missing_ok=True)
        if value is None:
            return "CONFLICT"
        for port,label in ((self.new,"AFTER"),(self.old,"BEFORE")):
            try:
                port._verify(value,item["key"],item["id"])
                if item["size"] is not None:
                    require(int(value["size"]) == item["size"], "CONFIGURATION_ROOT_CONTENT_CHANGED")
                return label
            except Exception:
                pass
        return "CONFLICT"

    def advance(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        state,revision = self._state()
        require(state is not None, "CONFIGURATION_ROOT_NOT_STARTED")
        if state["pending"] is not None:
            return self.inspect()  # A resumed call is never a new SDK send.
        checkpoint,_ = self._proof(state,dispatch=True)
        if state["phase"] == "MOVED":
            return "MOVED"
        self.old.check_root(); self.new.check_root()
        item = state["objects"][state["index"]]
        require(self._inspect_object(item) == "BEFORE", "CONFIGURATION_ROOT_INSPECT_REQUIRED")
        pending = dict(index=state["index"],operation_id=self._operation(state,state["index"]),
                       epoch=checkpoint.grant.epoch,dispatch="PREPARED")
        state = self._save({**state,"pending":pending},revision)
        result = self.ctx.effects.start(checkpoint.grant,Action.IDENTITY,pending["operation_id"],
                                        maintenance_transition=state["transition_id"])
        if result != "CONFIRMED":
            return result
        self._proof(state,dispatch=True)
        require(self._inspect_object(item) == "BEFORE", "CONFIGURATION_ROOT_INSPECT_REQUIRED")
        invoking = self._validate({**state,"pending":{**pending,"dispatch":"INVOKING"}})
        # Keep this local operation exclusive across the final read and send.
        # A second local reader/recovery cannot settle/reuse its native intent
        # while this live invocation may still reach the provider.
        with self.context.store.native.locked() as port:
            raw = port.read("settings.json")
            saved = self.context.store._decode(raw,port.binding)
            require(port.read("settings.pending") is None and saved.revision == revision+1
                    and saved.payload == state and sha(port.binding) == state["binding"],
                    "CONFIGURATION_ROOT_CHANGED")
            self._proof(state,dispatch=True)
            fact = self.ctx.effects.receipt(Action.IDENTITY)
            require(fact is not None and fact["operation_id"] == pending["operation_id"]
                    and fact["outcome"] == "UNKNOWN" and fact["owner"] == checkpoint.grant.owner
                    and fact["epoch"] == checkpoint.grant.epoch, "CONFIGURATION_ROOT_EVIDENCE")
            armed = self.context.store._save_locked(port,invoking,expected_revision=revision+1)
            require(armed.payload == invoking and armed.revision == revision+2,
                    "CONFIGURATION_ROOT_UNCONFIRMED")
            # Persist the possible-send boundary before invoking the SDK, while
            # retaining the same actual lock through the final owner proof/call.
            self._proof(invoking,dispatch=True)
            try:
                # Exactly metadata/parents; no upload, content/create/copy/delete.
                self.old._execute(self.old.drive.files().update(fileId=item["id"],
                    body=dict(properties=self.new._props(item["key"],self.new.spec.operation(item["key"]))),
                    addParents=self.new.root_id,removeParents=self.old.root_id,fields=FIELDS,supportsAllDrives=True))
            except Exception:
                return "UNKNOWN"  # A failed response never proves non-application.
        return self.inspect()

    def inspect(self):
        state,revision = self._state()
        require(state is not None, "CONFIGURATION_ROOT_NOT_STARTED")
        checkpoint,owns = self._proof(state,dispatch=False)
        if state["pending"] is None:
            return state["phase"]
        pending = state["pending"]
        result = self._inspect_object(state["objects"][pending["index"]])
        if result == "AFTER" and pending.get("dispatch") in {"PREPARED","REVOKED"}:
            return "CONFLICT"  # Contradictory evidence never clears UNKNOWN.
        if result != "AFTER":
            return "UNKNOWN" if result == "BEFORE" else "CONFLICT"
        if not owns or checkpoint.grant.epoch != pending["epoch"]:
            return "APPLIED_OWNER_SUPERSEDED"  # Role available; routing/evidence remains held.
        self._proof(state,dispatch=True)
        if self.ctx.effects.inspect() not in {"NO_PENDING","CONFIRMED"}:
            return "UNKNOWN"
        fact = self.ctx.effects.receipt(Action.IDENTITY)
        require(fact is not None and fact["operation_id"] == pending["operation_id"], "CONFIGURATION_ROOT_EVIDENCE")
        if fact["outcome"] != "COMPLETE":
            if self.ctx.effects.finish(checkpoint.grant,Action.IDENTITY,pending["operation_id"],"COMPLETE") != "CONFIRMED":
                return "UNKNOWN"
        index = state["index"]+1
        self._save({**state,"index":index,"pending":None,
                    "phase":"MOVED" if index == len(state["objects"]) else "MOVING"},revision)
        return "MOVED" if index == len(state["objects"]) else "CONFIRMED"

    def revoke_prepared(self, *, owner_authorized=False):
        """Fence a never-armed local invocation; do not clear shared UNKNOWN."""
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        state,revision = self._state()
        require(state is not None and state["pending"] is not None
                and state["pending"].get("dispatch") in {"PREPARED","REVOKED"},
                "CONFIGURATION_ROOT_NOT_PREPARED")
        if state["pending"]["dispatch"] == "REVOKED":
            return self.revocation()
        checkpoint,_ = self._proof(state,dispatch=True)
        require(checkpoint.grant.epoch == state["pending"]["epoch"], "OWNER_SUPERSEDED")
        require(self._inspect_object(state["objects"][state["index"]]) == "BEFORE",
                "CONFIGURATION_ROOT_INSPECT_REQUIRED")
        revoked = self._validate({**state,"pending":{**state["pending"],"dispatch":"REVOKED"}})
        with self.context.store.native.locked() as port:
            require(port.read("settings.pending") is None, "CONFIGURATION_ROOT_INSPECT_REQUIRED")
            current = self.context.store._decode(port.read("settings.json"),port.binding)
            require(current.revision == revision and current.payload == state
                    and sha(port.binding) == state["binding"], "CONFIGURATION_ROOT_CHANGED")
            self._proof(state,dispatch=True)
            after = self.context.store._save_locked(port,revoked,expected_revision=revision)
            require(after.payload == revoked and after.revision == revision+1,
                    "CONFIGURATION_ROOT_UNCONFIRMED")
        return self.revocation()

    def revocation(self):
        """Fresh actual native previous/current proof, never a saved boolean."""
        snapshot = self.context.store.read()
        require(snapshot is not None and snapshot.revision >= 3, "CONFIGURATION_ROOT_REVOCATION_REQUIRED")
        state = self._validate(snapshot.payload)
        pending = state["pending"]
        require(pending is not None and pending.get("dispatch") == "REVOKED",
                "CONFIGURATION_ROOT_REVOCATION_REQUIRED")
        before = {**state,"pending":{**pending,"dispatch":"PREPARED"}}
        require(snapshot.previous == before, "CONFIGURATION_ROOT_REVOCATION_REQUIRED")
        self._validate(before); self._proof(state,dispatch=False)
        require(self._inspect_object(state["objects"][state["index"]]) == "BEFORE",
                "CONFIGURATION_ROOT_INSPECT_REQUIRED")
        return RootRevocation(state["transition_id"],pending["operation_id"],pending["epoch"],state["index"],
            snapshot.revision,sha(state),sha(before),state["binding"],self)

    def require_revocation(self, proof):
        require(type(proof) is RootRevocation and proof._origin is self
                and proof == self.revocation(), "CONFIGURATION_ROOT_REVOCATION_REQUIRED")
        return proof

    def verify_moved(self):
        """Actual access/readback facts for later remote rebind, never activation."""
        state,_ = self._state()
        require(state is not None and state["phase"] == "MOVED" and state["pending"] is None,
                "CONFIGURATION_ROOT_INSPECT_REQUIRED")
        self._proof(state,dispatch=True); self.new.check_root()
        require(all(self._inspect_object(item) == "AFTER" for item in state["objects"]),
                "CONFIGURATION_ROOT_BINDING")
        last = state["objects"][-1]
        _,old = storage_spec(self.ctx.setup.private_choices()["storage"])
        expected = AuthorityHandle(last["id"],last["after_seal"],old.tab_id)
        require(self.new.inspect_authority(self.new.spec,expected) == expected
                and self.new.authority(expected).binding == self.ctx.leadership.backend.binding,
                "CONFIGURATION_ROOT_BINDING")
        return copy.deepcopy(state["objects"])

    def recover_local(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        store = self.context.store
        with store.native.locked() as port:
            pending,raw = port.read("settings.pending"),port.read("settings.json")
            if pending is None:
                return "NO_PENDING"
            candidate = store._decode(pending,port.binding)
            current = None if raw is None else store._decode(raw,port.binding)
            require(candidate.revision == (0 if current is None else current.revision)+1
                    and candidate.previous == (None if current is None else current.payload),
                    "CONFIGURATION_ROOT_RECOVERY_CONFLICT")
        state = self._validate(candidate.payload)
        self._proof(state,dispatch=False)
        with store.native.locked() as port:
            require(port.read("settings.pending") == pending and port.read("settings.json") == raw
                    and store._decode(pending,port.binding) == candidate, "CONFIGURATION_ROOT_RECOVERY_CONFLICT")
            port.promote()
            require(port.read("settings.json") == pending, "CONFIGURATION_ROOT_UNCONFIRMED")
        return "INSPECT_REQUIRED"  # Never resume the discarded live SDK call.
