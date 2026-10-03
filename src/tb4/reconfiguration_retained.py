"""Same retained authority publication after fresh C1 and actual first-run.
No root move, re-creation, commissioning rebind, execution or local activation.
"""
from dataclasses import asdict,dataclass
import copy
import hashlib
import json

from .ballpark import catalogue,validate as validate_descriptor
from .ballpark_records import shared,validate_header
from .ballpark_setup import pin_record,validate_pin
from .commissioning_checks import CommissionedStorage,Prerequisites
from .commissioning_state import Validation,storage_spec,validated
from .configuration_contract import configuration,require
from .drive.authority_transaction import OwnerGuard
from .drive.commissioning import digest,frozen_plan
from .drive.commissioning_native import NativeCommissioning
from .drive.commissioning_folder import FolderCommissioning
from .drive.folder_authority import FolderBinding
from .drive.folder_mapping import FolderMappedCommissioning
from .drive.docs_authority import AuthorityBinding,AuthorityError
from .exchange_layout import MAX_GENERATION,empty_document,encoded,validate_document
from .private_settings import PrivateSettings
from .reconfiguration_candidate import Candidate,DERIVED,SCHEMA,SCHEMA_SHA256,native_binding,seed
from .reconfiguration_commit import (ConfigurationCommit,ConfigurationMutation,CONTROLLED,STATE_FIELDS,
    catalogue_slots,catalogue_row,publication_header,work_sha)
from .reconfiguration_effects import SLOT,changed_row,ledger,covered
from .reconfiguration_folder_plan import matches_folder_plan
from .reconfiguration_maintenance import hex64,sha
from .watchdog.checkpoint_store import NativeCheckpoint
from .watchdog.leadership_runtime import Action

SCHEMA_DEFINITION="retainedConfigurationCommit"


def binding_matches(spec,handle,binding):
    if type(binding) is AuthorityBinding:
        return (spec.mode=="NATIVE_DOCS" and spec.domain_id==binding.domain_id
            and handle.object_id==binding.document_id and handle.tab_id==binding.tab_id)
    return (type(binding) is FolderBinding and spec.mode=="FOLDER_SQLITE_V1"
        and spec.root_id==binding.root_id==handle.object_id and spec.domain_id==binding.domain_id
        and handle.tab_id is None)


def retained_summary(row,config,mode):
    """Rootless retains the exact row; Folder removes only its terminal plan."""
    value=ledger(row)
    require(value is not None and value.get("root_plan") is None
        and value["barrier"] is not None and value["barrier"]["local_clear"] is True
        and value["barrier"]["transition_id"]==config["transition_id"]
        and not any(e["outcome"]=="UNKNOWN" for e in value["entries"].values()),"RETAINED_UNRESOLVED")
    plan=value.get("folder_plan")
    if plan is None:return copy.deepcopy(row)
    entry=value["entries"].get(Action.IDENTITY.value)
    require(mode=="FOLDER_SQLITE_V1" and plan["transition_id"]==config["transition_id"]
        and entry is not None and entry["operation_id"]==plan["operation_id"]
        and entry["outcome"]=="COMPLETE","RETAINED_UNRESOLVED")
    del value["folder_plan"]
    return changed_row(row,value)


