"""Bounded shared effect evidence in the existing authority, never a grant.

UNKNOWN is durable before invocation. New role owners inherit that evidence.
No election calls this helper or waits for any machine acknowledgement.
"""
from dataclasses import asdict, dataclass
import copy
import hashlib
import json

from .configuration_contract import ConfigurationError, configuration, require
from .drive.authority_transaction import OwnerGuard, RecordMutation, reconcile
from .drive.commissioning import SetupSpec, digest, frozen_plan, object_id, restored_plan
from .drive.leadership import Grant, Leadership, identity, transition_id
from .exchange_layout import MAX_GENERATION, Capacity, empty_document, encoded, validate_document
from .private_settings import PrivateSettings

SLOT = "global.summary"
KEY = "tb4_effects_v1"
SCHEMA = "protocol/reconfiguration-effects-v1.schema.json"
SCHEMA_SHA256 = "bddcddeabfa7d79cf96ad89e748a62cc34136bea2c332e01989f4ddceb2ffbf9"
OUTCOMES = frozenset({"UNKNOWN", "COMPLETE", "NO_WORK", "SUPERSEDED", "NOT_DISPATCHED"})


def ledger(row):
    from .watchdog.leadership_runtime import Action
    body = row["body"]
    if type(body) is not dict or KEY not in body:
        return None
    value = body[KEY]
    require(type(value) is dict and set(value) == {"schema_version", "coverage_epoch", "entries", "barrier"}
            and type(value["schema_version"]) is int and value["schema_version"] == 1
            and type(value["coverage_epoch"]) is int and value["coverage_epoch"] == 1
            and type(value["entries"]) is dict and set(value["entries"]) <= {a.value for a in Action}
            and row["retention"] != "FREE", "CONFIGURATION_EFFECT_JOURNAL")
    for entry in value["entries"].values():
        require(type(entry) is dict and set(entry) == {"owner", "epoch", "operation_id", "outcome"}
                and identity(entry["owner"]) and type(entry["epoch"]) is int
                and 1 <= entry["epoch"] <= MAX_GENERATION and transition_id(entry["operation_id"])
                and type(entry["outcome"]) is str and entry["outcome"] in OUTCOMES, "CONFIGURATION_EFFECT_JOURNAL")
    barrier = value["barrier"]
    if barrier is not None:
        require(type(barrier) is dict and set(barrier) == {
            "transition_id", "source_owner", "source_epoch", "local_clear"}
            and transition_id(barrier["transition_id"]) and identity(barrier["source_owner"])
            and type(barrier["source_epoch"]) is int and 1 <= barrier["source_epoch"] <= MAX_GENERATION
            and type(barrier["local_clear"]) is bool, "CONFIGURATION_EFFECT_JOURNAL")
    require(len(encoded(value)) <= 6144, "CONFIGURATION_EFFECT_JOURNAL_SIZE")
    require(row["retention"] == ("UNKNOWN" if any(e["outcome"] == "UNKNOWN"
            for e in value["entries"].values()) else "RETAINED"), "CONFIGURATION_EFFECT_JOURNAL")
    return copy.deepcopy(value)


def preserves_effects(before, after):
    """Normal publication cannot discard or rewrite the reserved effect evidence."""
    original = ledger(before["records"][SLOT])
    desired = ledger(after["records"][SLOT])
    return original is None and desired is None or original is not None and original == desired and (
        before["records"][SLOT] == after["records"][SLOT])


def changed_row(row, value):
    require(type(row["generation"]) is int and row["generation"] < MAX_GENERATION
            and (row["body"] is None or type(row["body"]) is dict), "CONFIGURATION_EFFECT_JOURNAL_SIZE")
    result = dict(generation=row["generation"]+1,
        operation_id=hashlib.sha256(encoded(value)).hexdigest(),
        retention="UNKNOWN" if any(x["outcome"] == "UNKNOWN" for x in value["entries"].values()) else "RETAINED",
        body={**(row["body"] or {}), KEY:copy.deepcopy(value)})
    ledger(result)
    return result


