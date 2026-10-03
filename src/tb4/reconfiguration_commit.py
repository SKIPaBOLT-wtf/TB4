"""Protected same-authority descriptor/configuration publication.

This publishes shared facts only. Original profile promotion, local admission,
release/deployment and ordinary execution remain separate qualified boundaries.
"""
from dataclasses import asdict, dataclass
import copy
import hashlib
import json

from .ballpark import catalogue, validate as validate_descriptor
from .ballpark_records import compact, provenance, shared, validate_header
from .ballpark_setup import pin_record, validate_pin
from .commissioning_checks import CommissionedStorage
from .commissioning_state import storage_spec, validated
from .configuration_contract import configuration, require
from .drive.authority_transaction import OwnerGuard, RecordMutation, reconcile
from .drive.commissioning import digest, frozen_plan, restored_plan
from .drive.commissioning_native import NativeCommissioning
from .drive.docs_authority import AuthorityBinding, AuthorityError, WriteResult
from .exchange_layout import MAX_GENERATION, empty_document, encoded, validate_document
from .private_settings import PrivateSettings
from .reconfiguration_candidate import SCHEMA, native_binding
from .reconfiguration_effects import SLOT, changed_row, ledger
from .reconfiguration_maintenance import hex64, sha
from .reconfiguration_post_root import PostRootCandidate, PostRootValidation
from .watchdog.leadership_runtime import Action

SCHEMA_DEFINITION = "configurationCommit"
SCHEMA_SHA256 = "b4e9aefd0d9e88c02d462745632c1853cf4b7ba05b146be17a598c11f9ab0498"
CONTROLLED = frozenset({"global.registry", "global.settings", SLOT})
STATE_FIELDS = frozenset({"schema_version", "kind", "installation_id", "transition_id",
    "base_revision", "base_sha256", "stage_revision", "stage_sha256", "stage_state_sha256",
    "authority", "pin", "bindings", "dispatch", "plan"})


def catalogue_slots(capacity):
    return tuple(f"target.{i:03d}.catalogue" for i in range(capacity.devices))


def publication_header(descriptor, pin, decision, slots):
    validate_descriptor(descriptor,shared=True)
    return dict(schema_version=1,kind="BALLPARK_REVISION",codec=1,revision=descriptor["revision"],
        slots=copy.deepcopy(slots),sha256=digest(descriptor),provenance=provenance(dict(pin=pin,decision=decision)))


def work_sha(document):
    capacity = validate_document(document)
    excluded = CONTROLLED | set(catalogue_slots(capacity)) | {"global.leadership", "global.force_request"}
    return digest({k:v for k,v in document["records"].items() if k not in excluded})


def consumed_summary(row, config):
    """Remove only the qualified terminal plan, retaining every effect receipt."""
    value = ledger(row)
    require(value is not None and value.get("root_plan") is not None
            and value["root_plan"]["transition_id"] == config["transition_id"]
            and value["barrier"] is not None and value["barrier"]["local_clear"] is True
            and value["barrier"]["transition_id"] == config["transition_id"]
            and not any(e["outcome"] == "UNKNOWN" for e in value["entries"].values()), "COMMIT_UNRESOLVED")
    last = value["entries"].get(Action.IDENTITY.value)
    require(last is not None and last["outcome"] == "COMPLETE"
            and last["operation_id"] == digest(["reconfiguration-root",config["transition_id"],"authority"]),
            "COMMIT_UNRESOLVED")
    del value["root_plan"]
    return changed_row(row,value)


def catalogue_row(row, device, revision, operation):
    require(type(row["generation"]) is int and 0 <= row["generation"] < MAX_GENERATION
            and row["retention"] == "RETAINED" and type(row["body"]) is dict
            and row["body"].get("discovery",{}).get("device_id") == device["device_id"]
            and row["body"]["discovery"]["alias"] == device["alias"], "COMMIT_IDENTITY")
    result = copy.deepcopy(row)
    result.update(generation=row["generation"]+1,operation_id=operation)
    result["body"]["ballpark"] = compact(device,revision)
    return result


