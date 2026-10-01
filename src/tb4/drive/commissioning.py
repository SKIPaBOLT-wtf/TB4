"""Unreleased fixed-slot commissioning over the one accepted authority.

The caller holds a qualified private setup journal lock and supplies an actual
RP016 grant. Bootstrap before an authority exists is a separate one-actor path.
No normal runtime should receive the allocation port exposed here.
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
import hashlib
import json
import re
from uuid import UUID

from tb4.exchange_layout import Capacity, empty_document, empty_record, encoded, validate_document
from .authority_transaction import OwnerGuard, RecordMutation, reconcile
from .docs_authority import AuthorityError, document_bytes, require
from .leadership import ClockSample, Grant, Leadership

COMMISSIONING = "global.commissioning"
RAW_LIMIT = 8 * 1024 * 1024
MODES = {"NATIVE_DOCS", "FOLDER_SQLITE_V1"}


def digest(value): return hashlib.sha256(encoded(value)).hexdigest()


def object_id(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is not None


def uuid(value):
    try: return type(value) is str and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError): return False


@dataclass(frozen=True, repr=False)
class SetupSpec:
    root_id: str
    domain_id: str
    setup_id: str
    bootstrap_actor: str
    mode: str
    capacity: Capacity

    def __post_init__(self):
        require(object_id(self.root_id) and uuid(self.domain_id) and uuid(self.bootstrap_actor)
                and type(self.setup_id) is str and re.fullmatch("[a-f0-9]{64}", self.setup_id)
                and type(self.mode) is str and self.mode in MODES
                and type(self.capacity) is Capacity, "SETUP_SPEC")

    @property
    def fingerprint(self): return digest(asdict(self))

    @property
    def artifact_keys(self):
        return tuple(f"artifact.{i:03d}.{kind}" for i in range(self.capacity.devices)
                     for kind in ("input", "output"))

    def operation(self, key): return digest([self.fingerprint, key])

    def marker(self, state):
        return dict(schema_version=1, setup_id=self.setup_id, root_id=self.root_id,
                    blueprint_sha256=self.fingerprint, mode=self.mode,
                    bootstrap_actor=self.bootstrap_actor, state=state)


def seed_document(spec, computer_name, clock):
    """Prepare bytes once, before the bootstrap write-ahead checkpoint."""
    require(type(spec) is SetupSpec and type(computer_name) is str and 1 <= len(computer_name) <= 128
            and isinstance(clock, ClockSample), "SETUP_SEED")
    document = empty_document(spec.domain_id, spec.capacity)
    op = spec.operation("authority")
    document["records"]["global.leadership"] = dict(generation=1, operation_id=op, retention="BUSY",
        body=dict(owner=spec.bootstrap_actor, computer_name=computer_name, epoch=1, phase="ACTIVE",
                  heartbeat_at=clock.utc if clock.wall_trusted else None, heartbeat_sequence=0,
                  acquisition_id=op, transition_id=op))
    document["records"][COMMISSIONING] = dict(generation=0, operation_id=spec.setup_id,
                                             retention="RETAINED", body=spec.marker("PREPARING"))
    # Descriptor capacity exists; real BALLPARK collection/publication is RP022+.
    document["records"]["global.settings"] = dict(generation=0, operation_id=spec.setup_id,
        retention="RETAINED", body={"descriptor_state":"UNCONFIGURED"})
    validate_document(document)
    return document_bytes(document)


@dataclass(frozen=True, repr=False)
class Allocation:
    object_id: str
    operation_id: str
    max_bytes: int = RAW_LIMIT
    seal: str | None = None

    def __post_init__(self):
        require(object_id(self.object_id) and type(self.operation_id) is str
                and re.fullmatch("[a-f0-9]{64}",self.operation_id)
                and type(self.max_bytes) is int and self.max_bytes == RAW_LIMIT
                and (self.seal is None or type(self.seal) is str
                     and re.fullmatch("[a-f0-9]{64}",self.seal)), "ALLOCATION")


def frozen_plan(plan):
    return dict(owner=plan.owner.owner, epoch=plan.owner.epoch,
                **{key:base64.b64encode(getattr(plan,key)).decode("ascii")
                   for key in ("header","protected","before","after")})


def restored_plan(value, binding):
    require(type(value) is dict and set(value)=={"owner","epoch","header","protected","before","after"},
            "SETUP_PENDING")
    try:
        raw = {key:base64.b64decode(value[key],validate=True)
               for key in ("header","protected","before","after")}
        require(all(len(v)<=512*1024 for v in raw.values()), "SETUP_PENDING")
        return RecordMutation(binding,OwnerGuard(value["owner"],value["epoch"]),**raw)
    except (ValueError,TypeError):
        raise AuthorityError("SETUP_PENDING") from None


class Commissioner:
    """One bounded advance under an exclusive private journal and current grant.

    shared UNKNOWN rows survive owner/process loss. Only the same live call that
    confirmed a newly prepared creation intent may dispatch that create. A
    restarted caller inspects the exact allocated ID and never repeats creation.
    """
    def __init__(self, spec, leadership, grant, allocation_port, journal):
        require(type(spec) is SetupSpec and isinstance(leadership,Leadership)
                and isinstance(grant,Grant) and grant.owner==leadership.actor, "SETUP_CONTEXT")
        require(getattr(allocation_port,"root_id",None)==spec.root_id
                and getattr(allocation_port,"mode",None)==spec.mode
                and getattr(allocation_port,"llm_authorized",None) is True, "SETUP_ACCESS")
        self.spec,self.leader,self.grant,self.port,self.journal=spec,leadership,grant,allocation_port,journal

    def _state(self):
        require(getattr(self.journal,"installation_id",None)==self.leader.actor
                and getattr(self.journal,"setup_id",None)==self.spec.setup_id
                and getattr(self.journal,"protected",None) is True
                and getattr(self.journal,"locked",None) is True, "SETUP_JOURNAL")
        state=self.journal.read()
        if state is None:
            state={"spec":self.spec.fingerprint,"pending":None}
            self._save(state)
        require(type(state) is dict and set(state)=={"spec","pending"}
                and state["spec"]==self.spec.fingerprint, "SETUP_JOURNAL")
        return state

    def _save(self,state):
        self.journal.save(state)
        require(encoded(self.journal.read())==encoded(state), "SETUP_JOURNAL_READBACK")

    def _commit(self,plan,state):
        state={**state,"pending":frozen_plan(plan)}
        self._save(state)  # Fail before any possibly mutating call.
        report=reconcile(self.leader.backend,plan,mode="START")
        if report.outcome in {"CONFIRMED","SUPERSEDED","CONFLICT","REJECTED"}:
            self._save({**state,"pending":None})
        return report.outcome

    def _document(self,snapshot):
        document=snapshot.document()
        require(document["domain_id"]==self.spec.domain_id
                and document["capacity"]==asdict(self.spec.capacity), "SETUP_BLUEPRINT")
        row=document["records"][COMMISSIONING]
        state=row["body"].get("state") if type(row["body"]) is dict else None
        require(row["operation_id"]==self.spec.setup_id and row["retention"]=="RETAINED"
                and row["generation"]==0 and state in {"PREPARING","STORAGE_READY"}
                and row["body"]==self.spec.marker(state), "SETUP_MARKER")
        return document,state

    def _current(self,clock):
        return self.leader.current_before_dispatch(self.grant,clock)

    def advance(self,clock):
        """No retry loop. Scheduler supplies fresh clock/lease renewal and pacing."""
        require(isinstance(clock,ClockSample),"CLOCK_SAMPLE")
        state=self._state()
        if state["pending"] is not None:
            plan=restored_plan(state["pending"],self.leader.backend.binding)
            report=reconcile(self.leader.backend,plan,mode="INSPECT")
            if report.outcome in {"CONFIRMED","SUPERSEDED","CONFLICT"}:
                self._save({**state,"pending":None})
            # Even confirmed intent is inspect-only after restart, never dispatch.
            return report.outcome
        if not self._current(clock): return "SUPERSEDED"
        self.port.check_root()
        snapshot=self.leader.backend.read()
        document,phase=self._document(snapshot)
        owner=OwnerGuard(self.grant.owner,self.grant.epoch)
        require(owner.matches(document), "OWNER_SUPERSEDED")
        rows=document["records"]
        if phase=="STORAGE_READY":
            self._verify_ready(rows)
            return "STORAGE_READY"
        for key in self.spec.artifact_keys:
            row=rows[key]
            op=self.spec.operation(key)
            if row["retention"]=="FREE":
                require(row==empty_record(), "SETUP_SLOT_CONFLICT")
                allocation=self.port.prepare(key,op)
                require(type(allocation) is Allocation and allocation.operation_id==op
                        and allocation.seal is None,"ALLOCATION")
                # IDs are reserved before the external mutation, in the authority.
                pending=dict(generation=0,operation_id=op,retention="UNKNOWN",
                    body=dict(object_id=allocation.object_id,max_bytes=RAW_LIMIT,phase="ALLOCATING",seal=None))
                plan=RecordMutation.prepare(snapshot,owner=owner,changes={key:pending},
                                            protect={COMMISSIONING})
                result=self._commit(plan,state)
                if result!="CONFIRMED":return result
                if not self._current(clock):return "SUPERSEDED"
                # A suspended old actor can have one admitted immutable create.
                # All owners inspect this same reserved ID; it cannot replace a
                # newer authority or reset another operation.
                try:self.port.create(key,allocation)
                except Exception:return "UNKNOWN"
                return "INSPECT_REQUIRED"
            self._allocation(row,key)
            if row["retention"]=="UNKNOWN":
                allocation=self._allocation(row,key)
                confirmed=self.port.inspect(key,allocation)
                if confirmed is None:return "UNKNOWN"
                require(type(confirmed) is Allocation and confirmed.object_id==allocation.object_id
                        and confirmed.operation_id==allocation.operation_id and confirmed.seal is not None,
                        "ALLOCATION_UNVERIFIED")
                ready={**row,"retention":"RETAINED","body":{**row["body"],"phase":"ALLOCATED",
                                                          "seal":confirmed.seal}}
                plan=RecordMutation.prepare(snapshot,owner=owner,changes={key:ready},
                                            protect={COMMISSIONING})
                return self._commit(plan,state)
        # All allocations confirmed; verify contents/identity again before a
        # single CAS publishes bindings and frees the initial payload descriptors.
        changes={COMMISSIONING:{**rows[COMMISSIONING],"body":self.spec.marker("STORAGE_READY")}}
        identities={getattr(self.leader.backend.binding,"document_id",None)}
        for index in range(self.spec.capacity.devices):
            refs={}
            for kind in ("input","output"):
                key=f"artifact.{index:03d}.{kind}"
                allocation=self._allocation(rows[key],key)
                require(allocation.object_id not in identities and self.port.inspect(key,allocation)==allocation,
                        "ALLOCATION_UNVERIFIED")
                identities.add(allocation.object_id)
                refs[kind]={"id":allocation.object_id,"seal":allocation.seal}
                changes[key]=empty_record()  # No command ever occupied these setup descriptors.
            catalogue=f"target.{index:03d}.catalogue"
            require(rows[catalogue]==empty_record(), "SETUP_CATALOGUE_CONFLICT")
            changes[catalogue]=dict(generation=0,operation_id=self.spec.setup_id,retention="RETAINED",
                                   body=dict(artifacts=refs,enrollment="UNENROLLED"))
        plan=RecordMutation.prepare(snapshot,owner=owner,changes=changes,protect=set())
        return self._commit(plan,state)

    def _allocation(self,row,key):
        require(row["generation"]==0 and row["operation_id"]==self.spec.operation(key)
                and row["retention"] in {"UNKNOWN","RETAINED"} and type(row["body"]) is dict
                and set(row["body"])=={"object_id","max_bytes","phase","seal"}
                and row["body"]["phase"]==("ALLOCATING" if row["retention"]=="UNKNOWN" else "ALLOCATED"),
                "SETUP_SLOT_CONFLICT")
        require((row["body"]["seal"] is None)==(row["retention"]=="UNKNOWN"),"SETUP_SLOT_CONFLICT")
        return Allocation(row["body"]["object_id"],row["operation_id"],row["body"]["max_bytes"],row["body"]["seal"])

    def _verify_ready(self,rows):
        identities={getattr(self.leader.backend.binding,"document_id",None)}
        for index in range(self.spec.capacity.devices):
            body=rows[f"target.{index:03d}.catalogue"]["body"]
            require(type(body) is dict and type(body.get("artifacts")) is dict
                    and set(body["artifacts"])=={"input","output"},"SETUP_BINDINGS")
            for kind,ref in body["artifacts"].items():
                key=f"artifact.{index:03d}.{kind}"
                require(type(ref) is dict and set(ref)=={"id","seal"},"SETUP_BINDINGS")
                allocation=Allocation(ref["id"],self.spec.operation(key),seal=ref["seal"])
                require(allocation.seal is not None and allocation.object_id not in identities
                        and self.port.inspect(key,allocation)==allocation,"ALLOCATION_UNVERIFIED")
                identities.add(allocation.object_id)

