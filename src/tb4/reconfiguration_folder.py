"""Actual same-folder native transaction. UNKNOWN never permits a repeat."""
from dataclasses import asdict,dataclass
import copy
import hashlib

from .ballpark_setup import pin_record,validate_pin
from .commissioning_checks import CommissionedStorage
from .commissioning_state import storage_spec
from .configuration_contract import configuration,require
from .drive.authority_transaction import OwnerGuard
from .drive.commissioning import digest
from .drive.folder_authority import FolderConfig,FolderStore
from .drive.folder_mapping import FolderPathMapping,FolderMappedCommissioning,_path,_parent
from .drive.folder_protocol import FolderSnapshot
from .drive.folder_relocation import NativeFolderRename
from .drive.leadership import ClockSample,Grant
from .exchange_layout import MAX_GENERATION,encoded as exchange_encoded
from .private_settings import PrivateSettings,encoded
from .private_settings_linux import LinuxSettingsNative
from .reconfiguration_candidate import Candidate,native_binding
from .reconfiguration_effects import Effects,EffectMutation,SLOT,ledger,changed_row
from .reconfiguration_folder_plan import folder_plan,matches_folder_plan
from .reconfiguration_inspection import inspect as inspect_work
from .reconfiguration_maintenance import Maintenance,MaintenanceContext,hex64,sha
from .reconfiguration_root_plan import stable_records
from .watchdog.checkpoint_store import NativeCheckpoint
from .watchdog.leadership_runtime import Action,Capabilities

SCHEMA="protocol/folder-relocation-v1.schema.json"
SCHEMA_SHA256="9c7e56fd2ea19348c49b9031c5d3321b0dfb24b0e2667ad664ad5a98c4428525"
FIELDS=frozenset({"schema_version","kind","installation_id","transition_id","configuration_revision",
    "base_revision","base_sha256","candidate_revision","candidate_sha256","authority","pin","binding",
    "mapping_sha256","records_sha256","operation_id","epoch","dispatch","phase"})


def _role(ctx,pin,document,*,reserved,revision,allow_operation=None,require_owner=True):
    ctx.setup._fresh()
    choices=ctx.setup.private_choices();spec,handle=storage_spec(choices["storage"])
    require(choices["role"]=="watchdog" and ctx.setup._payload["state"]!="CANCELLED"
            and type(ctx.storage_port) is FolderMappedCommissioning and spec==ctx.storage_port.spec
            and spec.mode=="FOLDER_SQLITE_V1","FOLDER_RELOCATION_CONTEXT")
    require(hashlib.sha256(pin.read(SCHEMA)).hexdigest()==SCHEMA_SHA256,"FOLDER_RELOCATION_INSTRUCTIONS")
    sample,caps,checkpoint=ctx.clock(),ctx.capabilities(),ctx.checkpoint.read()
    require(type(sample) is ClockSample and sample.wall_trusted and sample.monotonic_trusted,
            "CONFIGURATION_CLOCK")
    require(type(caps) is Capabilities and caps.installation_id==ctx.setup.installation_id
            and caps.observe and caps.coordinate and type(caps.actions) is frozenset
            and all(type(a) is Action for a in caps.actions) and Action.IDENTITY in caps.actions,
            "FOLDER_RELOCATION_CAPABILITY")
    require(type(checkpoint.grant) is Grant and checkpoint.grant.owner==ctx.setup.installation_id
            and checkpoint.election is None and checkpoint.mutation is None,"FOLDER_RELOCATION_CHECKPOINT")
    config=configuration(document)
    require(config is not None and config["phase"]=="MAINTENANCE"
            and checkpoint.maintenance in {None,config["transition_id"]}
            and (not reserved or checkpoint.maintenance==config["transition_id"]),"FOLDER_RELOCATION_RESERVATION")
    from .drive.docs_authority import AuthorityError
    try:
        leader,request=ctx.leadership._records(document)
        owns=ctx.leadership._owns(leader,request,checkpoint.grant)
    except AuthorityError:
        require(not require_owner,"OWNER_SUPERSEDED")
        owns=False
    require(not require_owner or owns,"OWNER_SUPERSEDED")
    value=ledger(document["records"][SLOT])
    require(value is not None and value["barrier"] is not None and value["barrier"]["local_clear"] is True
            and value["barrier"]["transition_id"]==config["transition_id"],"FOLDER_RELOCATION_EVIDENCE")
    snapshot=FolderSnapshot(ctx.leadership.backend.binding,revision,exchange_encoded(document),None)
    facts=inspect_work(snapshot,setup_payload=ctx.setup._payload,checkpoint=checkpoint)
    entry=value["entries"].get(Action.IDENTITY.value)
    unknown={action:fact for action,fact in value["entries"].items() if fact["outcome"]=="UNKNOWN"}
    allowed=(allow_operation is not None and entry is not None and entry["operation_id"]==allow_operation
             and unknown=={Action.IDENTITY.value:entry})
    require(all(allowed and ((b.kind=="SHARED_EFFECT_UNKNOWN" and b.identity==allow_operation)
            or (b.kind=="SHARED_UNKNOWN" and b.identity==SLOT)) for b in facts.blockers),
            "FOLDER_RELOCATION_UNRESOLVED")
    return checkpoint,config,handle,value,owns


