"""Current-role continuation of the exact shared Docs plan, never activation.

The old host is not an input. An ambiguous original operation stays blocked;
only the verified AFTER prefix and newly armed BEFORE remainder are used.
"""
import base64
import copy
from dataclasses import asdict, dataclass, replace
import hashlib
import json

from .ballpark_setup import pin_record, validate_pin
from .commissioning_state import storage_spec
from .configuration_contract import ConfigurationError, configuration, require
from .drive.commissioning import RAW_LIMIT, digest, object_id
from .drive.commissioning_native import NativeCommissioning
from .exchange_layout import MAX_GENERATION, encoded
from .private_settings import PrivateSettings
from .reconfiguration_candidate import native_binding
from .reconfiguration_effects import SLOT, ledger
from .reconfiguration_evidence import EvidenceReceipt, ProtectedEvidence
from .reconfiguration_inspection import inspect
from .reconfiguration_maintenance import MaintenanceContext, hex64
from .reconfiguration_root_facts import PartialRootInspection
from .reconfiguration_root_plan import matches_plan, references, root_plan, stable_records
from .reconfiguration_root_settlement import InheritedRootSettlement
from .reconfiguration_roots import DocsRootMoves
from .watchdog.leadership_runtime import Action

SCHEMA = "protocol/reconfiguration-root-resume-v1.schema.json"
SCHEMA_SHA256 = "aede9105fbb41f1e31629068811d198910902fcb715095938479b8cfe7f8a5e5"
FIELDS_STATE = frozenset({"schema_version","kind","installation_id","transition_id",
    "configuration_revision","base_revision","base_sha256","authority","target_root",
    "records_sha256","objects","index","pending","phase","pin","binding",
    "evidence","evidence_binding","plan","adopted_index"})


@dataclass(frozen=True, repr=False)
class ResumeRootContext:
    maintenance: MaintenanceContext
    store: PrivateSettings
    evidence: ProtectedEvidence
    target_root: str


