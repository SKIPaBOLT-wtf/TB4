"""Actual same-Docs commissioning/catalogue rebind, never routing activation."""
from dataclasses import asdict,dataclass,replace
import copy
import hashlib
import json

from .ballpark_setup import pin_record,validate_pin
from .commissioning_checks import CommissionedStorage
from .commissioning_records import current_record,ready_record,rebound_record
from .commissioning_state import storage_spec
from .configuration_contract import configuration,marker,require
from .drive.authority_transaction import OwnerGuard,RecordMutation,reconcile
from .drive.commissioning import SetupSpec,Allocation,digest,frozen_plan,restored_plan
from .drive.commissioning_bootstrap import AuthorityHandle
from .drive.commissioning_native import NativeCommissioning
from .drive.docs_authority import AuthorityBinding,AuthorityError
from .drive.leadership import ClockSample,Grant
from .exchange_layout import Capacity,MAX_GENERATION,empty_document,encoded,validate_document
from .private_settings import PrivateSettings
from .reconfiguration_candidate import native_binding
from .reconfiguration_effects import Effects,SLOT,ledger,preserves_effects
from .reconfiguration_inspection import inspect as inspect_work
from .reconfiguration_maintenance import Maintenance,MaintenanceContext,hex64,sha
from .reconfiguration_root_plan import root_plan,references,matches_plan
from .watchdog.checkpoint_store import NativeCheckpoint
from .watchdog.leadership_runtime import Action,Capabilities

SCHEMA="protocol/reconfiguration-rebind-v1.schema.json"
SCHEMA_SHA256="012c59ef47b7a91b98985987c1682b03c65f91a2c82d2949d40784ef4e1dc9b2"
STATE_FIELDS=frozenset({"schema_version","kind","installation_id","transition_id","base_revision","base_sha256",
    "authority","pin","binding","dispatch","plan"})


def slots(spec):return tuple(f"target.{i:03d}.catalogue" for i in range(spec.capacity.devices))


def work_hash(document,spec):
    ignored=set(slots(spec))|{"global.commissioning",SLOT,"global.leadership","global.force_request"}
    return digest({k:v for k,v in document["records"].items() if k not in ignored})


def catalogues_hash(document,spec):
    return digest({k:document["records"][k] for k in slots(spec)})


def source_spec(value):
    require(type(value) is dict and set(value)=={"root_id","domain_id","setup_id","bootstrap_actor","mode","capacity"},
            "REBIND_SPEC")
    result=SetupSpec(**{**value,"capacity":Capacity.parse(value["capacity"])})
    require(result.mode=="NATIVE_DOCS","REBIND_SPEC")
    return result


def catalogue_after(row,source,target,index,transition):
    require(type(row["generation"]) is int and 0<=row["generation"]<MAX_GENERATION
            and row["retention"]=="RETAINED" and type(row["body"]) is dict,"REBIND_CATALOGUE")
    refs=row["body"].get("artifacts")
    require(type(refs) is dict and set(refs)=={"input","output"},"REBIND_CATALOGUE")
    after=copy.deepcopy(row);after["generation"]+=1
    after["operation_id"]=digest(["reconfiguration-rebind",transition,f"target.{index:03d}.catalogue"])
    for kind,ref in refs.items():
        require(type(ref) is dict and set(ref)=={"id","seal"},"REBIND_CATALOGUE")
        key=f"artifact.{index:03d}.{kind}"
        require(ref["seal"]==digest([source.mode,source.root_id,source.domain_id,ref["id"],source.operation(key)]),
                "REBIND_CATALOGUE")
        after["body"]["artifacts"][kind]["seal"]=digest([
            target.mode,target.root_id,target.domain_id,ref["id"],target.operation(key)])
    return after


