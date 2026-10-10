"""Own native current-role Folder ACTIVE adoption; no former host or ACK."""
import copy
from dataclasses import asdict

from .commissioning_records import current_record
from .commissioning_state import storage_spec, validated
from .configuration_contract import configuration, require
from .drive.folder_prerequisites import native_folder_prerequisites
from .drive.folder_endpoint import _native
from .drive.folder_runtime import NativeFolderCommissioning
from .drive.leadership import Leadership
from .private_settings import PrivateSettings
from .reconfiguration_active_adoption import ActiveAdoptionContext
from .reconfiguration_admission import AdmissionContext, ConfigurationAdmission
from .reconfiguration_candidate import native_binding
from .reconfiguration_folder_active_adoption import FolderActiveAdoption
from .reconfiguration_folder_runtime import native_folder_admission
from .reconfiguration_maintenance import sha
from .timing_contract import TimingProfile
from .watchdog.checkpoint_store import NativeCheckpoint


def native_current_folder_admission(local):
    require(type(local) is AdmissionContext
        and type(local.checker.storage.port) is NativeFolderCommissioning
        and local.checker.storage.port._connection.profile is local.profile,
        "NATIVE_FOLDER_ACTIVE_CONTEXT")
    port=local.checker.storage.port
    return native_folder_admission(local.profile,local.checkpoint,access=port._access,
        environment=local.checker.environment,credential_clock=port._connection._clock,
        clock=local.clock,capabilities=local.capabilities,source=local.checker.source,
        runtime=local.checker.runtime,enrollment=local.leadership.enrollment)


class NativeFolderActiveAdoption(FolderActiveAdoption):
    def __init__(self,context):
        require(type(context) is ActiveAdoptionContext and type(context.local) is AdmissionContext
            and type(context.local.checker.storage.port) is NativeFolderCommissioning
            and context.local.checker.storage.port._connection.profile is context.local.profile
            and all(type(s) is PrivateSettings for s in
                (context.profile,context.archive,context.transaction)), "NATIVE_FOLDER_ACTIVE_CONTEXT")
        ConfigurationAdmission(context.local)
        self.context=context
        self._bindings()

    def _bindings(self,*,held=None):
        values=super()._bindings(held=held)
        port=self.context.local.checker.storage.port
        require(type(port) is NativeFolderCommissioning, "NATIVE_FOLDER_ACTIVE_CONTEXT")
        port._current()
        require(native_binding(port._connection.metadata.store) not in values.values(),
            "ACTIVE_ADOPTION_STORE_ALIAS")
        return values

    def _storage_schema(self,storage,authority):
        spec,handle=storage_spec(storage);port=self.context.local.checker.storage.port
        binding=self.context.local.leadership.backend.binding
        require(set(storage)=={"spec","authority"} and spec==port.spec
            and spec.mode=="FOLDER_SQLITE_V1" and spec.root_id==binding.root_id
            and spec.domain_id==binding.domain_id and handle.object_id==spec.root_id
            and handle.tab_id is None and authority==dict(mode=port.mode,binding=asdict(binding))
            and port.authority(handle).binding==binding, "ACTIVE_ADOPTION_BINDING")

    def _current_storage(self,payload,doc,binding):
        storage=copy.deepcopy(payload["choices"]["storage"])
        self._storage_schema(storage,self._authority_record(binding))
        spec,_=storage_spec(storage);current_record(doc,spec)
        fresh=self.context.local.checker.storage.port.verify(storage)
        current_record(fresh,spec)
        require(configuration(fresh)==configuration(doc)
            and all(fresh["records"][k]==doc["records"][k] for k in
                ("global.registry","global.settings","global.commissioning")),
            "ACTIVE_ADOPTION_CHANGED")
        return storage

    def _storage_request(self,storage):
        self._storage_schema(storage,self._authority_record(self.context.local.leadership.backend.binding))
        frame=self.context.local.profile.read()
        require(frame is not None,"ACTIVE_ADOPTION_PROFILE")
        return copy.deepcopy(validated(frame.payload)["choices"]["storage_request"])

    def _checker(self,state):
        self._storage_schema(state["storage"],state["authority"])
        old=self.context.local.checker;port=old.storage.port
        return native_folder_prerequisites(self.context.profile,access=port._access,
            environment=old.environment,source=old.source,runtime=old.runtime,
            clock=port._connection._clock,normal_authority=True)

    def _profile(self,payload,base,state,current_shared):
        value=super()._profile(payload,base,state,current_shared)
        require(value.get("folder_endpoint")==base.get("folder_endpoint"),"ACTIVE_ADOPTION_PROFILE")
        return value

    def recover_local(self,which,*,owner_authorized=False):
        if which!="original":return super().recover_local(which,owner_authorized=owner_authorized)
        local=self.context.local;old=local.checker;port=old.storage.port
        return recover_native_folder_main(local.profile,self.context.profile,self.context.archive,
            self.context.transaction,local.checkpoint,access=port._access,environment=old.environment,
            credential_clock=port._connection._clock,clock=local.clock,capabilities=local.capabilities,
            source=old.source,runtime=old.runtime,enrollment=local.leadership.enrollment,
            owner_authorized=owner_authorized)

    def admission(self):
        state,_=self._state()
        require(state is not None and state["phase"] in {"PREPARED","PROMOTED"}
            and self.inspect()=="PROFILE_PROMOTED","ACTIVE_ADOPTION_INSPECT_REQUIRED")
        return native_current_folder_admission(self.context.local)


