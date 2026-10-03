"""Current-role exact cloud root evidence; no old host or SDK mutation.

This only resolves the receipt of an actually applied inherited operation.
Partial-root first-run/routing admission and final promotion remain separate.
"""
from dataclasses import dataclass, replace
import copy
import hashlib

from .commissioning_state import storage_spec
from .configuration_contract import configuration, require
from .drive.authority_transaction import OwnerGuard
from .drive.commissioning import digest, object_id
from .drive.commissioning_bootstrap import AuthorityHandle
from .drive.commissioning_native import NativeCommissioning
from .drive.leadership import ClockSample, Grant
from .exchange_layout import encoded
from .reconfiguration_effects import Effects, EffectMutation, SLOT, changed_row, ledger
from .reconfiguration_maintenance import Maintenance, MaintenanceContext
from .reconfiguration_roots import SCHEMA, SCHEMA_SHA256
from .reconfiguration_root_plan import matches_plan
from .watchdog.checkpoint_store import NativeCheckpoint
from .watchdog.leadership_runtime import Action, Capabilities


@dataclass(frozen=True, repr=False)
class AppliedRootEvidence:
    transition_id: str
    operation_id: str
    key: str
    object_id: str
    parent: str
    entry: bytes
    protected: bytes
    _origin: object


class InheritedRootSettlement:
    def __init__(self, context):
        require(type(context) is MaintenanceContext and type(context.storage_port) is NativeCommissioning
                and type(context.effects) is Effects and type(context.checkpoint) is NativeCheckpoint
                and context.effects.checkpoint is context.checkpoint
                and context.effects.leadership is context.leadership, "CONFIGURATION_ROOT_SETTLEMENT_CONTEXT")
        self.context = context
        self.maintenance = Maintenance(context)

    def _role(self, *, reserved, require_owner=True):
        ctx = self.context
        pin = self.maintenance._proof()
        require(hashlib.sha256(pin.read(SCHEMA)).hexdigest() == SCHEMA_SHA256,
                "CONFIGURATION_ROOT_INSTRUCTIONS")
        ctx.setup._fresh()
        choices = ctx.setup.private_choices()
        spec,handle = storage_spec(choices["storage"])
        require(choices["role"] == "watchdog" and ctx.setup._payload["state"] != "CANCELLED"
                and spec == ctx.storage_port.spec and spec.mode == "NATIVE_DOCS"
                and ctx.storage_port.root_transition == choices["storage"].get("root_transition")
                and handle.seal == digest([spec.mode,spec.root_id,spec.domain_id,handle.object_id,handle.tab_id])
                and ctx.storage_port.authority(handle).binding == ctx.leadership.backend.binding,
                "CONFIGURATION_ROOT_SETTLEMENT_CONTEXT")
        caps,sample,checkpoint = ctx.capabilities(),ctx.clock(),ctx.checkpoint.read()
        require(type(caps) is Capabilities and caps.installation_id == ctx.setup.installation_id
                and caps.observe is True and caps.coordinate is True and type(caps.actions) is frozenset
                and all(type(a) is Action for a in caps.actions) and Action.IDENTITY in caps.actions,
                "CONFIGURATION_ROOT_NOT_AUTHORIZED")
        require(type(sample) is ClockSample and sample.wall_trusted and sample.monotonic_trusted,
                "CONFIGURATION_CLOCK")
        require(type(checkpoint.grant) is Grant and checkpoint.grant.owner == ctx.setup.installation_id
                and checkpoint.election is None and checkpoint.mutation is None,
                "CONFIGURATION_LEADERSHIP_UNKNOWN")
        if require_owner:
            observed = ctx.leadership.observe(sample)
            owns = ctx.leadership._owns(observed.leader,observed.request,checkpoint.grant)
            require(owns, "OWNER_SUPERSEDED")
            snapshot = observed.snapshot
        else:
            snapshot = ctx.leadership.backend.read()
            owns = OwnerGuard(checkpoint.grant.owner,checkpoint.grant.epoch).matches(snapshot.document())
        document = snapshot.document(); config = configuration(document)
        require(config is not None and config["phase"] == "MAINTENANCE"
                and checkpoint.maintenance in {None,config["transition_id"]}
                and (not reserved or checkpoint.maintenance == config["transition_id"]),
                "CONFIGURATION_ROOT_NOT_AUTHORIZED")
        commissioning = document["records"]["global.commissioning"]
        require(commissioning["body"] == spec.marker("STORAGE_READY")
                and commissioning["generation"] == 0 and commissioning["operation_id"] == spec.setup_id
                and commissioning["retention"] == "RETAINED", "CONFIGURATION_ROOT_BLUEPRINT")
        value = ledger(document["records"][SLOT])
        require(value is not None and value["barrier"] is not None
                and value["barrier"]["local_clear"] is True
                and value["barrier"]["transition_id"] == config["transition_id"],
                "CONFIGURATION_ROOT_EVIDENCE")
        return snapshot,checkpoint,config,handle,owns

    def _current(self, *, reserved, inherited=True, outcomes=("UNKNOWN","COMPLETE")):
        snapshot,checkpoint,config,handle,_ = self._role(reserved=reserved)
        value = ledger(snapshot.document()["records"][SLOT])
        entry = value["entries"].get(Action.IDENTITY.value)
        require(entry is not None and entry["outcome"] in outcomes
                and (entry["epoch"] < checkpoint.grant.epoch if inherited else
                     entry["epoch"] <= checkpoint.grant.epoch and
                     (entry["epoch"] != checkpoint.grant.epoch or entry["owner"] == checkpoint.grant.owner)),
                "CONFIGURATION_ROOT_NOT_INHERITED")
        keys = [key for key in self.context.storage_port.spec.artifact_keys + ("authority",)
                if digest(["reconfiguration-root",config["transition_id"],key]) == entry["operation_id"]]
        require(len(keys) == 1, "CONFIGURATION_ROOT_OPERATION")
        return snapshot,checkpoint,config,copy.deepcopy(entry),keys[0],handle

    def inspect(self):
        snapshot,checkpoint,config,entry,key,handle = self._current(reserved=False)
        ctx = self.context; spec = ctx.storage_port.spec; doc = snapshot.document()
        plan = ledger(doc["records"][SLOT]).get("root_plan")
        require(plan is not None and plan["transition_id"] == config["transition_id"]
                and matches_plan(doc,snapshot.binding,plan), "CONFIGURATION_ROOT_PLAN_CHANGED")
        protected = {k:doc["records"][k] for k in ("global.settings","global.commissioning")}
        if key == "authority":
            ref = handle.object_id
        else:
            _,index,kind = key.split("."); slot = "target."+index+".catalogue"
            protected[slot] = doc["records"][slot]
            item = protected[slot]["body"]["artifacts"][kind]; ref = item["id"]
            require(object_id(ref) and item["seal"] == digest([
                spec.mode,spec.root_id,spec.domain_id,ref,spec.operation(key)]), "CONFIGURATION_ROOT_BINDING")
        metadata = ctx.storage_port._metadata(ref,missing_ok=True)
        require(type(metadata) is dict and metadata.get("parents") == [plan["target_root"]],
                "CONFIGURATION_ROOT_AFTER_REQUIRED")
        parent = metadata["parents"][0]
        after = NativeCommissioning(ctx.storage_port.drive,ctx.storage_port.docs,
            replace(spec,root_id=parent),llm_authorized=True,root_transition=config["transition_id"])
        after.check_root(); after._verify(metadata,key,ref)
        if key == "authority":
            expected = AuthorityHandle(ref,digest([after.mode,parent,spec.domain_id,ref,handle.tab_id]),handle.tab_id)
            require(after.inspect_authority(after.spec,expected) == expected
                    and after.authority(expected).binding == ctx.leadership.backend.binding,
                    "CONFIGURATION_ROOT_BINDING")
        # Current role/source/reservation/spec/entry may have changed during I/O.
        fresh,_,fresh_config,fresh_entry,fresh_key,_ = self._current(reserved=False)
        require(fresh_config == config and fresh_entry == entry and fresh_key == key
                and all(fresh.document()["records"][k] == v for k,v in protected.items()),
                "CONFIGURATION_ROOT_CHANGED")
        return AppliedRootEvidence(config["transition_id"],entry["operation_id"],key,ref,parent,
                                   encoded(entry),encoded(protected),self)

    def settle(self, proof, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        require(type(proof) is AppliedRootEvidence and proof._origin is self,
                "CONFIGURATION_ROOT_EVIDENCE")
        fresh = self.inspect()
        require((fresh.transition_id,fresh.operation_id,fresh.key,fresh.object_id,fresh.parent,fresh.protected)
                == (proof.transition_id,proof.operation_id,proof.key,proof.object_id,proof.parent,proof.protected),
                "CONFIGURATION_ROOT_CHANGED")
        ctx = self.context
        snapshot,checkpoint,config,entry,key,_ = self._current(reserved=False)
        ctx.checkpoint.reserve(config["transition_id"],owner_authorized=True)
        snapshot,checkpoint,config,entry,key,_ = self._current(reserved=True)
        if entry["outcome"] == "COMPLETE":
            return "CONFIRMED"
        require(encoded(entry) == proof.entry, "CONFIGURATION_ROOT_CHANGED")
        require(ctx.effects.inspect() in {"NO_PENDING","CONFIRMED"}, "CONFIGURATION_EFFECT_INSPECT_REQUIRED")
        # Re-read after any exact pending inspection; no SDK mutation is involved.
        current = self.inspect()
        require(current == fresh, "CONFIGURATION_ROOT_CHANGED")
        snapshot,checkpoint,_,entry,_,_ = self._current(reserved=True)
        document = snapshot.document(); value = ledger(document["records"][SLOT])
        value["entries"][Action.IDENTITY.value] = {**entry,"outcome":"COMPLETE"}
        plan = EffectMutation.prepare(snapshot,OwnerGuard(checkpoint.grant.owner,checkpoint.grant.epoch),
            changed_row(document["records"][SLOT],value),purpose="ROOT_SETTLE",root_key=key)
        return ctx.effects._commit(plan)


class ProvenNoDispatchSettlement:
    """Actual native revocation can record non-dispatch; BEFORE alone cannot."""
    def __init__(self, context):
        self.current = InheritedRootSettlement(context)
        self.context = context

    def _proof(self, proof, *, reserved):
        from .reconfiguration_roots import DocsRootMoves, RootRevocation
        from .reconfiguration_root_resume import ResumedDocsRootMoves
        require(type(proof) is RootRevocation and type(proof._origin) in (DocsRootMoves,ResumedDocsRootMoves),
                "CONFIGURATION_ROOT_REVOCATION_REQUIRED")
        roots = proof._origin
        roots.require_revocation(proof)
        ctx = self.context
        require(roots.old.spec == ctx.storage_port.spec and roots.old.drive is ctx.storage_port.drive
                and roots.old.docs is ctx.storage_port.docs
                and roots.ctx.leadership.backend.binding == ctx.leadership.backend.binding,
                "CONFIGURATION_ROOT_BINDING")
        snapshot,checkpoint,config,entry,key,_ = self.current._current(reserved=reserved,inherited=False,
            outcomes=("UNKNOWN","NOT_DISPATCHED"))
        keys = roots.old.spec.artifact_keys + ("authority",)
        require(proof.transition_id == config["transition_id"] and proof.operation_id == entry["operation_id"]
                and proof.epoch == entry["epoch"] and entry["owner"] == roots.ctx.setup.installation_id
                and key == keys[proof.index], "CONFIGURATION_ROOT_EVIDENCE")
        return snapshot,checkpoint,config,entry,key

    def settle(self, proof, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        _,_,config,_,_ = self._proof(proof,reserved=False)
        ctx = self.context
        ctx.checkpoint.reserve(config["transition_id"],owner_authorized=True)
        snapshot,checkpoint,_,entry,key = self._proof(proof,reserved=True)
        if entry["outcome"] == "NOT_DISPATCHED":
            return "CONFIRMED"
        require(ctx.effects.inspect() in {"NO_PENDING","CONFIRMED"}, "CONFIGURATION_EFFECT_INSPECT_REQUIRED")
        snapshot,checkpoint,_,entry,key = self._proof(proof,reserved=True)
        document = snapshot.document(); value = ledger(document["records"][SLOT])
        value["entries"][Action.IDENTITY.value] = {**entry,"outcome":"NOT_DISPATCHED"}
        plan = EffectMutation.prepare(snapshot,OwnerGuard(checkpoint.grant.owner,checkpoint.grant.epoch),
            changed_row(document["records"][SLOT],value),purpose="ROOT_CANCEL",root_key=key)
        return ctx.effects._commit(plan)