@dataclass(frozen=True,repr=False)
class RebindMutation(RecordMutation):
    @classmethod
    def prepare(cls,snapshot,owner):
        doc=snapshot.document();value=ledger(doc["records"][SLOT]);config=configuration(doc)
        require(type(owner) is OwnerGuard and owner.matches(doc),"OWNER_SUPERSEDED")
        planned=None if value is None else value.get("root_plan")
        require(config is not None and config["phase"]=="MAINTENANCE" and planned is not None
                and planned["transition_id"]==config["transition_id"]
                and value["barrier"] is not None and value["barrier"]["local_clear"] is True
                and value["barrier"]["transition_id"]==config["transition_id"]
                and not any(e["outcome"]=="UNKNOWN" for e in value["entries"].values())
                and matches_plan(doc,snapshot.binding,planned),"REBIND_PLAN")
        last=value["entries"].get(Action.IDENTITY.value)
        require(last is not None and last["outcome"]=="COMPLETE" and last["epoch"]<=owner.epoch
                and (last["epoch"]!=owner.epoch or last["owner"]==owner.owner)
                and last["operation_id"]==digest(["reconfiguration-root",config["transition_id"],"authority"]),
                "REBIND_NOT_COMPLETE")
        source,_=references(doc,snapshot.binding);target=replace(source,root_id=planned["target_root"])
        after_doc=copy.deepcopy(doc);cats=[]
        for index,key in enumerate(slots(source)):
            row=doc["records"][key];after=catalogue_after(row,source,target,index,config["transition_id"])
            after_doc["records"][key]=after
            cats.append(dict(slot=key,before_sha256=digest(row),after_sha256=digest(after),
                artifacts=copy.deepcopy(row["body"]["artifacts"])))
        after_marker=rebound_record(doc["records"]["global.commissioning"],target,config,
            source_blueprint_sha256=source.fingerprint,root_plan_sha256=digest(planned),
            work_sha256=work_hash(doc,source),catalogues_sha256=catalogues_hash(after_doc,target))
        handle=AuthorityHandle(snapshot.binding.document_id,digest([
            target.mode,target.root_id,target.domain_id,snapshot.binding.document_id,snapshot.binding.tab_id]),
            snapshot.binding.tab_id)
        result=cls(snapshot.binding,owner,encoded({k:v for k,v in doc.items() if k!="records"}),
            encoded(dict(settings_sha256=digest(doc["records"]["global.settings"]),
                summary_sha256=digest(doc["records"][SLOT]),work_sha256=work_hash(doc,source))),
            encoded(dict(source_spec=asdict(source),root_plan=planned,configuration=config,
                marker=doc["records"]["global.commissioning"],catalogues=cats)),
            encoded(dict(marker=after_marker,authority=handle.record())))
        result._validate()
        return result

    def _validate(self):
        try:
            require(type(self.binding) is AuthorityBinding and type(self.owner) is OwnerGuard
                    and type(self.owner.epoch) is int and 1<=self.owner.epoch<=MAX_GENERATION,"REBIND_WAL")
            parts={k:json.loads(getattr(self,k)) for k in ("header","protected","before","after")}
            require(all(encoded(v)==getattr(self,k) for k,v in parts.items())
                    and set(parts["before"])=={"source_spec","root_plan","configuration","marker","catalogues"}
                    and set(parts["after"])=={"marker","authority"}
                    and set(parts["protected"])=={"settings_sha256","summary_sha256","work_sha256"}
                    and all(hex64(v) for v in parts["protected"].values()),"REBIND_WAL")
            data=parts["before"];source=source_spec(data["source_spec"]);planned=root_plan(data["root_plan"])
            config=marker(data["configuration"]);target=replace(source,root_id=planned["target_root"])
            require(config["phase"]=="MAINTENANCE" and config["transition_id"]==planned["transition_id"]
                    and source.root_id==planned["source_root"] and source.fingerprint==planned["blueprint_sha256"]
                    and source.domain_id==self.binding.domain_id
                    and parts["header"]=={k:v for k,v in empty_document(source.domain_id,source.capacity).items() if k!="records"},
                    "REBIND_WAL")
            prior=data["marker"];proof=prior["body"].get("reconfiguration",{})
            ready_record(source,prior,root_transition=proof.get("transition_id"),configuration_revision=config["revision"])
            require(type(data["catalogues"]) is list and len(data["catalogues"])==source.capacity.devices,"REBIND_WAL")
            refs=[];ids={self.binding.document_id}
            for key,cat in zip(slots(source),data["catalogues"]):
                require(type(cat) is dict and set(cat)=={"slot","before_sha256","after_sha256","artifacts"}
                        and cat["slot"]==key and hex64(cat["before_sha256"]) and hex64(cat["after_sha256"])
                        and type(cat["artifacts"]) is dict and set(cat["artifacts"])=={"input","output"},"REBIND_WAL")
                for kind,ref in cat["artifacts"].items():
                    allocation=Allocation(ref["id"],source.operation("artifact."+key.split(".")[1]+"."+kind),seal=ref["seal"])
                    require(set(ref)=={"id","seal"} and allocation.object_id not in ids
                            and allocation.seal==digest([source.mode,source.root_id,source.domain_id,
                                allocation.object_id,allocation.operation_id]),"REBIND_WAL")
                    refs.append(dict(key="artifact."+key.split(".")[1]+"."+kind,id=ref["id"],seal=ref["seal"]))
                    ids.add(ref["id"])
            refs.append(dict(key="authority",id=self.binding.document_id,seal=digest([
                source.mode,source.root_id,source.domain_id,self.binding.document_id,self.binding.tab_id])))
            require(digest(refs)==planned["references_sha256"],"REBIND_WAL")
            after=parts["after"];after_proof=after["marker"]["body"]["reconfiguration"]
            require(after["marker"]==rebound_record(prior,target,config,
                    source_blueprint_sha256=source.fingerprint,root_plan_sha256=digest(planned),
                    work_sha256=parts["protected"]["work_sha256"],catalogues_sha256=after_proof["catalogues_sha256"])
                    and AuthorityHandle.parse(after["authority"])==AuthorityHandle(
                        self.binding.document_id,digest([target.mode,target.root_id,target.domain_id,
                            self.binding.document_id,self.binding.tab_id]),self.binding.tab_id)
                    and len(encoded(frozen_plan(self)))<=192*1024,"REBIND_WAL")
            return source,target,data,after,parts["protected"]
        except AuthorityError:raise
        except Exception:raise AuthorityError("REBIND_WAL") from None

    @classmethod
    def restore(cls,value,binding):
        raw=restored_plan(value,binding)
        result=cls(raw.binding,raw.owner,raw.header,raw.protected,raw.before,raw.after)
        result._validate();return result

    def evaluate(self,snapshot):
        source,target,data,after,protected=self._validate();doc=snapshot.document()
        if snapshot.binding!=self.binding or encoded({k:v for k,v in doc.items() if k!="records"})!=self.header:
            return "CONFLICT",None
        rows=doc["records"]
        if digest(rows["global.settings"])!=protected["settings_sha256"] or digest(rows[SLOT])!=protected["summary_sha256"]                 or work_hash(doc,source)!=protected["work_sha256"]:
            return "CONFLICT",None
        if rows["global.commissioning"]==after["marker"] and all(
                digest(rows[c["slot"]])==c["after_sha256"] for c in data["catalogues"]):
            return "CONFIRMED",None
        if not self.owner.matches(doc):return "SUPERSEDED",None
        if rows["global.commissioning"]!=data["marker"] or not all(
                digest(rows[c["slot"]])==c["before_sha256"] for c in data["catalogues"]):
            return "CONFLICT",None
        if not matches_plan(doc,self.binding,data["root_plan"]):return "CONFLICT",None
        desired=copy.deepcopy(doc);desired["records"]["global.commissioning"]=copy.deepcopy(after["marker"])
        for index,cat in enumerate(data["catalogues"]):
            row=catalogue_after(rows[cat["slot"]],source,target,index,data["configuration"]["transition_id"])
            if digest(row)!=cat["after_sha256"]:return "CONFLICT",None
            desired["records"][cat["slot"]]=row
        if catalogues_hash(desired,target)!=after["marker"]["body"]["reconfiguration"]["catalogues_sha256"]:
            return "CONFLICT",None
        validate_document(desired);require(preserves_effects(doc,desired),"REBIND_WAL")
        return "READY",desired