class _PendingMainProof(NativeFolderActiveAdoption):
    """Internal read-only proof context; its native connection reads own stage."""
    def __init__(self,context,base):
        ConfigurationAdmission(context.local)
        self.context=context
        self._recovery_base=copy.deepcopy(base)
        self._bindings()

    def _storage_request(self,storage):
        self._storage_schema(storage,self._authority_record(self.context.local.leadership.backend.binding))
        return copy.deepcopy(self._recovery_base["choices"]["storage_request"])


def recover_native_folder_main(original,profile,archive,transaction,checkpoint,*,access,
        environment,credential_clock,clock,capabilities,source,runtime,enrollment,owner_authorized=False):
    """Cold restart of exactly one prepared native child, never normal admission.

    The ordinary Main transport still refuses pending data. This narrow path
    reconstructs fresh read-only proof from the frozen own stage and promotes
    the already-existing child. Transaction precedes Main in native lock order.
    """
    require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
    stores=(original,profile,archive,transaction)
    require(all(type(s) is PrivateSettings and _native(s) for s in stores)
        and type(checkpoint) is NativeCheckpoint and _native(checkpoint.store),
        "NATIVE_FOLDER_ACTIVE_CONTEXT")
    bindings=[native_binding(s) for s in (*stores,checkpoint.store)]
    require(len(set(bindings))==len(bindings),"ACTIVE_ADOPTION_STORE_ALIAS")
    with original.native.locked() as port:
        pending,raw=port.read("settings.pending"),port.read("settings.json")
        if pending is None:return "NO_PENDING"
        require(raw is not None,"ACTIVE_ADOPTION_RECOVERY")
        child,current=original._decode(pending,port.binding),original._decode(raw,port.binding)
        require(child.revision==current.revision+1 and child.previous==current.payload,
                "ACTIVE_ADOPTION_RECOVERY")
    saved=transaction.read();stage=profile.read();prior=archive.read()
    require(saved is not None and stage is not None and prior is not None,"ACTIVE_ADOPTION_RECOVERY")
    state=saved.payload;promotion=state.get("promotion")
    require(state.get("kind")==NativeFolderActiveAdoption.KIND and state.get("phase")=="PREPARED"
        and type(promotion) is dict and state.get("base_revision")==current.revision
        and state.get("base_sha256")==sha(current.payload)
        and promotion.get("stage_revision")==stage.revision
        and promotion.get("stage_sha256")==sha(stage.payload)
        and promotion.get("payload_sha256")==sha(child.payload),"ACTIVE_ADOPTION_RECOVERY")
    base=validated(current.payload);staged=validated(stage.payload)
    require(prior.revision==1 and prior.previous is None
        and prior.payload.get("profile")==base
        and staged.get("folder_endpoint")==base.get("folder_endpoint")
        and staged.get("credential_image")==base.get("credential_image"),
        "ACTIVE_ADOPTION_PROFILE")
    # No key/transport is opened until the prepared child and full stage agree.
    checker=native_folder_prerequisites(profile,access=access,environment=environment,
        source=source,runtime=runtime,clock=credential_clock,normal_authority=True)
    _,handle=storage_spec(staged["choices"]["storage"])
    leader=Leadership(checker.storage.port.authority(handle),actor=base["installation_id"],
        enrollment=enrollment,profile=TimingProfile.parse(staged["choices"]["timing"]))
    local=AdmissionContext(original,checkpoint,leader,checker,capabilities,clock)
    proof=_PendingMainProof(ActiveAdoptionContext(local,profile,archive,transaction),base)
    with transaction.native.locked() as held:
        txraw=held.read("settings.json")
        require(held.read("settings.pending") is None and transaction._decode(txraw,held.binding)==saved,
                "ACTIVE_ADOPTION_CHANGED")
        qualified,_=proof._qualified(state,held={"transaction":sha(held.binding)},original_snapshot=current)
        require(qualified[2]=="ORIGINAL" and qualified[1]==child.payload
            and held.read("settings.json")==txraw and held.read("settings.pending") is None,
            "ACTIVE_ADOPTION_RECOVERY")
        # Remote/source/role checks have finished before the Main lock is taken.
        with original.native.locked() as port:
            require(port.read("settings.pending")==pending and port.read("settings.json")==raw,
                    "ACTIVE_ADOPTION_RECOVERY")
            port.promote()
            require(port.read("settings.json")==pending and port.read("settings.pending") is None,
                    "ACTIVE_ADOPTION_UNCONFIRMED")
    return "INSPECT_REQUIRED"