@dataclass(frozen=True, repr=False)
class ConfigurationMutation(RecordMutation):
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
            SLOT:consumed_summary(doc["records"][SLOT],config)}
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
            require(type(self.binding) is AuthorityBinding and type(self.owner) is OwnerGuard
                    and type(self.owner.owner) is str and 1 <= len(self.owner.owner) <= 128
                    and type(self.owner.epoch) is int and 1 <= self.owner.epoch <= MAX_GENERATION, "COMMIT_WAL")
            parts = {k:json.loads(getattr(self,k)) for k in ("header","protected","before","after")}
            require(all(encoded(v) == getattr(self,k) for k,v in parts.items())
                    and set(parts["protected"]) == {"work_sha256"} and hex64(parts["protected"]["work_sha256"])
                    and set(parts["before"]) == {"storage","configuration","rows","catalogues"}
                    and set(parts["after"]) == {"descriptor","timing","pin","decision","rows"}, "COMMIT_WAL")
            before,after = parts["before"],parts["after"]
            spec,handle = storage_spec(before["storage"])
            require(spec.mode == "NATIVE_DOCS" and spec.domain_id == self.binding.domain_id
                    and handle.object_id == self.binding.document_id and handle.tab_id == self.binding.tab_id
                    and before["storage"].get("root_transition") == before["configuration"]["transition_id"]
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
                    and decision["id"] == digest(["reconfiguration-commit",old_config["transition_id"],
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
                SLOT:consumed_summary(before["rows"][SLOT],old_config)}
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

    @classmethod
    def restore(cls, value, binding):
        raw = restored_plan(value,binding)
        result = cls(raw.binding,raw.owner,raw.header,raw.protected,raw.before,raw.after)
        result._validate();return result

    def evaluate(self, snapshot):
        spec,before,after,protected = self._validate();doc = snapshot.document();rows = doc["records"]
        if snapshot.binding != self.binding or encoded({k:v for k,v in doc.items() if k != "records"}) != self.header:
            return "CONFLICT",None
        if work_sha(doc) != protected["work_sha256"]:return "CONFLICT",None
        if all(rows[k] == v for k,v in after["rows"].items()) and all(
                digest(rows[c["slot"]]) == c["after_sha256"] for c in before["catalogues"]):
            require(shared(doc) == after["descriptor"], "COMMIT_DESCRIPTOR")
            return "CONFIRMED",None
        if not self.owner.matches(doc):return "SUPERSEDED",None
        if any(rows[k] != v for k,v in before["rows"].items()) or any(
                digest(rows[c["slot"]]) != c["before_sha256"] for c in before["catalogues"]):
            return "CONFLICT",None
        old = shared(doc)
        if [(d["device_id"],d["alias"]) for d in old["devices"]] != [
                (d["device_id"],d["alias"]) for d in after["descriptor"]["devices"]]:return "CONFLICT",None
        selected = {f"target.{i:03d}.catalogue":d for i,d in zip(
            before["rows"]["global.registry"]["body"]["slots"],after["descriptor"]["devices"])}
        desired = copy.deepcopy(doc);desired["records"].update(copy.deepcopy(after["rows"]))
        for cat in before["catalogues"]:
            key = cat["slot"]
            row = catalogue_row(rows[key],selected[key],after["descriptor"]["revision"],after["decision"]["id"]) if key in selected else rows[key]
            if digest(row) != cat["after_sha256"]:return "CONFLICT",None
            desired["records"][key] = row
        require(shared(desired) == after["descriptor"], "COMMIT_DESCRIPTOR")
        return "READY",desired


@dataclass(frozen=True, repr=False)
class CommitContext:
    candidate: PostRootCandidate
    store: PrivateSettings


class _FencedAuthority:
    """Trusted local write boundary; no shared callback or arbitrary executor."""
    def __init__(self, commit, state, checker, commit_binding):
        self.commit,self.state,self.checker,self.commit_binding = commit,state,checker,commit_binding
    def read(self):return self.commit.ctx.leadership.backend.read()
    def compare_replace(self, snapshot, desired):
        fresh,_ = self.commit._before(self.state,self.checker,commit_binding=self.commit_binding)
        if fresh.revision != snapshot.revision or fresh.raw != snapshot.raw:return WriteResult.REJECTED
        return self.commit.ctx.leadership.backend.compare_replace(snapshot,desired)


class ConfigurationCommit:
    def __init__(self, context):
        require(type(context) is CommitContext and type(context.candidate) is PostRootCandidate
                and type(context.store) is PrivateSettings, "COMMIT_CONTEXT")
        self.context,self.candidate = context,context.candidate
        self.ctx = self.candidate.context.rebind.ctx
        self._bindings()

    def _bindings(self, commit_binding=None):
        # The caller can supply only the actual already-held native port's
        # identity. Never reacquire this same store's non-reentrant lock.
        require(commit_binding is None or hex64(commit_binding), "COMMIT_BINDING")
        values = {**self.candidate._bindings(),"commit":native_binding(self.context.store) if commit_binding is None else commit_binding}
        require(len(set(values.values())) == len(values), "COMMIT_STORE_ALIAS")
        return values

    def _schema(self, value, *, commit_binding=None):
        require(type(value) is dict and set(value) == STATE_FIELDS
                and type(value["schema_version"]) is int and value["schema_version"] == 1
                and value["kind"] == "RECONFIGURATION_CONFIGURATION_COMMIT"
                and value["installation_id"] == self.candidate.original.installation_id
                and all(hex64(value[k]) for k in ("transition_id","base_sha256","stage_sha256","stage_state_sha256"))
                and all(type(value[k]) is int and 1 <= value[k] <= MAX_GENERATION for k in ("base_revision","stage_revision"))
                and value["authority"] == asdict(self.ctx.leadership.backend.binding)
                and value["bindings"] == self._bindings(commit_binding) and type(value["dispatch"]) is str
                and value["dispatch"] in {"PREPARED","INVOKING","CONFIRMED"}, "COMMIT_SCHEMA")
        validate_pin(value["pin"])
        plan = ConfigurationMutation.restore(value["plan"],self.ctx.leadership.backend.binding)
        _,before,after,_ = plan._validate()
        require(before["configuration"]["transition_id"] == value["transition_id"]
                and plan.owner.owner == value["installation_id"] and after["pin"] == value["pin"]
                and len(encoded(value)) <= 256*1024, "COMMIT_SCHEMA")
        return copy.deepcopy(value)

    def _state(self):
        current = self.context.store.read()
        return (None,0) if current is None else (self._schema(current.payload),current.revision)

    def _save(self, state, revision):
        self.context.store.save(self._schema(state),expected_revision=revision)
        require(self._state() == (state,revision+1), "COMMIT_UNCONFIRMED")

    def _source(self, state):
        pin = self.candidate.context.rebind.maintenance._proof()
        require(pin_record(pin) == state["pin"]
                and hashlib.sha256(pin.read(SCHEMA)).hexdigest() == SCHEMA_SHA256, "COMMIT_INSTRUCTIONS")
        return pin

    def _profile_evidence(self, state):
        """Read-only exact protected evidence; works after the shared commit."""
        stage = self.candidate.context.profile.read();archive = self.candidate.context.archive.read()
        transaction = self.candidate.context.transaction.read()
        require(stage is not None and stage.revision == state["stage_revision"] and sha(stage.payload) == state["stage_sha256"]
                and transaction is not None and sha(transaction.payload) == state["stage_state_sha256"]
                and archive is not None and archive.revision == 1 and archive.previous is None
                and archive.payload["base_setup_revision"] == state["base_revision"]
                and archive.payload["base_setup_sha256"] == state["base_sha256"]
                and sha(archive.payload["profile"]) == state["base_sha256"]
                and archive.payload["transition_id"] == state["transition_id"], "COMMIT_PROFILE_CHANGED")
        value,base = validated(stage.payload),validated(archive.payload["profile"])
        plan = ConfigurationMutation.restore(state["plan"],self.ctx.leadership.backend.binding)
        _,before,after,_ = plan._validate()
        require(all(value[k] == base[k] for k in ("installation_id","setup_nonce","operations"))
                and value["choices"]["storage"] == before["storage"]
                and catalogue(value["choices"]["descriptor"]) == after["descriptor"]
                and sha(value["choices"]["descriptor"]) == after["decision"]["candidate_digest"]
                and value["choices"]["timing"] == after["timing"], "COMMIT_PROFILE_CHANGED")
        return value,plan

    def _before(self, state, checker, *, commit_binding=None):
        self._schema(state,commit_binding=commit_binding);self._source(state)
        staged,_ = self.candidate._state();self.candidate._proof(staged)
        value,plan = self._profile_evidence(state)
        proof = PostRootValidation(staged["transition_id"],staged["configuration_revision"],staged["epoch"],
            state["stage_revision"],state["stage_sha256"],copy.deepcopy(staged["storage"]),None,self.candidate)
        self.candidate.require_current(proof,checker)
        self.candidate.original._fresh()
        require(self.candidate.original.snapshot.revision == state["base_revision"]
                and sha(self.candidate.original._payload) == state["base_sha256"], "COMMIT_PROFILE_CHANGED")
        snapshot,cp,pin = self.candidate._proof(staged)
        require(cp.grant.owner == plan.owner.owner and cp.grant.epoch == plan.owner.epoch
                and pin_record(pin) == state["pin"] and plan.evaluate(snapshot)[0] == "READY", "COMMIT_CHANGED")
        self._profile_evidence(state)
        return snapshot,plan

    def begin(self, checker, *, owner_authorized=False, decided_at):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        require(type(decided_at) is int and 0 <= decided_at <= 10**12 and self._state()[0] is None, "COMMIT_EXISTS")
        staged,_ = self.candidate._state();snapshot,cp,pin = self.candidate._proof(staged)
        local = copy.deepcopy(self.candidate._setup(staged)._payload["choices"]["descriptor"])
        local["revision"] = shared(snapshot.document())["revision"]+1
        self.candidate.choose({"descriptor":local},owner_authorized=True)
        proof = self.candidate.require_validated(checker)
        staged,_ = self.candidate._state();snapshot,cp,pin = self.candidate._proof(staged)
        model = self.candidate._setup(staged);choices = model.private_choices()
        decision = dict(kind="LOCAL_OWNER_CONFIRMATION",at=decided_at,candidate_digest=sha(choices["descriptor"]))
        decision["id"] = digest(["reconfiguration-commit",staged["transition_id"],decision["candidate_digest"],
            digest(pin_record(pin)),cp.grant.owner,cp.grant.epoch,decided_at])
        plan = ConfigurationMutation.prepare(snapshot,OwnerGuard(cp.grant.owner,cp.grant.epoch),
            storage=proof.storage,descriptor=choices["descriptor"],timing=choices["timing"],pin=pin_record(pin),decision=decision)
        state = dict(schema_version=1,kind="RECONFIGURATION_CONFIGURATION_COMMIT",installation_id=model.installation_id,
            transition_id=staged["transition_id"],base_revision=staged["base_setup_revision"],base_sha256=staged["base_setup_sha256"],
            stage_revision=proof.revision,stage_sha256=proof.setup_sha256,stage_state_sha256=sha(staged),
            authority=asdict(snapshot.binding),pin=pin_record(pin),bindings=self._bindings(),dispatch="PREPARED",plan=frozen_plan(plan))
        self._before(state,checker);self._save(state,0)
        return "PREPARED"

    def advance(self, checker, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        state,revision = self._state();require(state is not None, "COMMIT_NOT_STARTED")
        if state["dispatch"] != "PREPARED":return self.inspect()
        self._before(state,checker)
        with self.context.store.native.locked() as port:
            saved = self.context.store._decode(port.read("settings.json"),port.binding)
            require(port.read("settings.pending") is None and saved.payload == state and saved.revision == revision
                    and sha(port.binding) == state["bindings"]["commit"], "COMMIT_CHANGED")
            _,plan = self._before(state,checker,commit_binding=sha(port.binding))
            invoking = {**state,"dispatch":"INVOKING"}
            result = self.context.store._save_locked(port,invoking,expected_revision=revision)
            require(result.payload == invoking, "COMMIT_UNCONFIRMED")
            report = reconcile(_FencedAuthority(self,state,checker,sha(port.binding)),plan,mode="START",max_reads=4,max_writes=2)
        return self.inspect() if report.outcome == "CONFIRMED" else report.outcome

    def inspect(self):
        state,revision = self._state();require(state is not None, "COMMIT_NOT_STARTED")
        self._source(state);_,plan = self._profile_evidence(state)
        snapshot = self.ctx.leadership.backend.read()
        if state["dispatch"] == "PREPARED":return "PREPARED"
        if plan.evaluate(snapshot)[0] != "CONFIRMED":return "UNKNOWN"
        _,before,_,_ = plan._validate();spec,_ = storage_spec(before["storage"])
        port = NativeCommissioning(self.ctx.storage_port.drive,self.ctx.storage_port.docs,spec,llm_authorized=True,
            root_transition=before["storage"]["root_transition"])
        CommissionedStorage(port).verify(before["storage"])
        self._source(state);self._profile_evidence(state)
        require(plan.evaluate(self.ctx.leadership.backend.read())[0] == "CONFIRMED", "COMMIT_CHANGED")
        if state["dispatch"] != "CONFIRMED":self._save({**state,"dispatch":"CONFIRMED"},revision)
        return "PUBLISHED"

    def recover_local(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        store = self.context.store
        with store.native.locked() as port:
            pending,raw = port.read("settings.pending"),port.read("settings.json")
            if pending is None:return "NO_PENDING"
            candidate = store._decode(pending,port.binding);current = None if raw is None else store._decode(raw,port.binding)
            require(candidate.revision == (0 if current is None else current.revision)+1
                    and candidate.previous == (None if current is None else current.payload), "COMMIT_RECOVERY")
            state = self._schema(candidate.payload,commit_binding=sha(port.binding))
        self._source(state);_,plan = self._profile_evidence(state)
        require(plan.evaluate(self.ctx.leadership.backend.read())[0] in {"READY","CONFIRMED","SUPERSEDED"}, "COMMIT_RECOVERY")
        with store.native.locked() as port:
            require(port.read("settings.pending") == pending and port.read("settings.json") == raw, "COMMIT_RECOVERY")
            port.promote();require(port.read("settings.json") == pending, "COMMIT_UNCONFIRMED")
        return "INSPECT_REQUIRED"