@dataclass(frozen=True,repr=False)
class RebindContext:
    maintenance: MaintenanceContext
    store: PrivateSettings


@dataclass(frozen=True,repr=False)
class ReboundStorage:
    storage: dict
    document_sha256: str
    _origin: object


class RemoteRebind:
    def __init__(self,context):
        require(type(context) is RebindContext and type(context.maintenance) is MaintenanceContext
                and type(context.store) is PrivateSettings,"REBIND_CONTEXT")
        self.context=context;self.ctx=context.maintenance;self.maintenance=Maintenance(self.ctx)
        require(type(self.ctx.storage_port) is NativeCommissioning and type(self.ctx.checkpoint) is NativeCheckpoint
                and type(self.ctx.effects) is Effects and self.ctx.effects.leadership is self.ctx.leadership
                and self.ctx.effects.checkpoint is self.ctx.checkpoint,"REBIND_CONTEXT")
        stores=[context.store,self.ctx.setup.store,self.ctx.store,self.ctx.baseline.store,
            self.ctx.checkpoint.store,self.ctx.effects.store]
        require(len({native_binding(s) for s in stores})==len(stores),"REBIND_STORE_ALIAS")

    def _role(self,*,owner,transition=None):
        pin=self.maintenance._proof()
        require(hashlib.sha256(pin.read(SCHEMA)).hexdigest()==SCHEMA_SHA256,"REBIND_INSTRUCTIONS")
        self.ctx.setup._fresh();choices=self.ctx.setup.private_choices();spec,handle=storage_spec(choices["storage"])
        require(choices["role"]=="watchdog" and self.ctx.setup._payload["state"]!="CANCELLED"
                and spec==self.ctx.storage_port.spec and spec.mode=="NATIVE_DOCS"
                and self.ctx.storage_port.authority(handle).binding==self.ctx.leadership.backend.binding,"REBIND_CONTEXT")
        caps,sample,cp=self.ctx.capabilities(),self.ctx.clock(),self.ctx.checkpoint.read()
        require(type(caps) is Capabilities and caps.installation_id==self.ctx.setup.installation_id
                and caps.observe and caps.coordinate and type(caps.actions) is frozenset
                and all(type(a) is Action for a in caps.actions) and Action.IDENTITY in caps.actions,"REBIND_CAPABILITY")
        require(type(sample) is ClockSample and sample.wall_trusted and sample.monotonic_trusted,"CONFIGURATION_CLOCK")
        require(type(cp.grant) is Grant and cp.grant.owner==self.ctx.setup.installation_id
                and cp.election is None and cp.mutation is None,"REBIND_CHECKPOINT")
        snap=self.ctx.leadership.backend.read();doc=snap.document();config=configuration(doc)
        require(config is not None and config["phase"]=="MAINTENANCE"
                and config["transition_id"]==self.ctx.baseline.transition_id
                and (transition is None or config["transition_id"]==transition)
                and cp.maintenance in {None,config["transition_id"]},"REBIND_RESERVATION")
        try:
            leader,request=self.ctx.leadership._records(doc);owns=self.ctx.leadership._owns(leader,request,cp.grant)
        except AuthorityError:
            require(not owner,"OWNER_SUPERSEDED");owns=False
        require(not owner or owns,"OWNER_SUPERSEDED")
        require(not inspect_work(snap,setup_payload=self.ctx.setup._payload,checkpoint=cp).blockers,"REBIND_UNRESOLVED")
        value=ledger(doc["records"][SLOT])
        require(value is not None and value["barrier"] is not None and value["barrier"]["local_clear"] is True
                and value["barrier"]["transition_id"]==config["transition_id"] and value.get("root_plan") is not None,
                "REBIND_PLAN")
        return snap,cp,pin

    def _state_shape(self,value,binding):
        require(type(value) is dict and set(value)==STATE_FIELDS and type(value["schema_version"]) is int
                and value["schema_version"]==1 and value["kind"]=="RECONFIGURATION_REMOTE_REBIND"
                and value["installation_id"]==self.ctx.setup.installation_id
                and value["authority"]==asdict(self.ctx.leadership.backend.binding) and value["binding"]==binding
                and hex64(value["transition_id"]) and hex64(value["base_sha256"])
                and type(value["base_revision"]) is int and 1<=value["base_revision"]<=MAX_GENERATION
                and type(value["dispatch"]) is str and value["dispatch"] in {"PREPARED","INVOKING","CONFIRMED"},"REBIND_WAL")
        validate_pin(value["pin"])
        plan=RebindMutation.restore(value["plan"],self.ctx.leadership.backend.binding)
        _,_,data,_,_=plan._validate()
        require(data["configuration"]["transition_id"]==value["transition_id"]
                and plan.owner.owner==value["installation_id"] and len(encoded(value))<=256*1024,"REBIND_WAL")
        return copy.deepcopy(value)

    def _state(self):
        current=self.context.store.read()
        return (None,0) if current is None else (
            self._state_shape(current.payload,native_binding(self.context.store)),current.revision)

    def _save(self,value,revision):
        self._state_shape(value,native_binding(self.context.store))
        self.context.store.save(value,expected_revision=revision)
        require(self._state()==(value,revision+1),"REBIND_UNCONFIRMED")

    def _proof(self,state,*,owner):
        snap,cp,pin=self._role(owner=owner,transition=state["transition_id"])
        require(pin_record(pin)==state["pin"] and self.ctx.setup.snapshot.revision==state["base_revision"]
                and sha(self.ctx.setup._payload)==state["base_sha256"],"REBIND_PROFILE_CHANGED")
        plan=RebindMutation.restore(state["plan"],snap.binding)
        source,_,_,_,_=plan._validate()
        require(source==self.ctx.storage_port.spec and (not owner or cp.grant.owner==plan.owner.owner
                and cp.grant.epoch==plan.owner.epoch),"OWNER_SUPERSEDED")
        return snap,plan

    def _objects(self,plan):
        _,target,data,after,_=plan._validate()
        port=NativeCommissioning(self.ctx.storage_port.drive,self.ctx.storage_port.docs,target,
            llm_authorized=True,root_transition=data["configuration"]["transition_id"])
        port.check_root()
        for cat in data["catalogues"]:
            for kind,ref in cat["artifacts"].items():
                key="artifact."+cat["slot"].split(".")[1]+"."+kind
                allocation=Allocation(ref["id"],target.operation(key),seal=digest([
                    target.mode,target.root_id,target.domain_id,ref["id"],target.operation(key)]))
                require(port.inspect(key,allocation)==allocation,"REBIND_AFTER_REQUIRED")
        handle=AuthorityHandle.parse(after["authority"])
        require(port.inspect_authority(target,handle)==handle and port.authority(handle).binding==plan.binding,
                "REBIND_AFTER_REQUIRED")
        return port,dict(spec=asdict(target),authority=handle.record(),root_transition=data["configuration"]["transition_id"])

    def begin(self,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        require(self._state()[0] is None,"REBIND_EXISTS")
        snap,cp,pin=self._role(owner=True)
        config=configuration(snap.document());self.ctx.checkpoint.reserve(config["transition_id"],owner_authorized=True)
        snap,cp,pin=self._role(owner=True)
        plan=RebindMutation.prepare(snap,OwnerGuard(cp.grant.owner,cp.grant.epoch))
        self._objects(plan)
        state=dict(schema_version=1,kind="RECONFIGURATION_REMOTE_REBIND",installation_id=self.ctx.setup.installation_id,
            transition_id=config["transition_id"],base_revision=self.ctx.setup.snapshot.revision,
            base_sha256=sha(self.ctx.setup._payload),authority=asdict(snap.binding),pin=pin_record(pin),
            binding=native_binding(self.context.store),dispatch="PREPARED",plan=frozen_plan(plan))
        fresh,_=self._proof(state,owner=True)
        require(plan.evaluate(fresh)[0]=="READY","REBIND_CHANGED")
        self._save(state,0);return "PREPARED"

    def advance(self,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        state,revision=self._state();require(state is not None,"REBIND_NOT_STARTED")
        if state["dispatch"]!="PREPARED":return self.inspect()
        snap,plan=self._proof(state,owner=True);self._objects(plan)
        require(plan.evaluate(snap)[0]=="READY","REBIND_CHANGED")
        with self.context.store.native.locked() as port:
            saved=self.context.store._decode(port.read("settings.json"),port.binding)
            require(port.read("settings.pending") is None and saved.payload==state and saved.revision==revision
                    and sha(port.binding)==state["binding"],"REBIND_CHANGED")
            fresh,_=self._proof(state,owner=True)
            require(plan.evaluate(fresh)[0]=="READY","REBIND_CHANGED")
            invoking={**state,"dispatch":"INVOKING"}
            result=self.context.store._save_locked(port,invoking,expected_revision=revision)
            require(result.payload==invoking,"REBIND_UNCONFIRMED")
            report=reconcile(self.ctx.leadership.backend,plan,mode="START",max_reads=4,max_writes=2)
        return self.inspect() if report.outcome=="CONFIRMED" else report.outcome

    def inspect(self):
        state,revision=self._state();require(state is not None,"REBIND_NOT_STARTED")
        snap,plan=self._proof(state,owner=False)
        if state["dispatch"]=="PREPARED":return "PREPARED"
        if plan.evaluate(snap)[0]!="CONFIRMED":return "UNKNOWN"
        port,storage=self._objects(plan);CommissionedStorage(port).verify(storage)
        if state["dispatch"]!="CONFIRMED":self._save({**state,"dispatch":"CONFIRMED"},revision)
        return "REBOUND"

    def recover_local(self,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        store=self.context.store
        with store.native.locked() as port:
            pending,raw=port.read("settings.pending"),port.read("settings.json")
            if pending is None:return "NO_PENDING"
            candidate=store._decode(pending,port.binding);current=None if raw is None else store._decode(raw,port.binding)
            require(candidate.revision==(0 if current is None else current.revision)+1
                    and candidate.previous==(None if current is None else current.payload),"REBIND_RECOVERY")
            state=self._state_shape(candidate.payload,sha(port.binding))
        self._proof(state,owner=False)
        with store.native.locked() as port:
            require(port.read("settings.pending")==pending and port.read("settings.json")==raw,"REBIND_RECOVERY")
            port.promote();require(port.read("settings.json")==pending,"REBIND_UNCONFIRMED")
        return "INSPECT_REQUIRED"

    def verify_current(self,*,owner_authorized=False):
        """Fresh shared AFTER proof without an old rebind WAL/profile/ACK."""
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        snap,cp,_=self._role(owner=True);doc=snap.document();value=ledger(doc["records"][SLOT])
        planned=root_plan(value["root_plan"]);config=configuration(doc);row=doc["records"]["global.commissioning"]
        body=row["body"];target=SetupSpec(body["root_id"],snap.binding.domain_id,body["setup_id"],
            body["bootstrap_actor"],body["mode"],Capacity.parse(doc["capacity"]))
        current_record(doc,target,root_transition=config["transition_id"])
        proof=body["reconfiguration"];source=replace(target,root_id=planned["source_root"])
        require(planned["transition_id"]==config["transition_id"] and target.root_id==planned["target_root"]
                and source.fingerprint==planned["blueprint_sha256"]==proof["source_blueprint_sha256"]
                and proof["root_plan_sha256"]==digest(planned) and proof["work_sha256"]==work_hash(doc,target)
                and proof["catalogues_sha256"]==catalogues_hash(doc,target),"REBIND_AFTER_REQUIRED")
        refs=[];ids={snap.binding.document_id}
        port=NativeCommissioning(self.ctx.storage_port.drive,self.ctx.storage_port.docs,target,
            llm_authorized=True,root_transition=config["transition_id"]);port.check_root()
        for key in target.artifact_keys:
            _,index,kind=key.split(".");cat=doc["records"]["target."+index+".catalogue"]
            require(cat["retention"]=="RETAINED" and type(cat["generation"]) is int and cat["generation"]>=1
                    and cat["operation_id"]==digest(["reconfiguration-rebind",config["transition_id"],"target."+index+".catalogue"]),
                    "REBIND_AFTER_REQUIRED")
            ref=cat["body"]["artifacts"][kind];allocation=Allocation(ref["id"],target.operation(key),seal=ref["seal"])
            require(ref["id"] not in ids and port.inspect(key,allocation)==allocation,"REBIND_AFTER_REQUIRED")
            ids.add(ref["id"]);refs.append(dict(key=key,id=ref["id"],seal=digest([
                source.mode,source.root_id,source.domain_id,ref["id"],source.operation(key)])))
        refs.append(dict(key="authority",id=snap.binding.document_id,seal=digest([
            source.mode,source.root_id,source.domain_id,snap.binding.document_id,snap.binding.tab_id])))
        require(digest(refs)==planned["references_sha256"],"REBIND_AFTER_REQUIRED")
        handle=AuthorityHandle(snap.binding.document_id,digest([
            target.mode,target.root_id,target.domain_id,snap.binding.document_id,snap.binding.tab_id]),snap.binding.tab_id)
        require(port.inspect_authority(target,handle)==handle and port.authority(handle).binding==snap.binding,"REBIND_AFTER_REQUIRED")
        storage=dict(spec=asdict(target),authority=handle.record(),root_transition=config["transition_id"])
        CommissionedStorage(port).verify(storage)
        fresh,new_cp,_=self._role(owner=True)
        require(new_cp.grant==cp.grant and fresh.raw==snap.raw,"REBIND_CHANGED")
        return ReboundStorage(storage,hashlib.sha256(snap.raw).hexdigest(),self)

    def require_current(self,proof,*,owner_authorized=False):
        require(type(proof) is ReboundStorage and proof._origin is self,"REBIND_AFTER_REQUIRED")
        current=self.verify_current(owner_authorized=owner_authorized)
        require(current==proof,"REBIND_CHANGED");return current
