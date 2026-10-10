"""Fresh exact partial-root facts from the one existing authority, never READY."""
from dataclasses import dataclass,replace

from .configuration_contract import require
from .drive.commissioning import RAW_LIMIT,digest
from .drive.commissioning_bootstrap import AuthorityHandle
from .drive.commissioning_native import NativeCommissioning
from .exchange_layout import encoded
from .reconfiguration_effects import SLOT,ledger
from .reconfiguration_inspection import inspect
from .reconfiguration_root_plan import references,matches_plan,stable_records
from .reconfiguration_root_settlement import InheritedRootSettlement


@dataclass(frozen=True,repr=False)
class PartialRootFacts:
    transition_id: str
    target_root: str
    owner: str
    epoch: int
    profile_revision: int
    profile_sha256: str
    plan: bytes
    objects: bytes
    snapshot: object
    inspection: object
    _origin: object

    def public_summary(self):
        import json
        rows = json.loads(self.objects)
        return dict(schema_version=1,moved=sum(r["state"] == "AFTER" for r in rows),
                    remaining=sum(r["state"] == "BEFORE" for r in rows),
                    requires_resolution=bool(self.inspection.blockers),execution_authorized=False)


class PartialRootInspection:
    def __init__(self,context):
        self.current = InheritedRootSettlement(context)
        self.context = context

    def inspect(self):
        ctx = self.context
        snapshot,checkpoint,config,handle,_ = self.current._role(reserved=False)
        doc = snapshot.document(); plan = ledger(doc["records"][SLOT]).get("root_plan")
        require(plan is not None and plan["transition_id"] == config["transition_id"]
                and matches_plan(doc,snapshot.binding,plan), "CONFIGURATION_ROOT_PLAN_CHANGED")
        spec,refs = references(doc,snapshot.binding)
        require(spec == ctx.storage_port.spec and handle.seal == refs[-1]["seal"],
                "CONFIGURATION_ROOT_BINDING")
        profile_revision = ctx.setup.snapshot.revision; profile_sha = digest(ctx.setup._payload)
        old = ctx.storage_port
        new = NativeCommissioning(old.drive,old.docs,replace(spec,root_id=plan["target_root"]),
            llm_authorized=True,root_transition=config["transition_id"])
        old.check_root(); new.check_root()
        rows = []
        for item in refs:
            metadata = old._metadata(item["id"],missing_ok=True)
            require(type(metadata) is dict, "CONFIGURATION_ROOT_BINDING")
            matched = []
            for port,state in ((old,"BEFORE"),(new,"AFTER")):
                try:
                    port._verify(metadata,item["key"],item["id"])
                    if item["key"] == "authority":
                        seal = digest([port.mode,port.root_id,spec.domain_id,item["id"],handle.tab_id])
                        bound = AuthorityHandle(item["id"],seal,handle.tab_id)
                        require(port.inspect_authority(port.spec,bound) == bound
                                and port.authority(bound).binding == snapshot.binding,"CONFIGURATION_ROOT_BINDING")
                        size = None
                    else:
                        size = int(metadata["size"])
                        require(0 <= size <= RAW_LIMIT,"CONFIGURATION_ROOT_CONTENT_CHANGED")
                    matched.append((state,size))
                except Exception:
                    pass
            require(len(matched) == 1,"CONFIGURATION_ROOT_BINDING")
            state,size = matched[0]
            after_seal = digest([new.mode,new.root_id,spec.domain_id,item["id"],
                                 handle.tab_id if item["key"] == "authority" else new.spec.operation(item["key"])])
            rows.append(dict(key=item["key"],id=item["id"],size=size,before_seal=item["seal"],
                             after_seal=after_seal,state=state))
        fresh,cp,fresh_config,_,_ = self.current._role(reserved=False)
        require(fresh_config == config and ledger(fresh.document()["records"][SLOT]).get("root_plan") == plan
                and matches_plan(fresh.document(),fresh.binding,plan)
                and ctx.setup.snapshot.revision == profile_revision and digest(ctx.setup._payload) == profile_sha,
                "CONFIGURATION_ROOT_CHANGED")
        facts = inspect(fresh,setup_payload=ctx.setup._payload,checkpoint=cp)
        return PartialRootFacts(config["transition_id"],plan["target_root"],cp.grant.owner,cp.grant.epoch,
            profile_revision,profile_sha,encoded(plan),encoded(rows),fresh,facts,self)

    def require_fresh(self,proof):
        require(type(proof) is PartialRootFacts and proof._origin is self,"CONFIGURATION_ROOT_EVIDENCE")
        fresh = self.inspect()
        require((fresh.transition_id,fresh.target_root,fresh.owner,fresh.epoch,fresh.profile_revision,
                 fresh.profile_sha256,fresh.plan,fresh.objects,fresh.inspection.setup_sha256)
                == (proof.transition_id,proof.target_root,proof.owner,proof.epoch,proof.profile_revision,
                    proof.profile_sha256,proof.plan,proof.objects,proof.inspection.setup_sha256)
                and fresh.inspection.blockers == proof.inspection.blockers
                and stable_records(fresh.snapshot.document()) == stable_records(proof.snapshot.document()),
                "CONFIGURATION_ROOT_CHANGED")
        return fresh
