"""Fresh local admission to an existing ACTIVE configuration, never activation.

No saved readiness, old transaction WAL or frozen workload is an execution grant.
Role election is independent; every ordinary runtime boundary checks this again.
"""
from dataclasses import dataclass, replace
from dataclasses import asdict
import copy
import hashlib

from .ballpark import catalogue
from .ballpark_records import provenance, shared
from .ballpark_setup import pin_record
from .commissioning_checks import CommissionedStorage, Prerequisites
from .commissioning_state import storage_spec, validated
from .configuration_contract import configuration, require
from .drive.commissioning_native import NativeCommissioning
from .drive.commissioning_folder import FolderCommissioning
from .drive.folder_mapping import FolderMappedCommissioning
from .drive.leadership import ClockSample, Grant, Leadership
from .instructions import check_boundary
from .private_settings import PrivateSettings
from .reconfiguration_candidate import native_binding, SCHEMA as CANDIDATE_SCHEMA, SCHEMA_SHA256 as CANDIDATE_SHA
from .reconfiguration_effects import covered, ledger, SLOT, SCHEMA as EFFECT_SCHEMA, SCHEMA_SHA256 as EFFECT_SHA
from .reconfiguration_inspection import inspect
from .reconfiguration_maintenance import sha, WAL_SCHEMA, WAL_SCHEMA_SHA256
from .timing_contract import TimingProfile
from .watchdog.checkpoint_store import NativeCheckpoint, SCHEMA as CHECKPOINT_SCHEMA, SCHEMA_SHA256 as CHECKPOINT_SHA
from .watchdog.leadership_runtime import Action, Capabilities


@dataclass(frozen=True, repr=False)
class AdmissionContext:
    profile: PrivateSettings
    checkpoint: NativeCheckpoint
    leadership: Leadership
    checker: Prerequisites
    capabilities: object
    clock: object