@dataclass(frozen=True, repr=False)
class RetainedConfigurationMutation(ConfigurationMutation):
    @classmethod
    def prepare(cls, snapshot, owner, *, storage, descriptor, timing, pin, decision):
        doc = snapshot.document(); capacity = validate_document(doc); old = shared(doc)
        config = configuration(doc)
        require(type(owner) is OwnerGuard and owner.matches(doc), "OWNER_SUPERSEDED")
        require(config is not None and config["phase"] == "MAINTENANCE"
                and config["revision"] < MAX_GENERATION, "COMMIT_CONFIGURATION")
        new = catalogue(descriptor)
        require(new["domain_id"] == old["domain_id"] and new["revision"] == old["revision"]+1
                and [(d["device_id"],d["alias"]) for d in new["devices"]]
                == [(d["device_id"],d["alias"]) for d in old["devices"]], "COMMIT_IDENTITY")
        slots = doc["records"]["global.registry"]["body"]["slots"]
        rows = {
            "global.registry":dict(generation=new["revision"],operation_id=decision["id"],retention="RETAINED",
                body=publication_header(new,pin,decision,slots)),
            "global.settings":dict(generation=new["revision"],operation_id=decision["id"],retention="RETAINED",
                body=dict(descriptor_state="VALIDATED",revision=new["revision"],timing=copy.deepcopy(timing),
                    configuration={**config,"revision":config["revision"]+1,"phase":"ACTIVE"})),
            SLOT:retained_summary(doc["records"][SLOT],config,storage_spec(storage)[0].mode)}
        after_doc = copy.deepcopy(doc); after_doc["records"].update(rows)
        selected = {f"target.{i:03d}.catalogue":d for i,d in zip(slots,new["devices"])}
        cats = []
        for key in catalogue_slots(capacity):
            before = doc["records"][key]
            after = catalogue_row(before,selected[key],new["revision"],decision["id"]) if key in selected else before
            after_doc["records"][key] = after
            cats.append(dict(slot=key,before_sha256=digest(before),after_sha256=digest(after)))
        require(shared(after_doc) == new, "COMMIT_DESCRIPTOR")
        result = cls(snapshot.binding,owner,encoded({k:v for k,v in doc.items() if k != "records"}),
            encoded(dict(work_sha256=work_sha(doc))),
            encoded(dict(storage=storage,configuration=config,rows={k:doc["records"][k] for k in CONTROLLED},
                catalogues=cats)),
            encoded(dict(descriptor=new,timing=timing,pin=pin,decision=decision,rows=rows)))
        result._validate()
        return result

    def _validate(self):
        try:
            require(type(self.binding) in {AuthorityBinding,FolderBinding} and type(self.owner) is OwnerGuard
                    and type(self.owner.owner) is str and 1 <= len(self.owner.owner) <= 128
                    and type(self.owner.epoch) is int and 1 <= self.owner.epoch <= MAX_GENERATION, "COMMIT_WAL")
            parts = {k:json.loads(getattr(self,k)) for k in ("header","protected","before","after")}
            require(all(encoded(v) == getattr(self,k) for k,v in parts.items())
                    and set(parts["protected"]) == {"work_sha256"} and hex64(parts["protected"]["work_sha256"])
                    and set(parts["before"]) == {"storage","configuration","rows","catalogues"}
                    and set(parts["after"]) == {"descriptor","timing","pin","decision","rows"}, "COMMIT_WAL")
            before,after = parts["before"],parts["after"]
            spec,handle = storage_spec(before["storage"])
            require(binding_matches(spec,handle,self.binding)
                    and parts["header"] == {k:v for k,v in empty_document(spec.domain_id,spec.capacity).items() if k != "records"}
                    and set(before["rows"]) == set(after["rows"]) == CONTROLLED, "COMMIT_WAL")
            probe = empty_document(spec.domain_id,spec.capacity);probe["records"].update(before["rows"])
            old_config = configuration(probe)
            old_header = validate_header(before["rows"]["global.registry"]["body"],spec.capacity.devices)
            old_settings = before["rows"]["global.settings"]
            require(old_config == before["configuration"] and old_config["phase"] == "MAINTENANCE"
                    and old_config["revision"] < MAX_GENERATION
                    and before["rows"]["global.registry"]["generation"] == old_header["revision"]
                    and old_settings["generation"] == old_header["revision"]
                    and old_settings["operation_id"] == before["rows"]["global.registry"]["operation_id"]
                    == old_header["provenance"]["decision_id"], "COMMIT_WAL")
            validate_descriptor(after["descriptor"],shared=True);validate_pin(after["pin"])
            decision = after["decision"]
            require(type(decision) is dict and set(decision) == {"id","at","kind","candidate_digest"}
                    and decision["kind"] == "LOCAL_OWNER_CONFIRMATION" and hex64(decision["id"])
                    and hex64(decision["candidate_digest"]) and type(decision["at"]) is int
                    and 0 <= decision["at"] <= 10**12
                    and decision["id"] == digest(["reconfiguration-retained-commit",old_config["transition_id"],
                        decision["candidate_digest"],digest(after["pin"]),self.owner.owner,self.owner.epoch,decision["at"]])
                    and after["descriptor"]["revision"] == old_header["revision"]+1
                    and after["descriptor"]["domain_id"] == spec.domain_id
                    and len(after["descriptor"]["devices"]) == len(old_header["slots"]), "COMMIT_WAL")
            expected = {
                "global.registry":dict(generation=after["descriptor"]["revision"],operation_id=decision["id"],retention="RETAINED",
                    body=publication_header(after["descriptor"],after["pin"],decision,old_header["slots"])),
                "global.settings":dict(generation=after["descriptor"]["revision"],operation_id=decision["id"],retention="RETAINED",
                    body=dict(descriptor_state="VALIDATED",revision=after["descriptor"]["revision"],timing=after["timing"],
                        configuration={**old_config,"revision":old_config["revision"]+1,"phase":"ACTIVE"})),
                SLOT:retained_summary(before["rows"][SLOT],old_config,spec.mode)}
            require(after["rows"] == expected and type(before["catalogues"]) is list
                    and len(before["catalogues"]) == spec.capacity.devices, "COMMIT_WAL")
            for key,cat in zip(catalogue_slots(spec.capacity),before["catalogues"]):
                require(type(cat) is dict and set(cat) == {"slot","before_sha256","after_sha256"}
                        and cat["slot"] == key and hex64(cat["before_sha256"]) and hex64(cat["after_sha256"]), "COMMIT_WAL")
            probe["records"].update(after["rows"]);configuration(probe)
            require(len(encoded(frozen_plan(self))) <= 192*1024, "COMMIT_WAL_SIZE")
            return spec,before,after,parts["protected"]
        except AuthorityError:
            raise
        except Exception:
            raise AuthorityError("COMMIT_WAL") from None

