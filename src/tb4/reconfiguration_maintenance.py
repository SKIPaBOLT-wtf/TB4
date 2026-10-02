"""Unreleased settings-only maintenance WAL and explicit zero-blocker resolution.

No candidate promotion, root relocation, work deletion, cancellation, executor or
default activation. All ports are trusted local composition, never shared input.
"""
from __future__ import annotations

import copy
import base64
from dataclasses import asdict, dataclass
import hashlib
import json
import re

from .ballpark_records import shared
from .ballpark_setup import pin_record, restore_pin, validate_pin
from .commissioning_checks import CommissionedStorage
from .commissioning_state import Setup, storage_spec
from .configuration_contract import ConfigurationError, configuration, require
from .drive.authority_transaction import OwnerGuard, RecordMutation, reconcile
from .drive.commissioning import frozen_plan, restored_plan
from .drive.leadership import ClockSample, Grant, Leadership
from .exchange_layout import MAX_GENERATION, encoded, validate_document
from .instructions import check_boundary, select
from .private_settings import PrivateSettings
from .reconfiguration_evidence import EvidenceReceipt, ProtectedEvidence
from .reconfiguration_inspection import authority_image, inspect, workload_fingerprint
from .watchdog.leadership_runtime import Action, Capabilities, Checkpoint
from .reconfiguration_effects import Effects, ledger, barrier_row, covered, SLOT

WAL_SCHEMA = "protocol/reconfiguration-maintenance-v1.schema.json"
WAL_SCHEMA_SHA256 = "f8cba98bb15e544d84a2e73cc58a2e359e974f96e323f708a46107275de13d31"
SETTINGS = "global.settings"
PROTECTED = frozenset({"global.commissioning", "global.registry"})


