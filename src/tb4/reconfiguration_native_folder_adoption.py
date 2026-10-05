"""Own native current-role Folder ACTIVE adoption; no former host or ACK."""
import copy
from dataclasses import asdict

from .commissioning_records import current_record
from .commissioning_state import storage_spec, validated
from .configuration_contract import configuration, require
from .drive.folder_prerequisites import native_folder_prerequisites
from .drive.folder_runtime import NativeFolderCommissioning
from .private_settings import PrivateSettings
from .reconfiguration_active_adoption import ActiveAdoptionContext
from .reconfiguration_admission import AdmissionContext, ConfigurationAdmission
from .reconfiguration_candidate import native_binding
from .reconfiguration_folder_active_adoption import FolderActiveAdoption
from .reconfiguration_folder_runtime import native_folder_admission


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

    def admission(self):
        state,_=self._state()
        require(state is not None and state["phase"] in {"PREPARED","PROMOTED"}
            and self.inspect()=="PROFILE_PROMOTED","ACTIVE_ADOPTION_INSPECT_REQUIRED")
        return native_current_folder_admission(self.context.local)

