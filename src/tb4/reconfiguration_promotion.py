"""Exact protected profile promotion after verified shared publication.

The saved profile remains INCOMPLETE. This never activates runtime, clears its
maintenance reservation, replays work or replaces a remote authority.
"""
from dataclasses import dataclass
import copy

from .ballpark_records import receipt
from .ballpark_setup import pin_record,validate_pin
from .commissioning_state import Setup,validated
from .configuration_contract import configuration,require
from .exchange_layout import MAX_GENERATION,encoded
from .private_settings import PrivateSettings,MAX_BYTES
from .reconfiguration_candidate import native_binding,DERIVED
from .reconfiguration_commit import ConfigurationCommit,ConfigurationMutation,SCHEMA,SCHEMA_SHA256
from .reconfiguration_maintenance import hex64,sha

SCHEMA_DEFINITION="profilePromotion"
STATE_FIELDS=frozenset({"schema_version","kind","installation_id","transition_id","configuration_revision",
    "base_revision","base_sha256","stage_revision","stage_sha256","commit_sha256","promoted_sha256",
    "pin","bindings","phase"})


@dataclass(frozen=True,repr=False)
class PromotionContext:
    commit: ConfigurationCommit
    store: PrivateSettings


class ProfilePromotion:
    def __init__(self,context):
        require(type(context) is PromotionContext and type(context.commit) is ConfigurationCommit
                and type(context.store) is PrivateSettings,"PROMOTION_CONTEXT")
        self.context,self.commit=context,context.commit
        self.original=self.commit.candidate.original
        self._bindings()

    def _bindings(self,promotion_binding=None):
        require(promotion_binding is None or hex64(promotion_binding),"PROMOTION_BINDING")
        result={**self.commit._bindings(),"promotion":native_binding(self.context.store) if promotion_binding is None else promotion_binding}
        require(len(set(result.values()))==len(result),"PROMOTION_STORE_ALIAS")
        return result

    def _schema(self,value,*,promotion_binding=None):
        require(type(value) is dict and set(value)==STATE_FIELDS
                and type(value["schema_version"]) is int and value["schema_version"]==1
                and value["kind"]=="RECONFIGURATION_PROFILE_PROMOTION"
                and value["installation_id"]==self.original.installation_id
                and all(hex64(value[k]) for k in ("transition_id","base_sha256","stage_sha256","commit_sha256","promoted_sha256"))
                and all(type(value[k]) is int and 1<=value[k]<=MAX_GENERATION for k in (
                    "configuration_revision","base_revision","stage_revision"))
                and value["base_revision"]<MAX_GENERATION
                and value["bindings"]==self._bindings(promotion_binding)
                and type(value["phase"]) is str and value["phase"] in {"PREPARED","PROMOTED"},"PROMOTION_SCHEMA")
        validate_pin(value["pin"])
        require(len(encoded(value))<=64*1024,"PROMOTION_SIZE")
        return copy.deepcopy(value)

    def _state(self):
        current=self.context.store.read()
        return (None,0) if current is None else (self._schema(current.payload),current.revision)

    def _save(self,value,revision):
        self.context.store.save(self._schema(value),expected_revision=revision)
        require(self._state()==(value,revision+1),"PROMOTION_UNCONFIRMED")

    def _committed(self):
        state,_=self.commit._state()
        require(state is not None and state["dispatch"]=="CONFIRMED","PROMOTION_PUBLICATION_REQUIRED")
        self.commit._source(state)
        staged,plan=self.commit._profile_evidence(state)
        require(plan.evaluate(self.commit.ctx.leadership.backend.read())[0]=="CONFIRMED","PROMOTION_PUBLICATION_REQUIRED")
        _,_,after,_=plan._validate()
        value=copy.deepcopy(staged)
        # All obsolete domain/root/lease/discovery/enrollment caches are absent
        # from the qualified seed. Rebuild only this exact publication receipt.
        require(not set(value)&DERIVED,"PROMOTION_PROFILE")
        draft=dict(candidate=value["choices"]["descriptor"],pin=after["pin"],decision=after["decision"])
        value["ballpark_publication"]=dict(active=receipt(draft,value["choices"]["timing"]),pending=None)
        value.update(state="INCOMPLETE",reason="REVALIDATION_REQUIRED")
        return state,plan,validated(value)

    def _checker(self,checker,cstate):
        # Use exactly the actual qualified SDK/source/runtime first-run adapter,
        # after ACTIVE, without invoking the obsolete maintenance proof.
        staged=self.commit.candidate.context.transaction.read()
        require(staged is not None and sha(staged.payload)==cstate["stage_state_sha256"],"PROMOTION_CHANGED")
        return self.commit.candidate._checker(checker,staged.payload)

    def _main(self,state,payload,snapshot):
        require(snapshot is not None,"PROMOTION_PROFILE")
        archive=self.commit.candidate.context.archive.read()
        require(archive is not None,"PROMOTION_PROFILE")
        base=validated(archive.payload["profile"])
        if snapshot.revision==state["base_revision"] and sha(snapshot.payload)==state["base_sha256"]:
            require(snapshot.payload==base,"PROMOTION_PROFILE")
            return "ORIGINAL"
        require(snapshot.revision==state["base_revision"]+1 and snapshot.payload==payload
                and snapshot.previous==base,"PROMOTION_PROFILE_CHANGED")
        return "PROMOTED"

    def _proof(self,state,checker,*,promotion_binding=None,original_snapshot=None):
        self._schema(state,promotion_binding=promotion_binding)
        cstate,plan,payload=self._committed()
        require(sha(cstate)==state["commit_sha256"] and cstate["transition_id"]==state["transition_id"]
                and cstate["base_revision"]==state["base_revision"] and cstate["base_sha256"]==state["base_sha256"]
                and cstate["stage_revision"]==state["stage_revision"] and cstate["stage_sha256"]==state["stage_sha256"]
                and cstate["pin"]==state["pin"] and sha(payload)==state["promoted_sha256"],"PROMOTION_CHANGED")
        snapshot=self.original.store.read() if original_snapshot is None else original_snapshot
        status=self._main(state,payload,snapshot)
        stage=self.commit.candidate.context.profile.read()
        validation=self._checker(checker,cstate).validate(copy.deepcopy(stage.payload))
        require(pin_record(validation.pin)==state["pin"],"PROMOTION_PIN_CHANGED")
        # Probe callbacks/source/remote changes cannot leave a stale proof.
        fresh,new_plan,new_payload=self._committed()
        require(fresh==cstate and new_payload==payload
                and new_plan.evaluate(self.commit.ctx.leadership.backend.read())[0]=="CONFIRMED"
                and configuration(self.commit.ctx.leadership.backend.read().document())["revision"]==state["configuration_revision"],
                "PROMOTION_CHANGED")
        if original_snapshot is None:
            require(self.original.store.read()==snapshot,"PROMOTION_PROFILE_CHANGED")
        return payload,status

    def _budget(self,payload,base,revision):
        # Exactly the standard native frame layout; no previous-profile pruning.
        with self.original.store.native.locked() as port:
            frame=dict(schema_version=1,binding=port.binding,revision=revision+1,
                payload=payload,previous=base,digest="0"*64)
            require(len(encoded(frame))<=MAX_BYTES,"PROMOTION_NATIVE_SIZE")

    def begin(self,checker,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        require(self._state()[0] is None,"PROMOTION_EXISTS")
        require(self.commit.inspect()=="PUBLISHED","PROMOTION_PUBLICATION_REQUIRED")
        cstate,plan,payload=self._committed()
        config=configuration(self.commit.ctx.leadership.backend.read().document())
        state=dict(schema_version=1,kind="RECONFIGURATION_PROFILE_PROMOTION",installation_id=self.original.installation_id,
            transition_id=cstate["transition_id"],configuration_revision=config["revision"],base_revision=cstate["base_revision"],
            base_sha256=cstate["base_sha256"],stage_revision=cstate["stage_revision"],stage_sha256=cstate["stage_sha256"],
            commit_sha256=sha(cstate),promoted_sha256=sha(payload),pin=cstate["pin"],bindings=self._bindings(),phase="PREPARED")
        payload,status=self._proof(state,checker)
        require(status=="ORIGINAL","PROMOTION_INSPECT_REQUIRED")
        self._budget(payload,self.original.store.read().payload,state["base_revision"])
        self._save(state,0)
        return "PREPARED"

    def advance(self,checker,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        state,revision=self._state();require(state is not None,"PROMOTION_NOT_STARTED")
        if state["phase"]=="PROMOTED":return self.inspect(checker)
        self._proof(state,checker)
        with self.context.store.native.locked() as port:
            saved=self.context.store._decode(port.read("settings.json"),port.binding)
            require(port.read("settings.pending") is None and saved.payload==state and saved.revision==revision
                    and sha(port.binding)==state["bindings"]["promotion"],"PROMOTION_CHANGED")
            payload,status=self._proof(state,checker,promotion_binding=sha(port.binding))
            if status=="ORIGINAL":
                self._budget(payload,self.original.store.read().payload,state["base_revision"])
                self.original.store.save(payload,expected_revision=state["base_revision"])
            require(self._proof(state,checker,promotion_binding=sha(port.binding))[1]=="PROMOTED","PROMOTION_UNCONFIRMED")
            promoted={**state,"phase":"PROMOTED"}
            require(self.context.store._save_locked(port,promoted,expected_revision=revision).payload==promoted,"PROMOTION_UNCONFIRMED")
        return self.inspect(checker)

    def inspect(self,checker):
        state,revision=self._state();require(state is not None,"PROMOTION_NOT_STARTED")
        _,status=self._proof(state,checker)
        if status=="ORIGINAL":return "PREPARED"
        if state["phase"]!="PROMOTED":self._save({**state,"phase":"PROMOTED"},revision)
        return "PROFILE_PROMOTED"

    def recover_original(self,checker,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        state,_=self._state();require(state is not None,"PROMOTION_NOT_STARTED")
        store=self.original.store
        with store.native.locked() as port:
            pending,raw=port.read("settings.pending"),port.read("settings.json")
            if pending is None:return "NO_PENDING"
            candidate=store._decode(pending,port.binding);current=None if raw is None else store._decode(raw,port.binding)
            require(current is not None and candidate.revision==current.revision+1
                    and candidate.previous==current.payload,"PROMOTION_RECOVERY")
        payload,status=self._proof(state,checker,original_snapshot=current)
        require(status=="ORIGINAL" and candidate.revision==state["base_revision"]+1
                and candidate.payload==payload,"PROMOTION_RECOVERY")
        with store.native.locked() as port:
            require(port.read("settings.pending")==pending and port.read("settings.json")==raw,"PROMOTION_RECOVERY")
            port.promote();require(port.read("settings.json")==pending,"PROMOTION_UNCONFIRMED")
        return "INSPECT_REQUIRED"

    def recover_local(self,checker,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        store=self.context.store
        with store.native.locked() as port:
            pending,raw=port.read("settings.pending"),port.read("settings.json")
            if pending is None:return "NO_PENDING"
            candidate=store._decode(pending,port.binding);current=None if raw is None else store._decode(raw,port.binding)
            require(candidate.revision==(0 if current is None else current.revision)+1
                    and candidate.previous==(None if current is None else current.payload),"PROMOTION_RECOVERY")
            state=self._schema(candidate.payload,promotion_binding=sha(port.binding))
        _,status=self._proof(state,checker)
        require(state["phase"]=="PREPARED" or status=="PROMOTED","PROMOTION_RECOVERY")
        with store.native.locked() as port:
            require(port.read("settings.pending")==pending and port.read("settings.json")==raw,"PROMOTION_RECOVERY")
            port.promote();require(port.read("settings.json")==pending,"PROMOTION_UNCONFIRMED")
        return "INSPECT_REQUIRED"

    def view(self):
        state,_=self._state()
        return dict(phase="NOT_STARTED" if state is None else state["phase"],runtime_active=False,automatic_replay=False)
