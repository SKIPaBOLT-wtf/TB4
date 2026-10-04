"""Full protected own-profile promotion after retained-authority publication."""
from dataclasses import dataclass
import copy

from .ballpark_setup import validate_pin
from .configuration_contract import configuration,require
from .drive.leadership import ClockSample,Grant
from .exchange_layout import MAX_GENERATION,encoded
from .private_settings import PrivateSettings
from .reconfiguration_candidate import native_binding
from .reconfiguration_maintenance import hex64,sha
from .reconfiguration_promotion import ProfilePromotion,STATE_FIELDS
from .reconfiguration_retained import RetainedConfigurationCommit
from .watchdog.leadership_runtime import Action,Capabilities

SCHEMA_DEFINITION="retainedProfilePromotion"


@dataclass(frozen=True,repr=False)
class RetainedPromotionContext:
    commit: RetainedConfigurationCommit
    store: PrivateSettings


class RetainedProfilePromotion(ProfilePromotion):
    def __init__(self,context):
        require(type(context) is RetainedPromotionContext and type(context.commit) is RetainedConfigurationCommit
            and type(context.store) is PrivateSettings,"PROMOTION_CONTEXT")
        self.context,self.commit=context,context.commit
        self.original=self.commit.candidate.original
        self._bindings()

    def _schema(self,value,*,promotion_binding=None):
        require(type(value) is dict and set(value)==STATE_FIELDS
                and type(value["schema_version"]) is int and value["schema_version"]==1
                and value["kind"]=="RECONFIGURATION_RETAINED_PROMOTION"
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

    def _checker(self,checker,cstate):
        staged=self.commit.candidate.context.transaction.read()
        require(staged is not None and sha(staged.payload)==cstate["stage_state_sha256"],"PROMOTION_CHANGED")
        return self.commit._checker(checker,cstate)

    def _role(self,state):
        ctx=self.commit.ctx
        cp=ctx.checkpoint.read();caps=ctx.capabilities();sample=ctx.clock()
        require(cp.election is None and type(cp.grant) is Grant
            and cp.grant.owner==state["installation_id"] and cp.maintenance==state["transition_id"],
            "PROMOTION_ROLE")
        require(type(caps) is Capabilities and caps.installation_id==state["installation_id"]
            and caps.observe is True and caps.coordinate is True and type(caps.actions) is frozenset
            and all(type(a) is Action for a in caps.actions) and Action.IDENTITY in caps.actions,
            "PROMOTION_CAPABILITIES")
        require(type(sample) is ClockSample and sample.wall_trusted and sample.monotonic_trusted,"PROMOTION_CLOCK")
        observed=ctx.leadership.observe(sample)
        require(ctx.leadership._owns(observed.leader,observed.request,cp.grant),"OWNER_SUPERSEDED")
        config=configuration(observed.snapshot.document())
        require(config is not None and config["phase"]=="ACTIVE"
            and config["transition_id"]==state["transition_id"] and config["revision"]==state["configuration_revision"],
            "PROMOTION_CHANGED")
        return cp

    def _proof(self,state,checker,*,promotion_binding=None,original_snapshot=None):
        before=self._role(state)
        result=super()._proof(state,checker,promotion_binding=promotion_binding,original_snapshot=original_snapshot)
        require(self._role(state)==before,"PROMOTION_CHANGED")
        return result

    def begin(self,checker,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        require(self._state()[0] is None,"PROMOTION_EXISTS")
        require(self.commit.inspect()=="PUBLISHED","PROMOTION_PUBLICATION_REQUIRED")
        cstate,plan,payload=self._committed()
        config=configuration(self.commit.ctx.leadership.backend.read().document())
        state=dict(schema_version=1,kind="RECONFIGURATION_RETAINED_PROMOTION",installation_id=self.original.installation_id,
            transition_id=cstate["transition_id"],configuration_revision=config["revision"],base_revision=cstate["base_revision"],
            base_sha256=cstate["base_sha256"],stage_revision=cstate["stage_revision"],stage_sha256=cstate["stage_sha256"],
            commit_sha256=sha(cstate),promoted_sha256=sha(payload),pin=cstate["pin"],bindings=self._bindings(),phase="PREPARED")
        payload,status=self._proof(state,checker)
        require(status=="ORIGINAL","PROMOTION_INSPECT_REQUIRED")
        self._budget(payload,self.original.store.read().payload,state["base_revision"])
        self._save(state,0)
        return "PREPARED"