class ConfigurationAdmission:
    def __init__(self, context):
        require(type(context) is AdmissionContext and type(context.profile) is PrivateSettings
                and type(context.checkpoint) is NativeCheckpoint and isinstance(context.leadership, Leadership)
                and type(context.checker) is Prerequisites
                and type(context.checker.storage) is CommissionedStorage
                and type(context.checker.storage.port) in {NativeCommissioning, FolderCommissioning, FolderMappedCommissioning}
                and callable(context.capabilities) and callable(context.clock), "ADMISSION_CONTEXT")
        require(context.checkpoint.installation_id == context.leadership.actor
                and context.checkpoint.binding == context.leadership.backend.binding, "ADMISSION_CONTEXT")
        self.context = context
        self._bindings()

    def _bindings(self, checkpoint_binding=None):
        # The optional identity comes only from our already-held actual port.
        cp = native_binding(self.context.checkpoint.store) if checkpoint_binding is None else checkpoint_binding
        profile = native_binding(self.context.profile)
        require(profile != cp, "ADMISSION_STORE_ALIAS")
        return profile, cp

    def _local(self, payload, cp, *, releasing):
        require(payload["installation_id"] == self.context.leadership.actor
                and payload["choices"]["role"] == "watchdog" and payload["state"] != "CANCELLED"
                and "UNKNOWN" not in payload["operations"].values(), "ADMISSION_PROFILE")
        require(cp.election is None and type(cp.grant) is Grant, "ADMISSION_LEADERSHIP_UNKNOWN")
        if not releasing:
            require(cp.maintenance is None, "CONFIGURATION_MAINTENANCE")
        spec, handle = storage_spec(payload["choices"]["storage"])
        require(self.context.checker.storage.port.authority(handle).binding == self.context.leadership.backend.binding,
                "ADMISSION_AUTHORITY")
        pub = payload.get("ballpark_publication")
        require(type(pub) is dict and pub["active"] is not None and pub["pending"] is None, "ADMISSION_PUBLICATION")
        # validated(payload) already validates this complete protected receipt.
        return spec, pub["active"]

    def _current(self, payload, cp, *, releasing):
        self._local(payload, cp, releasing=releasing)
        require(type(self.context.leadership.profile) is TimingProfile
                and self.context.leadership.profile == TimingProfile.parse(payload["choices"]["timing"]),
                "ADMISSION_TIMING")
        caps, sample = self.context.capabilities(), self.context.clock()
        require(type(caps) is Capabilities and caps.installation_id == payload["installation_id"]
                and caps.observe is True and caps.coordinate is True and type(caps.actions) is frozenset
                and all(type(a) is Action for a in caps.actions)
                and (not releasing or Action.IDENTITY in caps.actions), "ADMISSION_CAPABILITIES")
        require(type(sample) is ClockSample and sample.wall_trusted and sample.monotonic_trusted, "ADMISSION_CLOCK")
        observed = self.context.leadership.observe(sample)
        require(self.context.leadership._owns(observed.leader, observed.request, cp.grant), "OWNER_SUPERSEDED")
        doc = observed.snapshot.document()
        config = configuration(doc)
        require(config is not None and config["phase"] == "ACTIVE", "CONFIGURATION_MAINTENANCE")
        require(cp.maintenance in {None, config["transition_id"]}, "ADMISSION_TRANSITION")
        active = payload["ballpark_publication"]["active"]
        adoption = active.get("adoption")
        if adoption is not None:
            require(adoption["configuration"] == config
                    and adoption["authority"] == dict(mode=self.context.checker.storage.port.mode, binding=asdict(observed.snapshot.binding)),
                    "ADMISSION_PUBLICATION")
        require(shared(doc) == catalogue(payload["choices"]["descriptor"])
                and doc["records"]["global.settings"]["body"]["timing"] == payload["choices"]["timing"]
                and doc["records"]["global.registry"]["body"]["provenance"] == (
                    provenance(active) if adoption is None else adoption["provenance"]),
                "ADMISSION_PUBLICATION")
        effects = ledger(doc["records"][SLOT])
        require(effects is not None and covered(doc, config["transition_id"])
                and "root_plan" not in effects and "folder_plan" not in effects, "ADMISSION_RESOLUTION")
        if releasing:
            blockers = inspect(observed.snapshot, setup_payload=payload, checkpoint=cp).blockers
            # Adopting an already committed ACTIVE configuration never changes
            # shared routing. Inherited work/effects retain ordinary no-replay
            # guards and cannot become an unavailable former-host ACK barrier.
            require(not (blockers if adoption is None else tuple(
                    b for b in blockers if b.kind.startswith("LOCAL_"))),
                    "ADMISSION_UNRESOLVED")
        return observed.snapshot, config, sample

    def _prove(self, *, releasing=False, checkpoint=None, checkpoint_binding=None):
        ctx = self.context
        bindings = self._bindings(checkpoint_binding)
        profile = ctx.profile.read()
        require(profile is not None, "ADMISSION_PROFILE")
        payload = validated(profile.payload)
        cp = ctx.checkpoint.read() if checkpoint is None else checkpoint
        before, config, sample = self._current(payload, cp, releasing=releasing)
        validation = ctx.checker.validate(copy.deepcopy(payload))
        pin = validation.pin
        require(pin_record(pin) == payload["ballpark_publication"]["active"]["pin"]
                and all(hashlib.sha256(pin.read(path)).hexdigest() == expected for path, expected in (
                    (WAL_SCHEMA, WAL_SCHEMA_SHA256), (EFFECT_SCHEMA, EFFECT_SHA),
                    (CHECKPOINT_SCHEMA, CHECKPOINT_SHA), (CANDIDATE_SCHEMA, CANDIDATE_SHA))), "ADMISSION_INSTRUCTIONS")
        check_boundary(ctx.checker.source, pin, ctx.checker.runtime)
        require(ctx.profile.read() == profile and self._bindings(checkpoint_binding) == bindings, "ADMISSION_PROFILE_CHANGED")
        require(checkpoint is not None or ctx.checkpoint.read() == cp, "ADMISSION_CHECKPOINT_CHANGED")
        after, fresh, current_clock = self._current(payload, cp, releasing=releasing)
        require(fresh == config and current_clock.monotonic >= sample.monotonic
                and all(after.document()["records"][k] == before.document()["records"][k]
                        for k in ("global.settings", "global.registry", "global.commissioning")),
                "ADMISSION_CHANGED")
        # Normal BUSY/UNREAD work and our own durable UNKNOWN are handled by
        # ordinary runtime/Effects guards, never made into a role ACK gate.
        return fresh["revision"], cp

    def revision(self):
        """Trusted zero-argument runtime callback; revalidates on every use."""
        return self._prove()[0]

    def release(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        ctx = self.context
        cp = ctx.checkpoint.read()
        if cp.maintenance is None:
            return self.revision()
        self._prove(releasing=True)
        store = ctx.checkpoint.store
        with store.native.locked() as port:
            require(port.read("settings.pending") is None, "ADMISSION_INSPECT_REQUIRED")
            current = store._decode(port.read("settings.json"), port.binding)
            actual = ctx.checkpoint._decode(current.payload)
            require(actual == cp, "ADMISSION_CHECKPOINT_CHANGED")
            revision, _ = self._prove(releasing=True, checkpoint=actual, checkpoint_binding=sha(port.binding))
            desired = replace(actual, maintenance=None)
            saved = store._save_locked(port, ctx.checkpoint._encode(desired), expected_revision=current.revision)
            require(ctx.checkpoint._decode(saved.payload) == desired, "ADMISSION_UNCONFIRMED")
        require(ctx.checkpoint.read() == desired, "ADMISSION_UNCONFIRMED")
        require(self.revision() == revision, "ADMISSION_CHANGED")
        return revision

    def recover_pending(self, *, owner_authorized=False):
        """Promote only this exact reservation-release frame after fresh proof."""
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        ctx, store = self.context, self.context.checkpoint.store
        with store.native.locked() as port:
            pending, raw = port.read("settings.pending"), port.read("settings.json")
            if pending is None:
                return "NO_PENDING"
            candidate, current = store._decode(pending, port.binding), store._decode(raw, port.binding)
            before, after = ctx.checkpoint._decode(current.payload), ctx.checkpoint._decode(candidate.payload)
            require(before.maintenance is not None and after == replace(before, maintenance=None)
                    and candidate.revision == current.revision + 1 and candidate.previous == current.payload,
                    "ADMISSION_RECOVERY")
            self._prove(releasing=True, checkpoint=before, checkpoint_binding=sha(port.binding))
            require(port.read("settings.pending") == pending and port.read("settings.json") == raw, "ADMISSION_RECOVERY")
            port.promote()
            require(port.read("settings.json") == pending, "ADMISSION_UNCONFIRMED")
        return "INSPECT_REQUIRED"

    def status(self):
        return dict(runtime_active=False, automatic_replay=False)