def _paths(mapping,expected):
    source,target=_path(mapping["source_path"]),_path(mapping["target_path"])
    _parent(source,mapping["source_parent"]);_parent(target,mapping["target_parent"])
    # Selection checks exact objects/marker. This helper performs no DB read,
    # and is safe under the original inode's exclusive lock.
    from .drive.folder_authority import identity
    import os
    found=[]
    for path in (source,target):
        if not os.path.lexists(path):continue
        require(identity(path)==expected.root_identity,"FOLDER_RELOCATION_CONFLICT")
        config=FolderConfig(path,expected.binding,expected.root_identity,expected.db_identity,expected.journal_identity)
        config.verify();found.append(config)
    require(len(found)==1,"FOLDER_RELOCATION_UNAVAILABLE")
    return ("BEFORE" if found[0].root==source else "AFTER"),found[0]


@dataclass(frozen=True,repr=False)
class FolderRelocationContext:
    candidate: Candidate
    checker: object
    mapping: FolderPathMapping
    store: PrivateSettings
    native: NativeFolderRename


class FolderRelocation:
    def __init__(self,context):
        require(type(context) is FolderRelocationContext and type(context.candidate) is Candidate
                and type(context.mapping) is FolderPathMapping and type(context.store) is PrivateSettings
                and type(context.store.native) is LinuxSettingsNative and type(context.native) is NativeFolderRename,
                "FOLDER_RELOCATION_CONTEXT")
        self.context=context;self.maintenance=context.candidate.context.maintenance
        self.ctx=self.maintenance.context
        require(type(self.ctx.storage_port) is FolderMappedCommissioning
                and self.ctx.storage_port.mapping is context.mapping and type(self.ctx.effects) is Effects
                and type(self.ctx.checkpoint) is NativeCheckpoint,"FOLDER_RELOCATION_CONTEXT")
        self.expected=self.ctx.storage_port.expected
        all_stores=[self.ctx.setup.store,self.ctx.store,self.ctx.baseline.store,self.ctx.checkpoint.store,
            self.ctx.effects.store,context.candidate.context.resolution.store,context.mapping.store,
            context.candidate.context.profile,context.candidate.context.archive,context.candidate.context.transaction,
            context.store]
        require(all(type(s.native) is LinuxSettingsNative for s in all_stores)
                and len({native_binding(s) for s in all_stores})==len(all_stores),"FOLDER_RELOCATION_STORE_ALIAS")
        mapping=context.mapping.read();require(mapping is not None,"FOLDER_RELOCATION_MAPPING")
        for s in all_stores:
            require(not any(s.native.root==_path(mapping[k]) or _path(mapping[k]) in s.native.root.parents
                    for k in ("source_path","target_path")),"FOLDER_RELOCATION_STORE_ALIAS")

    def _shape(self,v,binding):
        require(type(v) is dict and set(v)==FIELDS and type(v["schema_version"]) is int
                and v["schema_version"]==1 and v["kind"]=="FOLDER_RELOCATION"
                and v["installation_id"]==self.ctx.setup.installation_id
                and v["authority"]==asdict(self.expected.binding) and v["binding"]==binding
                and type(v["dispatch"]) is str and v["dispatch"] in {"PREPARED","INVOKING"}
                and type(v["phase"]) is str and v["phase"] in {"ARMED","APPLIED","SETTLED"}
                and (v["phase"]=="ARMED" or v["dispatch"]=="INVOKING"),"FOLDER_RELOCATION_WAL")
        require(all(type(v[k]) is int and 1<=v[k]<=MAX_GENERATION for k in
                ("configuration_revision","base_revision","candidate_revision","epoch"))
                and all(hex64(v[k]) for k in ("transition_id","base_sha256","candidate_sha256",
                    "mapping_sha256","records_sha256","operation_id")),"FOLDER_RELOCATION_WAL")
        validate_pin(v["pin"])
        require(v["operation_id"]==digest(["folder-relocation",v["transition_id"],v["mapping_sha256"]])
                and len(encoded(v))<=64*1024,"FOLDER_RELOCATION_WAL")
        return copy.deepcopy(v)

    def _state(self):
        current=self.context.store.read()
        return (None,0) if current is None else (self._shape(current.payload,native_binding(self.context.store)),current.revision)

    def _save(self,value,revision):
        value=self._shape(value,native_binding(self.context.store))
        self.context.store.save(value,expected_revision=revision)
        require(self._state()==(value,revision+1),"FOLDER_RELOCATION_UNCONFIRMED")
        return value

    def _intent(self,state):
        m=self.context.mapping.read()
        require(m is not None and digest(m)==state["mapping_sha256"],"FOLDER_RELOCATION_MAPPING")
        return folder_plan(dict(schema_version=1,mode="FOLDER_SQLITE_V1",transition_id=state["transition_id"],
            operation_id=state["operation_id"],authority=state["authority"],blueprint_sha256=m["blueprint_sha256"],
            handle_sha256=m["handle_sha256"],mapping_sha256=state["mapping_sha256"],records_sha256=state["records_sha256"]))

    def _proof(self,state,document=None,*,owner=True,planned=True,sql_revision=None):
        pin=self.maintenance._proof()
        require(pin_record(pin)==state["pin"],"FOLDER_RELOCATION_INSTRUCTIONS")
        self.ctx.setup._fresh();candidate_state,_=self.context.candidate._state()
        model=self.context.candidate._setup(candidate_state)
        require(self.ctx.setup.snapshot.revision==state["base_revision"]
                and sha(self.ctx.setup._payload)==state["base_sha256"]
                and model.snapshot.revision==state["candidate_revision"]
                and sha(model._payload)==state["candidate_sha256"],"FOLDER_RELOCATION_PROFILE_CHANGED")
        if document is None:
            snapshot=self.ctx.leadership.backend.read();document=snapshot.document();sql_revision=snapshot.revision
        require(type(sql_revision) is int and sql_revision>=1,"FOLDER_RELOCATION_SNAPSHOT")
        checkpoint,config,handle,value,owns=_role(self.ctx,pin,document,reserved=True,
            revision=sql_revision,allow_operation=state["operation_id"],require_owner=owner)
        require(config["transition_id"]==state["transition_id"] and config["revision"]==state["configuration_revision"]
                and stable_records(document)==state["records_sha256"]
                and digest(handle.record())==self._intent(state)["handle_sha256"],"FOLDER_RELOCATION_CHANGED")
        if planned:require(value.get("folder_plan")==self._intent(state),"FOLDER_RELOCATION_PLAN")
        entry=value["entries"].get(Action.IDENTITY.value)
        if entry is not None and entry["outcome"]=="UNKNOWN":
            require(entry==dict(owner=state["installation_id"],epoch=state["epoch"],
                operation_id=state["operation_id"],outcome="UNKNOWN"),"FOLDER_RELOCATION_SENDER_CHANGED")
        if owner:require(checkpoint.grant.epoch==state["epoch"],"OWNER_SUPERSEDED")
        return checkpoint,owns

    def begin(self,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        require(self._state()[0] is None,"FOLDER_RELOCATION_EXISTS")
        qualified=self.context.candidate.require_validated(self.context.checker)
        mapping=self.context.mapping.read();position,_=_paths(mapping,self.expected)
        require(position=="BEFORE" and mapping["transition_id"]==qualified.decision.transition_id,
                "FOLDER_RELOCATION_MAPPING")
        snapshot=self.ctx.leadership.backend.read();document=snapshot.document()
        pin=self.maintenance._proof();checkpoint,config,_,value,_=_role(self.ctx,pin,document,reserved=True,revision=snapshot.revision)
        require(value.get("root_plan") is None and value.get("folder_plan") is None,"FOLDER_RELOCATION_PLAN")
        state=dict(schema_version=1,kind="FOLDER_RELOCATION",installation_id=self.ctx.setup.installation_id,
            transition_id=config["transition_id"],configuration_revision=config["revision"],
            base_revision=self.ctx.setup.snapshot.revision,base_sha256=sha(self.ctx.setup._payload),
            candidate_revision=qualified.revision,candidate_sha256=qualified.setup_sha256,
            authority=asdict(self.expected.binding),pin=pin_record(pin),binding=native_binding(self.context.store),
            mapping_sha256=digest(mapping),records_sha256=stable_records(document),
            operation_id=digest(["folder-relocation",config["transition_id"],digest(mapping)]),
            epoch=checkpoint.grant.epoch,dispatch="PREPARED",phase="ARMED")
        self._proof(state,planned=False);self._save(state,0)
        return "PREPARED"

    def _plan(self,state):
        self._proof(state,planned=False)
        require(self.ctx.effects.inspect() in {"NO_PENDING","CONFIRMED"},"FOLDER_RELOCATION_EFFECT_PENDING")
        snap=self.ctx.leadership.backend.read();doc=snap.document();value=ledger(doc["records"][SLOT])
        expected=self._intent(state)
        if value.get("folder_plan") is not None:
            require(value["folder_plan"]==expected,"FOLDER_RELOCATION_PLAN")
            return "CONFIRMED"
        cp,_=self._proof(state,doc,planned=False,sql_revision=snap.revision)
        mutation=EffectMutation.prepare(snap,OwnerGuard(cp.grant.owner,cp.grant.epoch),
            changed_row(doc["records"][SLOT],{**value,"folder_plan":expected}),purpose="FOLDER_PLAN")
        return self.ctx.effects._commit(mutation)

    def advance(self,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        state,revision=self._state();require(state is not None,"FOLDER_RELOCATION_NOT_STARTED")
        if state["dispatch"]=="INVOKING":return self.inspect()
        if self._plan(state)!="CONFIRMED":return "UNKNOWN"
        cp,_=self._proof(state);entry=self.ctx.effects.receipt(Action.IDENTITY)
        expected=dict(owner=cp.grant.owner,epoch=cp.grant.epoch,operation_id=state["operation_id"],outcome="UNKNOWN")
        if entry!=expected:
            if self.ctx.effects.start(cp.grant,Action.IDENTITY,state["operation_id"],
                    maintenance_transition=state["transition_id"])!="CONFIRMED":return "UNKNOWN"
        self._proof(state)
        mapping=self.context.mapping.read();position,config=_paths(mapping,self.expected)
        require(position=="BEFORE","FOLDER_RELOCATION_INSPECT_REQUIRED")
        # Native and original DB locks remain held through possible invocation.
        with self.context.store.native.locked() as port:
            saved=self.context.store._decode(port.read("settings.json"),port.binding)
            require(port.read("settings.pending") is None and saved.payload==state and saved.revision==revision
                    and sha(port.binding)==state["binding"],"FOLDER_RELOCATION_CHANGED")
            self._proof(state)
            invoking={**state,"dispatch":"INVOKING"}
            armed=self.context.store._save_locked(port,invoking,expected_revision=revision)
            require(armed.payload==invoking,"FOLDER_RELOCATION_UNCONFIRMED")
            with FolderStore(config).connection() as connection:
                # Pure proof consumes this actually locked SQL image. It must
                # never call backend.read/mapping.select under this inode lock.
                sql_revision,raw=FolderStore(config)._row(connection)
                from .drive.docs_authority import validated
                self._proof(invoking,validated(raw,config.binding),sql_revision=sql_revision)
                require(self.context.mapping.read()==mapping,"FOLDER_RELOCATION_MAPPING")
                require(_paths(mapping,self.expected)[0]=="BEFORE","FOLDER_RELOCATION_CHANGED")
                try:
                    self.context.native.run(config.root,_path(mapping["target_path"]),
                        mapping["source_parent"],mapping["target_parent"],mapping["root_identity"])
                except Exception:return "UNKNOWN"
                require(_paths(mapping,self.expected)[0]=="AFTER","FOLDER_RELOCATION_UNCONFIRMED")
                self.context.store._save_locked(port,{**invoking,"phase":"APPLIED"},expected_revision=revision+1)
        return self.inspect()

    def inspect(self):
        state,revision=self._state();require(state is not None,"FOLDER_RELOCATION_NOT_STARTED")
        cp,owns=self._proof(state,owner=False,planned=state["dispatch"]=="INVOKING")
        position,_=_paths(self.context.mapping.read(),self.expected)
        if position=="BEFORE":return "PREPARED" if state["dispatch"]=="PREPARED" else "UNKNOWN"
        require(state["dispatch"]=="INVOKING","FOLDER_RELOCATION_CONFLICT")
        if not owns or cp.grant.epoch!=state["epoch"]:return "APPLIED_OWNER_SUPERSEDED"
        if state["phase"]=="SETTLED":return "MOVED"
        settle=FolderAppliedSettlement(self.ctx,self.context.mapping)
        if settle.settle(owner_authorized=True)!="CONFIRMED":return "UNKNOWN"
        self._save({**state,"phase":"SETTLED"},revision)
        return "MOVED"

    def recover_local(self,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        store=self.context.store
        with store.native.locked() as port:
            pending,raw=port.read("settings.pending"),port.read("settings.json")
            if pending is None:return "NO_PENDING"
            candidate=store._decode(pending,port.binding)
            current=None if raw is None else store._decode(raw,port.binding)
            require(candidate.revision==(0 if current is None else current.revision)+1
                    and candidate.previous==(None if current is None else current.payload),"FOLDER_RELOCATION_RECOVERY")
            state=self._shape(candidate.payload,sha(port.binding))
        self._proof(state,owner=False,planned=state["dispatch"]=="INVOKING")
        with store.native.locked() as port:
            require(port.read("settings.pending")==pending and port.read("settings.json")==raw,
                    "FOLDER_RELOCATION_RECOVERY")
            port.promote();require(port.read("settings.json")==pending,"FOLDER_RELOCATION_UNCONFIRMED")
        return "INSPECT_REQUIRED"


class FolderAppliedSettlement:
    """Actual current role verifies same-inode AFTER, without former host/WAL."""
    def __init__(self,context,mapping):
        require(type(context) is MaintenanceContext and type(context.storage_port) is FolderMappedCommissioning
                and type(context.effects) is Effects and type(context.checkpoint) is NativeCheckpoint
                and type(mapping) is FolderPathMapping and context.storage_port.mapping is mapping
                and context.effects.leadership is context.leadership and context.effects.checkpoint is context.checkpoint,
                "FOLDER_RELOCATION_CONTEXT")
        self.ctx,self.mapping=context,mapping
        self.maintenance=Maintenance(context)

    def _current(self,*,reserved):
        pin=self.maintenance._proof();snapshot=self.ctx.leadership.backend.read();doc=snapshot.document()
        value=ledger(doc["records"][SLOT]);plan=None if value is None else value.get("folder_plan")
        require(plan is not None and matches_folder_plan(doc,snapshot.binding,plan),"FOLDER_RELOCATION_PLAN")
        cp,config,handle,value,_=_role(self.ctx,pin,doc,reserved=reserved,revision=snapshot.revision,
            allow_operation=plan["operation_id"])
        mapping=self.mapping.read()
        require(mapping is not None and digest(mapping)==plan["mapping_sha256"]
                and mapping["transition_id"]==config["transition_id"]==plan["transition_id"]
                and digest(handle.record())==plan["handle_sha256"]
                and _paths(mapping,self.ctx.storage_port.expected)[0]=="AFTER","FOLDER_RELOCATION_AFTER_REQUIRED")
        CommissionedStorage(self.ctx.storage_port).verify(self.ctx.setup.private_choices()["storage"])
        entry=value["entries"].get(Action.IDENTITY.value)
        require(entry is not None and entry["operation_id"]==plan["operation_id"]
                and entry["outcome"] in {"UNKNOWN","COMPLETE"} and entry["epoch"]<=cp.grant.epoch
                and (entry["epoch"]!=cp.grant.epoch or entry["owner"]==cp.grant.owner),"FOLDER_RELOCATION_EVIDENCE")
        return snapshot,cp,config,entry,plan

    def settle(self,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        first=self._current(reserved=False)
        self.ctx.checkpoint.reserve(first[2]["transition_id"],owner_authorized=True)
        require(self.ctx.effects.inspect() in {"NO_PENDING","CONFIRMED"},"FOLDER_RELOCATION_EFFECT_PENDING")
        snapshot,cp,config,entry,plan=self._current(reserved=True)
        require(first[2:]==(config,entry,plan),"FOLDER_RELOCATION_CHANGED")
        if entry["outcome"]=="COMPLETE":return "CONFIRMED"
        doc=snapshot.document();value=ledger(doc["records"][SLOT])
        value["entries"][Action.IDENTITY.value]={**entry,"outcome":"COMPLETE"}
        mutation=EffectMutation.prepare(snapshot,OwnerGuard(cp.grant.owner,cp.grant.epoch),
            changed_row(doc["records"][SLOT],value),purpose="FOLDER_SETTLE")
        return self.ctx.effects._commit(mutation)
