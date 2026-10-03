"""Own current-role ACTIVE adoption of an existing actual Linux Folder authority.

The original fixed marker/spec/objects remain. This is a local profile operation,
not a shared mutation, relocation, replay or a former installation's private input.
"""
from dataclasses import asdict
import copy

from .commissioning_state import storage_spec, validated
from .commissioning_records import current_record
from .configuration_contract import require
from .drive.commissioning_folder import FolderCommissioning
from .drive.folder_mapping import FolderMappedCommissioning
from .private_settings import PrivateSettings
from .reconfiguration_active_adoption import ActiveAdoption, ActiveAdoptionContext
from .reconfiguration_admission import AdmissionContext, ConfigurationAdmission
from .reconfiguration_candidate import native_binding

PORTS = {FolderCommissioning, FolderMappedCommissioning}


def current_folder_admission(local):
    """Current own Main/actual port suffice; no old adoption WAL or mapping."""
    require(type(local) is AdmissionContext and type(local.checker.storage.port) in PORTS,
            "FOLDER_ACTIVE_ADOPTION_CONTEXT")
    ConfigurationAdmission(local)
    frame = local.profile.read()
    require(frame is not None, "ACTIVE_ADOPTION_PROFILE")
    payload = validated(frame.payload)
    spec,_ = storage_spec(payload["choices"]["storage"])
    require(spec == local.checker.storage.port.spec, "FOLDER_ACTIVE_ADOPTION_STORAGE")
    return ConfigurationAdmission(local)


class FolderActiveAdoption(ActiveAdoption):
    SCHEMA_DEFINITION = "folderActiveAdoption"
    KIND = "RECONFIGURATION_FOLDER_ACTIVE_ADOPTION"
    ARCHIVE_KIND = "RECONFIGURATION_FOLDER_ACTIVE_ADOPTION_ORIGINAL"
    RECEIPT_KIND = "CURRENT_FOLDER_ACTIVE_ADOPTION"

    def __init__(self, context):
        require(type(context) is ActiveAdoptionContext and type(context.local) is AdmissionContext
                and type(context.local.checker.storage.port) in PORTS
                and all(type(s) is PrivateSettings for s in (
                    context.profile, context.archive, context.transaction)), "FOLDER_ACTIVE_ADOPTION_CONTEXT")
        ConfigurationAdmission(context.local)
        self.context = context
        self._bindings()

    def _bindings(self, *, held=None):
        values = super()._bindings(held=held)
        port = self.context.local.checker.storage.port
        if type(port) is FolderMappedCommissioning:
            values["mapping"] = native_binding(port.mapping.store)
        require(len(set(values.values())) == len(values), "ACTIVE_ADOPTION_STORE_ALIAS")
        return values

    def _authority_record(self, binding):
        return dict(mode="FOLDER_SQLITE_V1", binding=asdict(binding))

    def _storage_schema(self, storage, authority):
        spec,handle = storage_spec(storage)
        port = self.context.local.checker.storage.port
        require(set(storage) == {"spec","authority"} and spec == port.spec and spec.mode == "FOLDER_SQLITE_V1"
                and spec.domain_id == port.binding.domain_id and spec.root_id == port.binding.root_id
                and handle.object_id == spec.root_id and handle.tab_id is None
                and authority == self._authority_record(port.binding)
                and port.binding == self.context.local.leadership.backend.binding,
                "ACTIVE_ADOPTION_BINDING")

    def _current_storage(self, payload, doc, binding):
        storage = copy.deepcopy(payload["choices"]["storage"])
        spec,handle = storage_spec(storage)
        port = self.context.local.checker.storage.port
        self._storage_schema(storage, self._authority_record(binding))
        # Same-folder final publication deliberately retains the original marker.
        current_record(doc, spec)
        port.check_root()
        require(port.inspect_authority(spec,handle) == handle
                and port.authority(handle).binding == binding, "ACTIVE_ADOPTION_AUTHORITY")
        return storage

    def _storage_request(self, storage):
        spec,_ = storage_spec(storage)
        port = self.context.local.checker.storage.port
        require(spec == port.spec, "FOLDER_ACTIVE_ADOPTION_STORAGE")
        # This installation's configured and freshly selected protected path.
        return dict(mode=port.mode, location=str(port.root))

    def _checker(self, state):
        self._storage_schema(state["storage"],state["authority"])
        return self.context.local.checker

    def admission(self):
        state,_ = self._state()
        require(state is not None and state["phase"] in {"PREPARED","PROMOTED"},
                "ACTIVE_ADOPTION_INSPECT_REQUIRED")
        require(self.inspect() == "PROFILE_PROMOTED", "ACTIVE_ADOPTION_INSPECT_REQUIRED")
        return current_folder_admission(self.context.local)