@dataclass(frozen=True,repr=False)
class RetainedCommitContext:
    candidate: Candidate
    store: PrivateSettings


class RetainedConfigurationCommit(ConfigurationCommit):
    """Shares qualified conditional dispatch mechanics, with a distinct proof."""
    def __init__(self,context):
        require(type(context) is RetainedCommitContext and type(context.candidate) is Candidate
            and type(context.store) is PrivateSettings,"RETAINED_CONTEXT")
        self.context,self.candidate=context,context.candidate
        self.ctx=self.candidate.context.maintenance.context
        require(type(self.ctx.storage_port) in {NativeCommissioning,FolderCommissioning,FolderMappedCommissioning}
            and type(self.ctx.checkpoint) is NativeCheckpoint and self.ctx.effects is not None,"RETAINED_CONTEXT")
        self._bindings()

    def _bindings(self,commit_binding=None):
        require(commit_binding is None or hex64(commit_binding),"COMMIT_BINDING")
        values={**self.candidate._bindings(),**{k:native_binding(v) for k,v in (
            ("checkpoint",self.ctx.checkpoint.store),("effects",self.ctx.effects.store),
            ("maintenance",self.ctx.store),("baseline",self.ctx.baseline.store),
            ("resolution",self.candidate.context.resolution.store))},
            "commit":native_binding(self.context.store) if commit_binding is None else commit_binding}
        if type(self.ctx.storage_port) is FolderMappedCommissioning:
            values["mapping"]=native_binding(self.ctx.storage_port.mapping.store)
        require(len(set(values.values()))==len(values),"COMMIT_STORE_ALIAS")
        return values

    def _schema(self,value,*,commit_binding=None):
        require(type(value) is dict and set(value)==STATE_FIELDS
            and type(value["schema_version"]) is int and value["schema_version"]==1
            and value["kind"]=="RECONFIGURATION_RETAINED_COMMIT"
            and value["installation_id"]==self.candidate.original.installation_id
            and all(hex64(value[k]) for k in ("transition_id","base_sha256","stage_sha256","stage_state_sha256"))
            and all(type(value[k]) is int and 1<=value[k]<=MAX_GENERATION for k in ("base_revision","stage_revision"))
            and value["authority"]==asdict(self.ctx.leadership.backend.binding)
            and value["bindings"]==self._bindings(commit_binding)
            and type(value["dispatch"]) is str and value["dispatch"] in {"PREPARED","INVOKING","CONFIRMED"},
            "COMMIT_SCHEMA")
        validate_pin(value["pin"])
        plan=RetainedConfigurationMutation.restore(value["plan"],self.ctx.leadership.backend.binding)
        _,before,after,_=plan._validate()
        require(before["configuration"]["transition_id"]==value["transition_id"]
            and plan.owner.owner==value["installation_id"] and after["pin"]==value["pin"]
            and len(encoded(value))<=256*1024,"COMMIT_SCHEMA")
        return copy.deepcopy(value)

    def _source(self,state):
        pin=self.candidate.context.maintenance._proof()
        require(pin_record(pin)==state["pin"] and hashlib.sha256(pin.read(SCHEMA)).hexdigest()==SCHEMA_SHA256,
            "COMMIT_INSTRUCTIONS")
        return pin

    def _profile_evidence(self,state):
        stage=self.candidate.context.profile.read()
        archive=self.candidate.context.archive.read()
        transaction=self.candidate.context.transaction.read()
        require(stage is not None and stage.revision==state["stage_revision"] and sha(stage.payload)==state["stage_sha256"]
            and transaction is not None and sha(transaction.payload)==state["stage_state_sha256"]
            and archive is not None and archive.revision==1 and archive.previous is None
            and archive.payload["base_setup_revision"]==state["base_revision"]
            and archive.payload["base_setup_sha256"]==state["base_sha256"]
            and sha(archive.payload["profile"])==state["base_sha256"]
            and archive.payload["transition_id"]==state["transition_id"],"COMMIT_PROFILE_CHANGED")
        value,base=validated(stage.payload),validated(archive.payload["profile"])
        plan=RetainedConfigurationMutation.restore(state["plan"],self.ctx.leadership.backend.binding)
        _,before,after,_=plan._validate()
        require(all(value[k]==base[k] for k in ("installation_id","setup_nonce","operations"))
            and value["choices"]["role"]==base["choices"]["role"]=="watchdog"
            and value["choices"]["storage"]==base["choices"]["storage"]==before["storage"]
            and value["choices"].get("storage_request")==base["choices"].get("storage_request")
            and not set(value)&DERIVED
            and transaction.payload["seed_sha256"]==sha(seed(base))
            and catalogue(value["choices"]["descriptor"])==after["descriptor"]
            and sha(value["choices"]["descriptor"])==after["decision"]["candidate_digest"]
            and value["choices"]["timing"]==after["timing"],"COMMIT_PROFILE_CHANGED")
        return value,plan

    def _checker(self,checker,state=None):
        checked=self.candidate._checker(checker)
        require(checked.storage.port is self.ctx.storage_port,"RETAINED_CHECKER")
        if state is not None:
            _,plan=self._profile_evidence(state)
            spec,before,_,_=plan._validate()
            require(checked.storage.port.spec==spec,"RETAINED_STORAGE")
            CommissionedStorage(checked.storage.port).verify(before["storage"])
            summary=ledger(before["rows"][SLOT])
            folder=summary.get("folder_plan")
            if folder is not None:
                port=checked.storage.port
                require(type(port) is FolderMappedCommissioning,"RETAINED_FOLDER_AFTER_REQUIRED")
                mapping=port.mapping.read()
                require(mapping is not None and digest(mapping)==folder["mapping_sha256"]
                    and mapping["transition_id"]==state["transition_id"]
                    and str(port._config().root)==mapping["target_path"],"RETAINED_FOLDER_AFTER_REQUIRED")
        return checked

    def _before(self,state,checker,*,commit_binding=None):
        self._schema(state,commit_binding=commit_binding);self._source(state)
        staged,_=self.candidate._state();decision,pin=self.candidate._proof(staged)
        value,_=self._profile_evidence(state)
        stage=self.candidate.context.profile.read()
        require(stage is not None and stage.revision==state["stage_revision"]
            and stage.payload==value and sha(stage.payload)==state["stage_sha256"],"COMMIT_CHANGED")
        # UI review intentionally saves a new local revision. A frozen final
        # proof must run the actual first-run probes without that mutation.
        validation=self._checker(checker,state).validate(copy.deepcopy(value))
        require(type(validation) is Validation and pin_record(validation.pin)==state["pin"]
            and self.candidate.context.profile.read()==stage and self.candidate._state()[0]==staged,
            "COMMIT_CHANGED")
        staged,_=self.candidate._state();fresh,pin=self.candidate._proof(staged)
        snapshot,cp=self.candidate.context.maintenance._current()
        _,plan=self._profile_evidence(state)
        require(fresh==decision and cp.grant.owner==decision.owner==plan.owner.owner
            and cp.grant.epoch==decision.epoch==plan.owner.epoch and pin_record(pin)==state["pin"]
            and covered(snapshot.document(),state["transition_id"]) and plan.evaluate(snapshot)[0]=="READY",
            "COMMIT_CHANGED")
        _,before,_,_=plan._validate()
        folder=ledger(before["rows"][SLOT]).get("folder_plan")
        if folder is not None:
            require(matches_folder_plan(snapshot.document(),snapshot.binding,folder),"RETAINED_FOLDER_PLAN")
        self._checker(checker,state)
        self.candidate._proof(staged);self._profile_evidence(state)
        # Last coherent boundary precedes SDK dispatch, including late force/work changes.
        final,actual=self.candidate.context.maintenance._current()
        require(actual==cp and plan.evaluate(final)[0]=="READY","COMMIT_CHANGED")
        return final,plan

    def begin(self,checker,*,owner_authorized=False,decided_at):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        require(type(decided_at) is int and 0<=decided_at<=10**12 and self._state()[0] is None,"COMMIT_EXISTS")
        staged,_=self.candidate._state();self.candidate._proof(staged)
        snapshot,cp=self.candidate.context.maintenance._current()
        local=copy.deepcopy(self.candidate._setup(staged)._payload["choices"]["descriptor"])
        local["revision"]=shared(snapshot.document())["revision"]+1
        self.candidate.choose({"descriptor":local},owner_authorized=True)
        proof=self.candidate.require_validated(self._checker(checker))
        staged,_=self.candidate._state();decision,pin=self.candidate._proof(staged)
        snapshot,cp=self.candidate.context.maintenance._current()
        require(decision.owner==cp.grant.owner and decision.epoch==cp.grant.epoch,"COMMIT_CHANGED")
        model=self.candidate._setup(staged);choices=model.private_choices()
        owner_decision=dict(kind="LOCAL_OWNER_CONFIRMATION",at=decided_at,candidate_digest=sha(choices["descriptor"]))
        owner_decision["id"]=digest(["reconfiguration-retained-commit",staged["transition_id"],owner_decision["candidate_digest"],
            digest(pin_record(pin)),cp.grant.owner,cp.grant.epoch,decided_at])
        plan=RetainedConfigurationMutation.prepare(snapshot,OwnerGuard(cp.grant.owner,cp.grant.epoch),
            storage=choices["storage"],descriptor=choices["descriptor"],timing=choices["timing"],
            pin=pin_record(pin),decision=owner_decision)
        state=dict(schema_version=1,kind="RECONFIGURATION_RETAINED_COMMIT",installation_id=model.installation_id,
            transition_id=staged["transition_id"],base_revision=staged["base_setup_revision"],
            base_sha256=staged["base_setup_sha256"],stage_revision=proof.revision,stage_sha256=proof.setup_sha256,
            stage_state_sha256=sha(staged),authority=asdict(snapshot.binding),pin=pin_record(pin),
            bindings=self._bindings(),dispatch="PREPARED",plan=frozen_plan(plan))
        self._before(state,checker);self._save(state,0)
        return "PREPARED"

    def inspect(self):
        state,revision=self._state();require(state is not None,"COMMIT_NOT_STARTED")
        self._source(state);_,plan=self._profile_evidence(state)
        if state["dispatch"]=="PREPARED":return "PREPARED"
        if plan.evaluate(self.ctx.leadership.backend.read())[0]!="CONFIRMED":return "UNKNOWN"
        _,before,_,_=plan._validate()
        CommissionedStorage(self.ctx.storage_port).verify(before["storage"])
        self._source(state);self._profile_evidence(state)
        require(plan.evaluate(self.ctx.leadership.backend.read())[0]=="CONFIRMED","COMMIT_CHANGED")
        if state["dispatch"]!="CONFIRMED":self._save({**state,"dispatch":"CONFIRMED"},revision)
        return "PUBLISHED"

    def recover_local(self,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        store=self.context.store
        with store.native.locked() as port:
            pending,raw=port.read("settings.pending"),port.read("settings.json")
            if pending is None:return "NO_PENDING"
            candidate=store._decode(pending,port.binding);current=None if raw is None else store._decode(raw,port.binding)
            require(candidate.revision==(0 if current is None else current.revision)+1
                and candidate.previous==(None if current is None else current.payload),"COMMIT_RECOVERY")
            state=self._schema(candidate.payload,commit_binding=sha(port.binding))
        self._source(state);_,plan=self._profile_evidence(state)
        require(plan.evaluate(self.ctx.leadership.backend.read())[0] in {"READY","CONFIRMED","SUPERSEDED"},"COMMIT_RECOVERY")
        with store.native.locked() as port:
            require(port.read("settings.pending")==pending and port.read("settings.json")==raw,"COMMIT_RECOVERY")
            port.promote();require(port.read("settings.json")==pending,"COMMIT_UNCONFIRMED")
        return "INSPECT_REQUIRED"