def sha(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def hex64(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True, repr=False)
class MaintenanceMutation(RecordMutation):
    """Closed settings-only ENTER transition; elections use their own primitive."""

    @classmethod
    def enter(cls, snapshot, owner, *, transition_id, effect_summary=None):
        document = snapshot.document()
        shared(document)
        require(type(owner) is OwnerGuard and owner.matches(document), "OWNER_SUPERSEDED")
        old = configuration(document)
        require(old is None or old["phase"] == "ACTIVE", "CONFIGURATION_ALREADY_MAINTAINED")
        revision = 1 if old is None else old["revision"] + 1
        require(revision <= MAX_GENERATION and hex64(transition_id)
                and (old is None or transition_id != old["transition_id"]), "CONFIGURATION_TRANSITION")
        before = copy.deepcopy(document["records"][SETTINGS])
        after = copy.deepcopy(before)
        after["body"]["configuration"] = dict(schema_version=1, revision=revision,
            phase="MAINTENANCE", transition_id=transition_id)
        proposed = copy.deepcopy(document)
        proposed["records"][SETTINGS] = after
        before_rows, after_rows = {SETTINGS:before}, {SETTINGS:after}
        protected = PROTECTED | {SLOT}
        if effect_summary is not None:
            value = ledger(effect_summary)
            require(value is not None and value["barrier"] is not None
                    and effect_summary == barrier_row(document["records"][SLOT], owner=owner,
                        transition=transition_id, local_clear=value["barrier"]["local_clear"]),
                    "CONFIGURATION_EFFECT_EVIDENCE_REQUIRED")
            before_rows[SLOT], after_rows[SLOT] = document["records"][SLOT], effect_summary
            protected = PROTECTED
            proposed["records"][SLOT] = effect_summary
        validate_document(proposed)
        require(shared(proposed) == shared(document), "CONFIGURATION_DESCRIPTOR_CHANGED")
        return cls(snapshot.binding, owner, encoded({k:v for k,v in document.items() if k != "records"}),
            encoded({k:document["records"][k] for k in protected}),
            encoded(before_rows), encoded(after_rows))

    @classmethod
    def restore(cls, value, binding, *, transition_id, revision):
        try:
            plan = restored_plan(value, binding)
            parts = {k:json.loads(getattr(plan,k)) for k in ("header","protected","before","after")}
            require(all(encoded(v) == getattr(plan,k) for k,v in parts.items()), "CONFIGURATION_WAL")
            keys = set(parts["before"])
            require(keys in ({SETTINGS}, {SETTINGS,SLOT}) and keys == set(parts["after"])
                    and set(parts["protected"]) == (PROTECTED | ({SLOT} if SLOT not in keys else set())),
                    "CONFIGURATION_WAL")
            before, after = parts["before"][SETTINGS], parts["after"][SETTINGS]
            expected = copy.deepcopy(before)
            expected["body"]["configuration"] = dict(schema_version=1, revision=revision,
                phase="MAINTENANCE", transition_id=transition_id)
            require(after == expected, "CONFIGURATION_WAL")
            if SLOT in keys:
                summary = parts["after"][SLOT]
                effects = ledger(summary)
                require(effects is not None and effects["barrier"] is not None
                        and summary == barrier_row(parts["before"][SLOT], owner=plan.owner,
                            transition=transition_id, local_clear=effects["barrier"]["local_clear"]),
                        "CONFIGURATION_WAL")
            from .exchange_layout import Capacity, empty_document
            header = parts["header"]
            require(type(header) is dict and set(header) == {"layout_version", "compatibility_status",
                "domain_id", "layout_revision", "capacity"}, "CONFIGURATION_WAL")
            probe = empty_document(binding.domain_id, Capacity.parse(header["capacity"]))
            probe.update(header)
            require(probe["domain_id"] == binding.domain_id, "CONFIGURATION_WAL")
            probe["records"].update(parts["protected"])
            probe["records"].update(parts["before"])
            validate_document(probe)
            old = configuration(probe)
            require(revision == (1 if old is None else old["revision"] + 1)
                    and (old is None or old["phase"] == "ACTIVE"
                         and old["transition_id"] != transition_id), "CONFIGURATION_WAL")
            probe["records"].update(parts["after"])
            configuration(probe)
            require(type(plan.owner.owner) is str and 1 <= len(plan.owner.owner) <= 128
                    and type(plan.owner.epoch) is int and 1 <= plan.owner.epoch <= MAX_GENERATION,
                    "CONFIGURATION_WAL")
            return cls(binding, plan.owner, plan.header, plan.protected, plan.before, plan.after)
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("CONFIGURATION_WAL") from None

    def evaluate(self, snapshot):
        document = snapshot.document()
        if snapshot.binding != self.binding or encoded({k:v for k,v in document.items() if k != "records"}) != self.header:
            return "CONFLICT", None
        rows = document["records"]
        protected, before, after = (json.loads(v) for v in (self.protected,self.before,self.after))
        if all(encoded(rows[k]) == encoded(v) for k,v in after.items()):
            return "CONFIRMED", None  # Exact prior effect, including after owner takeover.
        if any(encoded(rows[k]) != encoded(v) for k,v in protected.items()):
            return "CONFLICT", None
        if not self.owner.matches(document):
            return "SUPERSEDED", None
        if any(encoded(rows[k]) != encoded(v) for k,v in before.items()):
            return "CONFLICT", None
        document["records"].update(after)
        configuration(document)
        return "READY", document


@dataclass(frozen=True, repr=False)
class ResolutionProposal:
    transition_id: str
    revision: int
    owner: str
    epoch: int
    work_sha256: str
    setup_sha256: str

    def __post_init__(self):
        require(hex64(self.transition_id) and hex64(self.work_sha256) and hex64(self.setup_sha256)
                and type(self.revision) is int and 1 <= self.revision <= MAX_GENERATION
                and type(self.epoch) is int and 1 <= self.epoch <= MAX_GENERATION
                and type(self.owner) is str and 1 <= len(self.owner) <= 128, "CONFIGURATION_RESOLUTION")


@dataclass(frozen=True, repr=False)
class MaintenanceContext:
    setup: Setup
    leadership: Leadership
    checkpoint: object
    store: PrivateSettings
    baseline: ProtectedEvidence
    storage_port: object
    clock: object
    capabilities: object
    source: object
    runtime: object
    effects: object = None


class Maintenance:
    def __init__(self, context):
        require(type(context) is MaintenanceContext and type(context.setup) is Setup
                and isinstance(context.leadership, Leadership) and type(context.store) is PrivateSettings
                and type(context.baseline) is ProtectedEvidence
                and context.setup.installation_id == context.leadership.actor == context.baseline.installation_id
                and callable(context.clock) and callable(context.capabilities), "CONFIGURATION_CONTEXT")
        require(context.checkpoint.installation_id == context.setup.installation_id
                and context.checkpoint.binding == context.leadership.backend.binding, "CONFIGURATION_CONTEXT")
        self.context, self._pin = context, None
        if context.effects is not None:
            require(type(context.effects) is Effects and context.effects.leadership is context.leadership
                    and context.effects.checkpoint is context.checkpoint, "CONFIGURATION_EFFECT_CONTEXT")

    def _proof(self, state=None):
        try:
            if self._pin is None:
                self._pin = (select(self.context.source, self.context.runtime) if state is None else
                             restore_pin(self.context.source, state["pin"], self.context.runtime))
            check_boundary(self.context.source, self._pin, self.context.runtime)
            require(hashlib.sha256(self._pin.read(WAL_SCHEMA)).hexdigest() == WAL_SCHEMA_SHA256,
                    "CONFIGURATION_SCHEMA_INCOMPATIBLE")
            if self.context.effects is not None:
                from .reconfiguration_effects import SCHEMA, SCHEMA_SHA256
                from .watchdog.checkpoint_store import SCHEMA as CS, SCHEMA_SHA256 as CSH
                require(all(hashlib.sha256(self._pin.read(path)).hexdigest() == expected
                            for path,expected in ((SCHEMA,SCHEMA_SHA256),(CS,CSH))),
                        "CONFIGURATION_SCHEMA_INCOMPATIBLE")
            if state is not None:
                require(pin_record(self._pin) == state["pin"], "CONFIGURATION_PIN_CHANGED")
            return self._pin
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("CONFIGURATION_INSTRUCTIONS_REQUIRED") from None

    def _current(self):
        ctx = self.context
        try:
            ctx.setup._fresh()
            choices = ctx.setup.private_choices()
            require(choices["role"] == "watchdog" and ctx.setup._payload["state"] != "CANCELLED",
                    "CONFIGURATION_CONTEXT")
            caps, sample, checkpoint = ctx.capabilities(), ctx.clock(), ctx.checkpoint.read()
            require(type(caps) is Capabilities and caps.installation_id == ctx.setup.installation_id
                    and caps.observe is True and caps.coordinate is True and type(caps.actions) is frozenset
                    and all(type(a) is Action for a in caps.actions)
                    and Action.IDENTITY in caps.actions, "CONFIGURATION_NOT_AUTHORIZED")
            require(type(sample) is ClockSample and sample.wall_trusted and sample.monotonic_trusted,
                    "CONFIGURATION_CLOCK")
            require(type(checkpoint) is Checkpoint and checkpoint.election is None
                    and type(checkpoint.grant) is Grant, "CONFIGURATION_LEADERSHIP_UNKNOWN")
            _, handle = storage_spec(choices["storage"])
            require(ctx.storage_port.authority(handle).binding == ctx.leadership.backend.binding,
                    "CONFIGURATION_CONTEXT")
            CommissionedStorage(ctx.storage_port).verify(choices["storage"])
            observed = ctx.leadership.observe(sample)
            require(ctx.leadership._owns(observed.leader, observed.request, checkpoint.grant), "OWNER_SUPERSEDED")
            shared(observed.snapshot.document())
            return observed.snapshot, checkpoint
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("CONFIGURATION_CONTEXT_UNAVAILABLE") from None

    def _validate(self, value):
        try:
            require(type(value) is dict and set(value) == {"schema_version", "kind", "installation_id",
                "authority", "transition_id", "configuration_revision", "phase", "base_setup_sha256",
                "base_setup_revision", "pin", "baseline", "pending", "resolution", "adopted"}, "CONFIGURATION_WAL")
            ctx = self.context
            spec, handle = storage_spec(ctx.setup.private_choices()["storage"])
            authority = dict(mode=spec.mode, binding=asdict(ctx.leadership.backend.binding))
            require(type(value["schema_version"]) is int and value["schema_version"] == 1
                    and value["kind"] == "RECONFIGURATION_MAINTENANCE_WAL"
                    and value["installation_id"] == ctx.setup.installation_id and value["authority"] == authority
                    and value["transition_id"] == ctx.baseline.transition_id and hex64(value["transition_id"])
                    and hex64(value["base_setup_sha256"])
                    and type(value["base_setup_revision"]) is int and 1 <= value["base_setup_revision"] <= MAX_GENERATION
                    and type(value["configuration_revision"]) is int
                    and 1 <= value["configuration_revision"] <= MAX_GENERATION
                    and type(value["adopted"]) is bool
                    and value["phase"] in {"ENTERING", "MAINTENANCE", "RESOLVED", "SUPERSEDED"},
                    "CONFIGURATION_WAL")
            validate_pin(value["pin"])
            receipt = EvidenceReceipt(**value["baseline"])
            require(asdict(receipt) == value["baseline"] and receipt.installation_id == ctx.setup.installation_id
                    and receipt.transition_id == value["transition_id"] and hex64(receipt.payload_sha256),
                    "CONFIGURATION_WAL")
            require((value["pending"] is not None) == (value["phase"] == "ENTERING"), "CONFIGURATION_WAL")
            require(not value["adopted"] or value["pending"] is None
                    and (value["resolution"] is None or self.context.effects is not None),
                    "CONFIGURATION_WAL")
            if value["pending"] is not None:
                plan = MaintenanceMutation.restore(value["pending"], ctx.leadership.backend.binding,
                    transition_id=value["transition_id"], revision=value["configuration_revision"])
                require(plan.owner.owner == ctx.setup.installation_id, "CONFIGURATION_WAL")
            require((value["resolution"] is not None) == (value["phase"] == "RESOLVED"), "CONFIGURATION_WAL")
            if value["resolution"] is not None:
                resolution = value["resolution"]
                require(type(resolution) is dict and set(resolution) == {"decision", "evidence"}, "CONFIGURATION_WAL")
                decision = ResolutionProposal(**resolution["decision"])
                require(asdict(decision) == resolution["decision"] and decision.owner == ctx.setup.installation_id
                        and decision.transition_id == value["transition_id"]
                        and decision.revision == value["configuration_revision"], "CONFIGURATION_WAL")
                proof = EvidenceReceipt(**resolution["evidence"])
                require(asdict(proof) == resolution["evidence"] and proof.installation_id == ctx.setup.installation_id
                        and proof.transition_id == value["transition_id"] and hex64(proof.payload_sha256),
                        "CONFIGURATION_WAL")
            require(len(encoded(value)) <= 64 * 1024, "CONFIGURATION_WAL_SIZE")
            return copy.deepcopy(value)
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("CONFIGURATION_WAL") from None

    def _state(self):
        try:
            current = self.context.store.read()
            if current is None:
                return None, 0
            state = self._validate(current.payload)
            proof = self.context.baseline.read(EvidenceReceipt(**state["baseline"]))
            require(proof["inspection"]["authority"] == state["authority"]
                    and proof["inspection"]["setup_sha256"] == state["base_setup_sha256"], "CONFIGURATION_WAL")
            original = json.loads(base64.b64decode(proof["image"], validate=True))
            old_config = configuration(original)
            adopted = old_config is not None and old_config["phase"] == "MAINTENANCE"
            require(state["adopted"] == adopted, "CONFIGURATION_WAL")
            if adopted:
                require(old_config["transition_id"] == state["transition_id"]
                        and old_config["revision"] == state["configuration_revision"], "CONFIGURATION_WAL")
            elif state["pending"] is not None:
                plan = MaintenanceMutation.restore(state["pending"], self.context.leadership.backend.binding,
                    transition_id=state["transition_id"], revision=state["configuration_revision"])
                keys,protected = json.loads(plan.before),json.loads(plan.protected)
                require(plan.header == encoded({k:v for k,v in original.items() if k != "records"})
                        and plan.before == encoded({k:original["records"][k] for k in keys})
                        and plan.protected == encoded({k:original["records"][k] for k in protected})
                        and plan.owner.matches(original), "CONFIGURATION_WAL")
                if SLOT in keys:
                    barrier = ledger(json.loads(plan.after)[SLOT])["barrier"]
                    require(barrier["local_clear"] == (not any(x["kind"].startswith("LOCAL_")
                            for x in proof["inspection"]["blockers"])), "CONFIGURATION_WAL")
            return state, current.revision
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("CONFIGURATION_LOCAL_INSPECT_REQUIRED") from None

    def _save(self, value, revision):
        value = self._validate(value)
        self.context.store.save(value, expected_revision=revision)
        state, after = self._state()
        require(state == value and after == revision + 1, "CONFIGURATION_LOCAL_UNCONFIRMED")
        return state

    def begin(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        require(self._state()[0] is None, "CONFIGURATION_INSPECT_REQUIRED")
        self._proof()
        snapshot, checkpoint = self._current()
        if self.context.effects is not None:
            self.context.checkpoint.reserve(self.context.baseline.transition_id,owner_authorized=True)
            checkpoint = self.context.checkpoint.read()
            existing = configuration(snapshot.document())
            if existing is None or existing["phase"] != "MAINTENANCE":
                self.context.effects.ensure(checkpoint)
            snapshot, checkpoint = self._current()
        config = configuration(snapshot.document())
        ctx = self.context
        transaction = ctx.baseline.transition_id
        adopting = config is not None and config["phase"] == "MAINTENANCE"
        if adopting:
            require(config["transition_id"] == transaction, "CONFIGURATION_TRANSITION")
            plan, revision = None, config["revision"]
        else:
            summary = None
            if ctx.effects is not None:
                local = inspect(snapshot,setup_payload=ctx.setup._payload,checkpoint=checkpoint)
                summary = barrier_row(snapshot.document()["records"][SLOT],
                    owner=OwnerGuard(checkpoint.grant.owner,checkpoint.grant.epoch),transition=transaction,
                    local_clear=not any(x.kind.startswith("LOCAL_") for x in local.blockers))
            plan = MaintenanceMutation.enter(snapshot, OwnerGuard(checkpoint.grant.owner, checkpoint.grant.epoch),
                                             transition_id=transaction,effect_summary=summary)
            revision = json.loads(plan.after)[SETTINGS]["body"]["configuration"]["revision"]
        facts = inspect(snapshot, setup_payload=ctx.setup._payload, checkpoint=checkpoint)
        receipt = ctx.baseline.preserve(snapshot, facts, owner_authorized=True)
        value = dict(schema_version=1, kind="RECONFIGURATION_MAINTENANCE_WAL",
            installation_id=ctx.setup.installation_id, authority=facts.authority, transition_id=transaction,
            configuration_revision=revision, phase="MAINTENANCE" if adopting else "ENTERING",
            adopted=adopting,
            base_setup_sha256=facts.setup_sha256, base_setup_revision=ctx.setup.snapshot.revision,
            pin=pin_record(self._pin), baseline=asdict(receipt),
            pending=None if plan is None else frozen_plan(plan), resolution=None)
        self._save(value, 0)
        self._proof(value)
        self._current()  # Fresh admission after both protected writes.
        if adopting:
            return "MAINTENANCE"  # A local adoption, never a second authority write.
        report = reconcile(ctx.leadership.backend, plan, mode="START", max_reads=4, max_writes=2)
        if report.outcome == "CONFIRMED":
            return self.inspect()
        return report.outcome  # Exact pending plan survives even an unavailable reply.

    def inspect(self):
        state, revision = self._state()
        require(state is not None, "CONFIGURATION_NOT_STARTED")
        if state["pending"] is not None:
            plan = MaintenanceMutation.restore(state["pending"], self.context.leadership.backend.binding,
                transition_id=state["transition_id"], revision=state["configuration_revision"])
            report = reconcile(self.context.leadership.backend, plan, mode="INSPECT", max_reads=4, max_writes=1)
            if report.outcome == "CONFIRMED":
                self._save({**state, "phase":"MAINTENANCE", "pending":None}, revision)
                return "MAINTENANCE"
            if report.outcome == "SUPERSEDED":
                self._save({**state, "phase":"SUPERSEDED", "pending":None}, revision)
            return report.outcome
        config = configuration(self.context.leadership.backend.read().document())
        if (config is None or config["phase"] != "MAINTENANCE" or config["transition_id"] != state["transition_id"]
                or config["revision"] != state["configuration_revision"]):
            return "SUPERSEDED"
        return state["phase"]

    def _proposal(self, state):
        require(state["pending"] is None and state["phase"] in {"MAINTENANCE","RESOLVED"},
                "CONFIGURATION_INSPECT_REQUIRED")
        self._proof(state)
        if self.context.effects is not None:
            effect_state,_ = self.context.effects._state()
            require(effect_state is None or effect_state["pending"] is None, "CONFIGURATION_EFFECT_INSPECT_REQUIRED")
        snapshot, checkpoint = self._current()
        config = configuration(snapshot.document())
        require(config is not None and config == dict(schema_version=1,
            revision=state["configuration_revision"], phase="MAINTENANCE",
            transition_id=state["transition_id"]), "CONFIGURATION_SUPERSEDED")
        facts = inspect(snapshot, setup_payload=self.context.setup._payload, checkpoint=checkpoint)
        require(facts.setup_sha256 == state["base_setup_sha256"]
                and self.context.setup.snapshot.revision == state["base_setup_revision"],
                "CONFIGURATION_PROFILE_CHANGED")
        decision = ResolutionProposal(state["transition_id"], state["configuration_revision"],
            checkpoint.grant.owner, checkpoint.grant.epoch, workload_fingerprint(snapshot.document()), facts.setup_sha256)
        return decision, facts, snapshot

    def proposal(self):
        state, _ = self._state()
        require(state is not None, "CONFIGURATION_NOT_STARTED")
        decision, facts, snapshot = self._proposal(state)
        inherited = state["adopted"] and (self.context.effects is None
            or not covered(snapshot.document(),state["transition_id"]))
        return decision, {**facts.public_summary(), "original_evidence_required":inherited}

    def resolve(self, approved, evidence, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        state, revision = self._state()
        require(state is not None and type(approved) is ResolutionProposal
                and type(evidence) is ProtectedEvidence
                and evidence.installation_id == self.context.setup.installation_id
                and evidence.transition_id == state["transition_id"], "CONFIGURATION_RESOLUTION")
        decision, facts, snapshot = self._proposal(state)
        require(not state["adopted"] or self.context.effects is not None
                and covered(snapshot.document(),state["transition_id"]), "CONFIGURATION_ORIGINAL_EVIDENCE_REQUIRED")
        require(approved == decision, "CONFIGURATION_RESOLUTION_CHANGED")
        require(not facts.blockers, "CONFIGURATION_RESOLUTION_REQUIRED")
        receipt = evidence.preserve(snapshot, facts, owner_authorized=True)
        current, fresh_facts, _ = self._proposal(state)
        require(current == decision and not fresh_facts.blockers, "CONFIGURATION_RESOLUTION_CHANGED")
        self._save({**state, "phase":"RESOLVED", "resolution":dict(decision=asdict(decision),
                    evidence=asdict(receipt))}, revision)
        return "RESOLVED"

    def require_resolved(self, evidence):
        """Fresh prerequisite for the later staged candidate, never a bearer grant."""
        state, _ = self._state()
        require(state is not None and state["phase"] == "RESOLVED", "CONFIGURATION_RESOLUTION_REQUIRED")
        require(type(evidence) is ProtectedEvidence, "CONFIGURATION_RESOLUTION")
        proof = evidence.read(EvidenceReceipt(**state["resolution"]["evidence"]))
        decision, facts, _ = self._proposal(state)
        require(asdict(decision) == state["resolution"]["decision"] and not facts.blockers
                and proof["inspection"]["setup_sha256"] == decision.setup_sha256,
                "CONFIGURATION_RESOLUTION_CHANGED")
        return decision

    def refresh_local_evidence(self, *, owner_authorized=False):
        """Only the original guarded owner can certify its freshly clear local WAL.

This changes evidence only; UNKNOWN shared work/effects are never cleared here.
"""
        require(owner_authorized is True and self.context.effects is not None, "CONFIGURATION_OWNER_REQUIRED")
        state,_ = self._state()
        require(state is not None and not state["adopted"], "CONFIGURATION_ORIGINAL_EVIDENCE_REQUIRED")
        decision,facts,snapshot = self._proposal(state)
        require(not any(x.kind.startswith("LOCAL_") for x in facts.blockers), "CONFIGURATION_RESOLUTION_REQUIRED")
        result = self.context.effects.certify(snapshot,self.context.checkpoint.read().grant,state["transition_id"])
        return result  # New proposal/explicit approval is still required afterwards.

    def recover_local(self, *, owner_authorized=False):
        """Promote only the exact schema/binding-checked existing local candidate.

Provider work remains inspect-only. This does not reconstruct or replay a send.
"""
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        store = self.context.store
        try:
            with store.native.locked() as port:
                pending, raw = port.read("settings.pending"), port.read("settings.json")
                if pending is None:
                    return "NO_PENDING"
                candidate = store._decode(pending, port.binding)
                current = None if raw is None else store._decode(raw, port.binding)
                state = self._validate(candidate.payload)
                self.context.baseline.read(EvidenceReceipt(**state["baseline"]))
                require(candidate.revision == (0 if current is None else current.revision) + 1
                        and candidate.previous == (None if current is None else current.payload),
                        "CONFIGURATION_LOCAL_RECOVERY_CONFLICT")
                port.promote()
                require(port.read("settings.json") == pending, "CONFIGURATION_LOCAL_UNCONFIRMED")
            self._state()
            return "INSPECT_REQUIRED"
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("CONFIGURATION_LOCAL_INSPECT_REQUIRED") from None