class ResumedDocsRootMoves(DocsRootMoves):
    def __init__(self, context):
        require(type(context) is ResumeRootContext and type(context.maintenance) is MaintenanceContext
                and type(context.store) is PrivateSettings and type(context.evidence) is ProtectedEvidence
                and object_id(context.target_root), "CONFIGURATION_ROOT_CONTEXT")
        self.context, self.ctx = context, context.maintenance
        self.current = InheritedRootSettlement(self.ctx)
        self.maintenance = self.current.maintenance
        self.inspector = PartialRootInspection(self.ctx)
        self.old = self.ctx.storage_port
        require(context.target_root != self.old.root_id
                and context.evidence.installation_id == self.ctx.setup.installation_id
                and context.evidence.transition_id == self.ctx.baseline.transition_id,
                "CONFIGURATION_ROOT_CONTEXT")
        self.new = NativeCommissioning(self.old.drive,self.old.docs,
            replace(self.old.spec,root_id=context.target_root),llm_authorized=True,
            root_transition=context.evidence.transition_id)
        self._binding()

    def _binding(self):
        stores = [self.context.store,self.context.evidence.store,self.ctx.setup.store,
                  self.ctx.store,self.ctx.baseline.store,self.ctx.checkpoint.store,self.ctx.effects.store]
        values = [native_binding(s) for s in stores]
        require(values[0] != values[1] and not set(values[:2]) & set(values[2:]),
                "CONFIGURATION_ROOT_STORE_ALIAS")
        return values[0]

    def _evidence(self, receipt=None):
        evidence = self.context.evidence
        current = evidence.store.read()
        require(current is not None and current.revision == 1 and current.previous is None,
                "CONFIGURATION_ROOT_EVIDENCE")
        actual = evidence._receipt(current.payload)
        require(receipt is None or actual == receipt, "CONFIGURATION_ROOT_EVIDENCE")
        payload = evidence.read(actual)
        return actual,payload,json.loads(base64.b64decode(payload["image"],validate=True))

    def _original_document(self):
        return self._evidence()[2]

    def _validate(self, value):
        try:
            require(type(value) is dict and set(value) == FIELDS_STATE
                    and type(value["schema_version"]) is int and value["schema_version"] == 1
                    and value["kind"] == "RECONFIGURATION_DOCS_ROOT_RESUME"
                    and value["installation_id"] == self.ctx.setup.installation_id
                    and value["transition_id"] == self.context.evidence.transition_id
                    and value["target_root"] == self.context.target_root and value["binding"] == self._binding()
                    and value["evidence_binding"] == native_binding(self.context.evidence.store),
                    "CONFIGURATION_ROOT_WAL")
            require(all(type(value[k]) is int and 1 <= value[k] <= MAX_GENERATION
                        for k in ("configuration_revision","base_revision"))
                    and all(hex64(value[k]) for k in ("base_sha256","records_sha256")),
                    "CONFIGURATION_ROOT_WAL")
            require(value["authority"] == asdict(self.ctx.leadership.backend.binding)
                    and type(value["phase"]) is str and value["phase"] in {"MOVING","MOVED"},
                    "CONFIGURATION_ROOT_WAL")
            validate_pin(value["pin"])
            receipt = EvidenceReceipt(**value["evidence"])
            require(asdict(receipt) == value["evidence"], "CONFIGURATION_ROOT_EVIDENCE")
            _,facts,original = self._evidence(receipt)
            plan = root_plan(value["plan"])
            require(plan["transition_id"] == value["transition_id"]
                    and plan["target_root"] == value["target_root"]
                    and matches_plan(original,self.ctx.leadership.backend.binding,plan)
                    and plan["source_root"] == self.old.root_id
                    and plan["blueprint_sha256"] == self.old.spec.fingerprint
                    and value["records_sha256"] == stable_records(original)
                    and facts["inspection"]["setup_sha256"] == value["base_sha256"]
                    and not facts["inspection"]["blockers"], "CONFIGURATION_ROOT_EVIDENCE")
            spec,refs = references(original,self.ctx.leadership.backend.binding)
            require(spec == self.old.spec, "CONFIGURATION_ROOT_WAL")
            objects = value["objects"]; keys = spec.artifact_keys + ("authority",)
            require(type(objects) is list and len(objects) == len(keys) <= 129
                    and type(value["index"]) is int and type(value["adopted_index"]) is int
                    and 0 <= value["adopted_index"] <= value["index"] <= len(keys)
                    and (value["phase"] == "MOVED") == (value["index"] == len(keys)),
                    "CONFIGURATION_ROOT_WAL")
            _,handle = storage_spec(self.ctx.setup.private_choices()["storage"])
            for key,item,ref in zip(keys,objects,refs):
                require(type(item) is dict and set(item) == {"key","id","size","before_seal","after_seal"}
                        and item["key"] == key and item["id"] == ref["id"]
                        and item["before_seal"] == ref["seal"], "CONFIGURATION_ROOT_WAL")
                require(item["size"] is None if key == "authority" else
                        type(item["size"]) is int and 0 <= item["size"] <= RAW_LIMIT,
                        "CONFIGURATION_ROOT_WAL")
                after = digest([self.new.mode,self.new.root_id,spec.domain_id,item["id"],
                                handle.tab_id if key == "authority" else self.new.spec.operation(key)])
                require(item["after_seal"] == after, "CONFIGURATION_ROOT_WAL")
            pending = value["pending"]
            if pending is not None:
                require(type(pending) is dict and set(pending) == {"index","operation_id","epoch","dispatch"}
                        and type(pending["index"]) is int and pending["index"] == value["index"] < len(keys)
                        and type(pending["epoch"]) is int and 1 <= pending["epoch"] <= MAX_GENERATION
                        and pending["operation_id"] == self._operation(value,pending["index"])
                        and type(pending["dispatch"]) is str
                        and pending["dispatch"] in {"PREPARED","INVOKING","REVOKED"},
                        "CONFIGURATION_ROOT_WAL")
            require(value["phase"] != "MOVED" or pending is None, "CONFIGURATION_ROOT_WAL")
            require(len(encoded(value)) <= 128*1024, "CONFIGURATION_ROOT_WAL_SIZE")
            return copy.deepcopy(value)
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("CONFIGURATION_ROOT_WAL") from None

    def _proof(self, state, *, dispatch, root_plan_required=True):
        # This is called inside the inherited actual native send lock. Never
        # read/reacquire this controller's WAL from here.
        pin = self.maintenance._proof(state)
        require(hashlib.sha256(pin.read(SCHEMA)).hexdigest() == SCHEMA_SHA256
                and pin_record(pin) == state["pin"], "CONFIGURATION_ROOT_INSTRUCTIONS")
        self.ctx.setup._fresh()
        require(self.ctx.setup.snapshot.revision == state["base_revision"]
                and digest(self.ctx.setup._payload) == state["base_sha256"],
                "CONFIGURATION_ROOT_PROFILE_CHANGED")
        require(native_binding(self.context.evidence.store) == state["evidence_binding"],
                "CONFIGURATION_ROOT_EVIDENCE")
        self._evidence(EvidenceReceipt(**state["evidence"]))
        snapshot,checkpoint,config,_,owns = self.current._role(reserved=True,require_owner=dispatch)
        document = snapshot.document()
        require(config == dict(schema_version=1,revision=state["configuration_revision"],
            phase="MAINTENANCE",transition_id=state["transition_id"])
            and stable_records(document) == state["records_sha256"], "CONFIGURATION_ROOT_CHANGED")
        value = ledger(document["records"][SLOT])
        require(value.get("root_plan") == state["plan"]
                and matches_plan(document,snapshot.binding,state["plan"]), "CONFIGURATION_ROOT_PLAN_CHANGED")
        pending = state["pending"]
        if dispatch and pending is None:
            current = self.inspector.inspect()
            rows = json.loads(current.objects)
            require([row["state"] for row in rows] == ["AFTER"]*state["index"]
                    + ["BEFORE"]*(len(rows)-state["index"])
                    and [{k:v for k,v in row.items() if k != "state"} for row in rows] == state["objects"],
                    "CONFIGURATION_ROOT_ORDER")
        for action,fact in value["entries"].items():
            if fact["outcome"] == "UNKNOWN":
                require(pending is not None and action == Action.IDENTITY.value
                        and fact["operation_id"] == pending["operation_id"]
                        and fact["owner"] == state["installation_id"] and fact["epoch"] == pending["epoch"],
                        "CONFIGURATION_ROOT_UNKNOWN")
        facts = inspect(snapshot,setup_payload=self.ctx.setup._payload,checkpoint=checkpoint)
        # The summary retention mirrors the strictly checked UNKNOWN entry.
        # Any other unresolved action or blocker still forbids this send.
        require(all(pending is not None and (
                    row.kind == "SHARED_EFFECT_UNKNOWN" and row.identity == pending["operation_id"]
                    or row.kind == "SHARED_UNKNOWN" and row.identity == SLOT) for row in facts.blockers),
                "CONFIGURATION_ROOT_EVIDENCE")
        return checkpoint,owns

    def _intent(self, state):
        return copy.deepcopy(state["plan"])

    def _ensure_plan(self, state):
        self._proof(state,dispatch=True)
        if self.ctx.effects.inspect() not in {"NO_PENDING","CONFIRMED"}:
            return "UNKNOWN"
        self._proof(state,dispatch=True)
        return "CONFIRMED"  # Existing shared plan only; never create/replace it.

    def begin(self, proof, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        require(self._state()[0] is None, "CONFIGURATION_ROOT_INSPECT_REQUIRED")
        fresh = self.inspector.require_fresh(proof)
        require(fresh.target_root == self.context.target_root and not fresh.inspection.blockers,
                "CONFIGURATION_ROOT_EVIDENCE")
        plan = json.loads(fresh.plan); rows = json.loads(fresh.objects)
        states = [row["state"] for row in rows]
        index = sum(state == "AFTER" for state in states)
        require(states == ["AFTER"]*index + ["BEFORE"]*(len(rows)-index),
                "CONFIGURATION_ROOT_ORDER")
        document = fresh.snapshot.document()
        value = ledger(document["records"][SLOT]); fact = value["entries"].get(Action.IDENTITY.value)
        operations = [digest(["reconfiguration-root",fresh.transition_id,row["key"]]) for row in rows]
        if index:
            require(fact is not None and (fact["outcome"] == "COMPLETE"
                    and fact["operation_id"] == operations[index-1]
                    or index < len(rows) and fact["outcome"] == "NOT_DISPATCHED"
                    and fact["operation_id"] == operations[index]), "CONFIGURATION_ROOT_EVIDENCE")
        else:
            require(fact is None or fact["operation_id"] not in operations
                    or fact["outcome"] == "NOT_DISPATCHED" and fact["operation_id"] == operations[0],
                    "CONFIGURATION_ROOT_EVIDENCE")
        self.ctx.checkpoint.reserve(fresh.transition_id,owner_authorized=True)
        fresh = self.inspector.require_fresh(proof)
        if self.context.evidence.store.read() is None:
            receipt = self.context.evidence.preserve(fresh.snapshot,fresh.inspection,owner_authorized=True)
        else:
            receipt,preserved,original = self._evidence()
            require(not preserved["inspection"]["blockers"]
                    and preserved["inspection"]["setup_sha256"] == fresh.inspection.setup_sha256
                    and stable_records(original) == stable_records(fresh.snapshot.document())
                    and ledger(original["records"][SLOT]).get("root_plan") == plan,
                    "CONFIGURATION_ROOT_EVIDENCE")
        _,_,config,_,_ = self.current._role(reserved=True)
        state = dict(schema_version=1,kind="RECONFIGURATION_DOCS_ROOT_RESUME",
            installation_id=self.ctx.setup.installation_id,transition_id=fresh.transition_id,
            configuration_revision=config["revision"],base_revision=self.ctx.setup.snapshot.revision,
            base_sha256=digest(self.ctx.setup._payload),authority=asdict(fresh.snapshot.binding),
            target_root=fresh.target_root,records_sha256=stable_records(fresh.snapshot.document()),
            objects=[{k:v for k,v in row.items() if k != "state"} for row in rows],
            index=index,pending=None,phase="MOVED" if index == len(rows) else "MOVING",
            pin=pin_record(self.maintenance._proof()),binding=self._binding(),
            evidence=asdict(receipt),evidence_binding=native_binding(self.context.evidence.store),
            plan=plan,adopted_index=index)
        self._proof(state,dispatch=True)
        self._save(state,0)
        return state["phase"]

    def recover_evidence(self, *, owner_authorized=False):
        """Promote only an exact first evidence frame; never send or adopt."""
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        store = self.context.evidence.store
        with store.native.locked() as port:
            pending,raw = port.read("settings.pending"),port.read("settings.json")
            if pending is None:
                return "NO_PENDING"
            candidate = store._decode(pending,port.binding)
            require(raw is None and candidate.revision == 1 and candidate.previous is None,
                    "CONFIGURATION_ROOT_RECOVERY_CONFLICT")
        self.context.evidence._validate(candidate.payload)
        fresh = self.inspector.inspect()
        original = json.loads(base64.b64decode(candidate.payload["image"],validate=True))
        require(not fresh.inspection.blockers and not candidate.payload["inspection"]["blockers"]
                and candidate.payload["inspection"]["setup_sha256"] == fresh.inspection.setup_sha256
                and stable_records(original) == stable_records(fresh.snapshot.document())
                and ledger(original["records"][SLOT]).get("root_plan") == json.loads(fresh.plan),
                "CONFIGURATION_ROOT_RECOVERY_CONFLICT")
        with store.native.locked() as port:
            require(port.read("settings.pending") == pending and port.read("settings.json") is None,
                    "CONFIGURATION_ROOT_RECOVERY_CONFLICT")
            port.promote()
            require(port.read("settings.json") == pending, "CONFIGURATION_ROOT_UNCONFIRMED")
        return "INSPECT_REQUIRED"