def barrier_row(row, *, owner, transition, local_clear):
    value = ledger(row)
    require(value is not None and type(owner) is OwnerGuard and transition_id(transition)
            and type(local_clear) is bool, "CONFIGURATION_EFFECT_EVIDENCE_REQUIRED")
    value["barrier"] = dict(transition_id=transition, source_owner=owner.owner,
                            source_epoch=owner.epoch, local_clear=local_clear)
    return changed_row(row, value)


def covered(document, transition):
    value = ledger(document["records"][SLOT])
    return value is not None and value["barrier"] is not None and (
        value["barrier"]["transition_id"] == transition and value["barrier"]["local_clear"] is True)


@dataclass(frozen=True, repr=False)
class EffectMutation(RecordMutation):
    purpose: str

    @classmethod
    def prepare(cls, snapshot, owner, row, *, purpose, root_key=None):
        doc = snapshot.document()
        require(type(owner) is OwnerGuard and owner.matches(doc), "OWNER_SUPERSEDED")
        protected = {"global.settings"}
        if purpose in {"ROOT_SETTLE","ROOT_CANCEL","ROOT_RETRY"}:
            require(type(root_key) is str and root_key in (
                tuple(f"artifact.{i:03d}.{kind}" for i in range(Capacity.parse(doc["capacity"]).devices)
                      for kind in ("input","output")) + ("authority",)), "CONFIGURATION_EFFECT_WAL")
            protected.add("global.commissioning")
            if root_key != "authority":
                protected.add("target."+root_key.split(".")[1]+".catalogue")
        else:
            require(root_key is None, "CONFIGURATION_EFFECT_WAL")
        result = cls(snapshot.binding, owner, encoded({k:v for k,v in doc.items() if k != "records"}),
            encoded({k:doc["records"][k] for k in protected}),
            encoded({SLOT:doc["records"][SLOT]}), encoded({SLOT:row}), purpose)
        result._validate()
        return result

    def _validate(self):
        try:
            parts = {k:json.loads(getattr(self,k)) for k in ("header", "protected", "before", "after")}
            require(all(encoded(v) == getattr(self,k) for k,v in parts.items())
                    and "global.settings" in parts["protected"]
                    and set(parts["before"]) == set(parts["after"]) == {SLOT}
                    and identity(self.owner.owner) and type(self.owner.epoch) is int
                    and 1 <= self.owner.epoch <= MAX_GENERATION, "CONFIGURATION_EFFECT_WAL")
            header = parts["header"]
            require(set(header) == {"layout_version", "compatibility_status", "domain_id", "layout_revision", "capacity"}
                    and header["domain_id"] == self.binding.domain_id, "CONFIGURATION_EFFECT_WAL")
            probe = empty_document(self.binding.domain_id, Capacity.parse(header["capacity"]))
            probe.update(header); probe["records"].update(parts["protected"])
            before, after = parts["before"][SLOT], parts["after"][SLOT]
            for row in (before,after):
                probe["records"][SLOT] = row
                validate_document(probe)
            old, new = ledger(before), ledger(after)
            require(new is not None and after == changed_row(before,new), "CONFIGURATION_EFFECT_WAL")
            config = configuration(probe)
            require(self.purpose in {"INITIALIZE", "START", "ROOT_START", "ROOT_SETTLE", "ROOT_CANCEL", "ROOT_RETRY", "FINISH", "CERTIFY"}, "CONFIGURATION_EFFECT_WAL")
            if self.purpose not in {"ROOT_SETTLE","ROOT_CANCEL","ROOT_RETRY"}:
                require(set(parts["protected"]) == {"global.settings"}, "CONFIGURATION_EFFECT_WAL")
            if self.purpose in {"INITIALIZE", "START"}:
                require(config is None or config["phase"] != "MAINTENANCE", "CONFIGURATION_MAINTENANCE")
            if self.purpose == "INITIALIZE":
                require(old is None and self.owner.epoch == 1 and new["barrier"] is None
                        and before["retention"] in {"FREE", "RETAINED"}
                        and all(x["owner"] == self.owner.owner and x["epoch"] == 1
                                for x in new["entries"].values()), "CONFIGURATION_LEGACY_EVIDENCE_REQUIRED")
            else:
                require(old is not None, "CONFIGURATION_EFFECT_WAL")
                if self.purpose == "CERTIFY":
                    barrier = old["barrier"]
                    require(barrier is not None and config is not None and config["phase"] == "MAINTENANCE"
                            and barrier["transition_id"] == config["transition_id"]
                            and barrier["source_owner"] == self.owner.owner
                            and barrier["source_epoch"] == self.owner.epoch and not barrier["local_clear"]
                            and new == {**old,"barrier":{**barrier,"local_clear":True}}, "CONFIGURATION_EFFECT_WAL")
                else:
                    changed = {key for key in set(old["entries"]) | set(new["entries"])
                               if old["entries"].get(key) != new["entries"].get(key)}
                    require(len(changed) == 1 and new["barrier"] == old["barrier"], "CONFIGURATION_EFFECT_WAL")
                    action = next(iter(changed)); entry = new["entries"].get(action); prior = old["entries"].get(action)
                    require(entry is not None and (self.purpose in {"ROOT_SETTLE","ROOT_CANCEL"} or
                            entry["owner"] == self.owner.owner and entry["epoch"] == self.owner.epoch),
                            "CONFIGURATION_EFFECT_WAL")
                    if self.purpose in {"ROOT_SETTLE","ROOT_CANCEL","ROOT_RETRY"}:
                        barrier = old["barrier"]
                        require(action == "IDENTITY" and prior is not None
                                and config is not None and config["phase"] == "MAINTENANCE"
                                and barrier is not None and barrier["local_clear"] is True
                                and barrier["transition_id"] == config["transition_id"], "CONFIGURATION_EFFECT_WAL")
                        if self.purpose == "ROOT_RETRY":
                            require(prior["outcome"] == "NOT_DISPATCHED" and entry["outcome"] == "UNKNOWN"
                                    and entry["operation_id"] == prior["operation_id"]
                                    and prior["epoch"] <= self.owner.epoch
                                    and (prior["epoch"] != self.owner.epoch or prior["owner"] == self.owner.owner),
                                    "CONFIGURATION_EFFECT_WAL")
                        else:
                            require(prior["outcome"] == "UNKNOWN"
                                    and entry["outcome"] == ("COMPLETE" if self.purpose == "ROOT_SETTLE" else "NOT_DISPATCHED")
                                    and (prior["epoch"] < self.owner.epoch if self.purpose == "ROOT_SETTLE" else
                                         prior["epoch"] <= self.owner.epoch and
                                         (prior["epoch"] != self.owner.epoch or prior["owner"] == self.owner.owner))
                                    and {k:v for k,v in entry.items() if k != "outcome"}
                                    == {k:v for k,v in prior.items() if k != "outcome"}, "CONFIGURATION_EFFECT_WAL")
                        row = parts["protected"]["global.commissioning"]
                        marker = row["body"]
                        spec = SetupSpec(marker["root_id"],self.binding.domain_id,marker["setup_id"],
                                         marker["bootstrap_actor"],marker["mode"],Capacity.parse(header["capacity"]))
                        require(spec.mode == "NATIVE_DOCS" and marker == spec.marker("STORAGE_READY")
                                and row["generation"] == 0 and row["retention"] == "RETAINED"
                                and row["operation_id"] == spec.setup_id, "CONFIGURATION_EFFECT_WAL")
                        keys = [k for k in spec.artifact_keys + ("authority",)
                                if digest(["reconfiguration-root",config["transition_id"],k]) == prior["operation_id"]]
                        require(len(keys) == 1, "CONFIGURATION_EFFECT_WAL")
                        key = keys[0]; needed = {"global.settings","global.commissioning"}
                        if key != "authority":
                            _,index,kind = key.split("."); slot = "target."+index+".catalogue"
                            needed.add(slot)
                            item = parts["protected"][slot]["body"]["artifacts"][kind]
                            require(object_id(item["id"]) and item["seal"] == digest([
                                spec.mode,spec.root_id,spec.domain_id,item["id"],spec.operation(key)]),
                                "CONFIGURATION_EFFECT_WAL")
                        require(set(parts["protected"]) == needed, "CONFIGURATION_EFFECT_WAL")
                    if self.purpose == "ROOT_START":
                        barrier = old["barrier"]
                        require(action == "IDENTITY" and config is not None and config["phase"] == "MAINTENANCE"
                                and barrier is not None and barrier["local_clear"] is True
                                and barrier["transition_id"] == config["transition_id"], "CONFIGURATION_EFFECT_WAL")
                    if self.purpose == "ROOT_RETRY":
                        pass  # Exact NOT_DISPATCHED precondition validated above.
                    elif self.purpose in {"START", "ROOT_START"}:
                        require(entry["outcome"] == "UNKNOWN" and
                                (prior is None or prior["outcome"] != "UNKNOWN"
                                 and prior["operation_id"] != entry["operation_id"]), "CONFIGURATION_EFFECT_UNKNOWN")
                    else:
                        require(prior is not None and prior["outcome"] == "UNKNOWN"
                                and entry["outcome"] != "UNKNOWN"
                                and {k:v for k,v in entry.items() if k != "outcome"}
                                == {k:v for k,v in prior.items() if k != "outcome"}, "CONFIGURATION_EFFECT_WAL")
            return self
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("CONFIGURATION_EFFECT_WAL") from None

    @classmethod
    def restore(cls, value, binding):
        require(type(value) is dict and "purpose" in value, "CONFIGURATION_EFFECT_WAL")
        raw = restored_plan({k:v for k,v in value.items() if k != "purpose"}, binding)
        return cls(raw.binding,raw.owner,raw.header,raw.protected,raw.before,raw.after,value["purpose"])._validate()

    def evaluate(self, snapshot):
        self._validate()
        doc = snapshot.document()
        if snapshot.binding != self.binding or encoded({k:v for k,v in doc.items() if k != "records"}) != self.header:
            return "CONFLICT", None
        before, after = json.loads(self.before), json.loads(self.after)
        if doc["records"][SLOT] == after[SLOT]:
            return "CONFIRMED", None  # Read-only fact, also after takeover.
        if not self.owner.matches(doc):
            return "SUPERSEDED", None
        if any(doc["records"][key] != value for key,value in json.loads(self.protected).items()):
            return "CONFLICT", None
        if doc["records"][SLOT] != before[SLOT]:
            return "CONFLICT", None
        doc["records"].update(after)
        validate_document(doc)
        return "READY", doc


class Effects:
    def __init__(self, leadership, checkpoint, store):
        from .watchdog.checkpoint_store import NativeCheckpoint
        require(isinstance(leadership, Leadership) and type(checkpoint) is NativeCheckpoint
                and type(store) is PrivateSettings and checkpoint.installation_id == leadership.actor
                and checkpoint.binding == leadership.backend.binding, "CONFIGURATION_EFFECT_CONTEXT")
        self.leadership, self.checkpoint, self.store = leadership, checkpoint, store

    def _validate(self, value):
        try:
            require(type(value) is dict and set(value) == {"schema_version", "kind", "installation_id", "authority", "pending", "last"}
                    and type(value["schema_version"]) is int and value["schema_version"] == 1
                    and value["kind"] == "RECONFIGURATION_EFFECT_WAL"
                    and value["installation_id"] == self.leadership.actor
                    and value["authority"] == asdict(self.leadership.backend.binding), "CONFIGURATION_EFFECT_WAL")
            for plan in (value["pending"], value["last"]["plan"] if value["last"] is not None else None):
                if plan is not None:
                    require(EffectMutation.restore(plan,self.leadership.backend.binding).owner.owner == self.leadership.actor,
                            "CONFIGURATION_EFFECT_WAL")
            require(value["last"] is None or type(value["last"]) is dict
                    and set(value["last"]) == {"plan", "outcome"}
                    and value["last"]["outcome"] in {"CONFIRMED", "SUPERSEDED"}, "CONFIGURATION_EFFECT_WAL")
            require(len(encoded(value)) <= 64 * 1024, "CONFIGURATION_EFFECT_WAL_SIZE")
            return copy.deepcopy(value)
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("CONFIGURATION_EFFECT_INSPECT_REQUIRED") from None

    def _state(self):
        try:
            snap = self.store.read()
            return (None,0) if snap is None else (self._validate(snap.payload),snap.revision)
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("CONFIGURATION_EFFECT_INSPECT_REQUIRED") from None

    def _save(self, pending, last, revision):
        value = dict(schema_version=1,kind="RECONFIGURATION_EFFECT_WAL",installation_id=self.leadership.actor,
                     authority=asdict(self.leadership.backend.binding),pending=pending,last=last)
        self.store.save(value,expected_revision=revision)
        require(self._state() == (value,revision+1), "CONFIGURATION_EFFECT_UNCONFIRMED")

    def _commit(self, plan):
        state,revision = self._state()
        require(state is None or state["pending"] is None, "CONFIGURATION_EFFECT_INSPECT_REQUIRED")
        frozen = {**frozen_plan(plan),"purpose":plan.purpose}
        self._save(frozen,None if state is None else state["last"],revision)
        report = reconcile(self.leadership.backend,plan,mode="START",max_reads=4,max_writes=2)
        if report.outcome in {"CONFIRMED", "SUPERSEDED"}:
            self._save(None,dict(plan=frozen,outcome=report.outcome),revision+1)
        return report.outcome

    def inspect(self):
        state,revision = self._state()
        if state is None or state["pending"] is None:
            return "NO_PENDING"
        plan = EffectMutation.restore(state["pending"],self.leadership.backend.binding)
        report = reconcile(self.leadership.backend,plan,mode="INSPECT",max_reads=4,max_writes=1)
        if report.outcome in {"CONFIRMED", "SUPERSEDED"}:
            self._save(None,dict(plan=state["pending"],outcome=report.outcome),revision)
        return report.outcome

    def ensure(self, checkpoint):
        from .watchdog.leadership_runtime import Checkpoint
        require(type(checkpoint) is Checkpoint and self.checkpoint.read() == checkpoint
                and type(checkpoint.grant) is Grant and checkpoint.election is None,
                "CONFIGURATION_EFFECT_CONTEXT")
        state,_ = self._state()
        require(state is None or state["pending"] is None, "CONFIGURATION_EFFECT_INSPECT_REQUIRED")
        snap = self.leadership.backend.read(); doc = snap.document()
        owner = OwnerGuard(checkpoint.grant.owner,checkpoint.grant.epoch)
        require(owner.matches(doc), "OWNER_SUPERSEDED")
        if ledger(doc["records"][SLOT]) is not None:
            return "CONFIRMED"
        require(checkpoint.grant.epoch == 1 and checkpoint.mutation is None,
                "CONFIGURATION_LEGACY_EVIDENCE_REQUIRED")
        entries = {r.action.value:dict(owner=self.leadership.actor,epoch=r.epoch,
                   operation_id=r.operation_id,outcome=r.outcome) for r in checkpoint.receipts}
        value = dict(schema_version=1,coverage_epoch=1,entries=entries,barrier=None)
        plan = EffectMutation.prepare(snap,owner,changed_row(doc["records"][SLOT],value),purpose="INITIALIZE")
        require(self._commit(plan) == "CONFIRMED", "CONFIGURATION_EFFECT_INSPECT_REQUIRED")
        return "CONFIRMED"

    def receipt(self, action):
        from .watchdog.leadership_runtime import Action
        require(type(action) is Action, "CONFIGURATION_EFFECT_ACTION")
        value = ledger(self.leadership.backend.read().document()["records"][SLOT])
        require(value is not None, "CONFIGURATION_EFFECT_EVIDENCE_REQUIRED")
        return copy.deepcopy(value["entries"].get(action.value))

    def start(self, grant, action, operation, *, maintenance_transition=None):
        from .watchdog.leadership_runtime import Action
        require(type(grant) is Grant and grant.owner == self.leadership.actor
                and type(action) is Action and transition_id(operation), "CONFIGURATION_EFFECT_ACTION")
        snap = self.leadership.backend.read(); doc = snap.document()
        purpose = "START"
        if maintenance_transition is not None:
            checkpoint = self.checkpoint.read()
            config = configuration(doc)
            require(transition_id(maintenance_transition) and action is Action.IDENTITY
                    and checkpoint.grant == grant and checkpoint.maintenance == maintenance_transition
                    and checkpoint.election is None and checkpoint.mutation is None
                    and config is not None and config["phase"] == "MAINTENANCE"
                    and config["transition_id"] == maintenance_transition,
                    "CONFIGURATION_ROOT_NOT_AUTHORIZED")
            purpose = "ROOT_START"
        value = ledger(doc["records"][SLOT]); require(value is not None, "CONFIGURATION_EFFECT_EVIDENCE_REQUIRED")
        old = value["entries"].get(action.value)
        root_key = None
        if purpose == "ROOT_START" and old is not None and old["outcome"] == "NOT_DISPATCHED" and old["operation_id"] == operation:
            keys = tuple(f"artifact.{i:03d}.{kind}" for i in range(Capacity.parse(doc["capacity"]).devices)
                         for kind in ("input","output")) + ("authority",)
            matched = [key for key in keys if digest(["reconfiguration-root",maintenance_transition,key]) == operation]
            require(len(matched) == 1, "CONFIGURATION_EFFECT_WAL")
            purpose,root_key = "ROOT_RETRY",matched[0]
        else:
            require(old is None or old["outcome"] != "UNKNOWN" and old["operation_id"] != operation,
                    "CONFIGURATION_EFFECT_UNKNOWN")
        value["entries"][action.value] = dict(owner=grant.owner,epoch=grant.epoch,operation_id=operation,outcome="UNKNOWN")
        return self._commit(EffectMutation.prepare(snap,OwnerGuard(grant.owner,grant.epoch),
            changed_row(doc["records"][SLOT],value),purpose=purpose,root_key=root_key))

    def finish(self, grant, action, operation, outcome):
        from .watchdog.leadership_runtime import Action
        require(type(grant) is Grant and grant.owner == self.leadership.actor and type(action) is Action
                and transition_id(operation) and outcome in OUTCOMES - {"UNKNOWN"}, "CONFIGURATION_EFFECT_ACTION")
        snap = self.leadership.backend.read(); doc = snap.document()
        value = ledger(doc["records"][SLOT]); require(value is not None, "CONFIGURATION_EFFECT_EVIDENCE_REQUIRED")
        old = value["entries"].get(action.value)
        require(old is not None and old["owner"] == grant.owner and old["epoch"] == grant.epoch
                and old["operation_id"] == operation, "CONFIGURATION_EFFECT_UNKNOWN")
        if old["outcome"] == outcome:
            return "CONFIRMED"
        require(old["outcome"] == "UNKNOWN", "CONFIGURATION_EFFECT_UNKNOWN")
        value["entries"][action.value] = {**old,"outcome":outcome}
        return self._commit(EffectMutation.prepare(snap,OwnerGuard(grant.owner,grant.epoch),
            changed_row(doc["records"][SLOT],value),purpose="FINISH"))

    def certify(self, snapshot, grant, transition):
        doc = snapshot.document(); value = ledger(doc["records"][SLOT])
        require(value is not None and value["barrier"] is not None
                and value["barrier"]["transition_id"] == transition, "CONFIGURATION_EFFECT_EVIDENCE_REQUIRED")
        if value["barrier"]["local_clear"]:
            return "CONFIRMED"
        value["barrier"]["local_clear"] = True
        return self._commit(EffectMutation.prepare(snapshot,OwnerGuard(grant.owner,grant.epoch),
            changed_row(doc["records"][SLOT],value),purpose="CERTIFY"))

    def recover_local(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        try:
            with self.store.native.locked() as port:
                pending,raw = port.read("settings.pending"),port.read("settings.json")
                if pending is None:
                    return "NO_PENDING"
                candidate = self.store._decode(pending,port.binding)
                current = None if raw is None else self.store._decode(raw,port.binding)
                self._validate(candidate.payload)
                if current is not None:
                    self._validate(current.payload)
                require(candidate.revision == (0 if current is None else current.revision)+1
                        and candidate.previous == (None if current is None else current.payload),
                        "CONFIGURATION_EFFECT_RECOVERY_CONFLICT")
                port.promote()
                require(port.read("settings.json") == pending, "CONFIGURATION_EFFECT_UNCONFIRMED")
            return "INSPECT_REQUIRED"
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("CONFIGURATION_EFFECT_INSPECT_REQUIRED") from None
