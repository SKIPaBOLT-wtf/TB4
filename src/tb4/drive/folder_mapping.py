"""Protected same-folder lookup facts. No rename, role grant or dispatch."""
import copy
from dataclasses import asdict,dataclass
import hashlib
import os
from pathlib import Path
import stat
import sys

from tb4.ballpark_setup import pin_record,validate_pin
from tb4.commissioning_state import storage_spec
from tb4.configuration_contract import require
from tb4.drive.commissioning import digest,uuid
from tb4.exchange_layout import MAX_GENERATION
from tb4.private_settings import PrivateSettings,encoded
from tb4.private_settings_linux import LinuxSettingsNative
from tb4.reconfiguration_candidate import native_binding
from tb4.reconfiguration_effects import Effects,SLOT,ledger
from tb4.reconfiguration_evidence import ProtectedEvidence
from tb4.reconfiguration_maintenance import Maintenance,hex64
from tb4.watchdog.checkpoint_store import NativeCheckpoint
from .commissioning_folder import FolderCommissioning
from .folder_authority import FolderBinding,FolderConfig,FolderStore,identity,filesystem_type

SCHEMA="protocol/folder-path-mapping-v1.schema.json"
SCHEMA_SHA256="24f83e184623f491c4730e81a64101ce8828ea6be8e6c89b642eab04d1acaa1b"
FIELDS=frozenset({"schema_version","kind","installation_id","transition_id","configuration_revision",
    "base_setup_revision","base_setup_sha256","authority","source_path","target_path",
    "source_parent","target_parent","root_identity","db_identity","journal_identity",
    "blueprint_sha256","handle_sha256","marker_sha256","store_binding","pin"})
IDENTITIES=("source_parent","target_parent","root_identity","db_identity","journal_identity")


def _path(value):
    require(type(value) is str and 1<=len(value)<=4096 and not any(ord(x)<32 for x in value),
            "FOLDER_MAPPING_PATH")
    result=Path(value)
    require(result.is_absolute() and str(result)==value and result.name not in {"",".",".."},
            "FOLDER_MAPPING_PATH")
    return result


def _parent(path,expected=None):
    require(sys.platform=="linux","SERVER_PLATFORM_UNSUPPORTED")
    parent=path.parent
    value=parent.lstat()
    actual=(value.st_dev,value.st_ino)
    require(parent.resolve(strict=True)==parent and stat.S_ISDIR(value.st_mode)
            and value.st_uid==os.geteuid() and stat.S_IMODE(value.st_mode)==0o700
            and (expected is None or actual==tuple(expected)),"FOLDER_MAPPING_PARENT")
    filesystem_type(parent,Path("/proc/self/mountinfo").read_text())
    return list(actual)


def _shape(value):
    require(type(value) is dict and set(value)==FIELDS and type(value["schema_version"]) is int
            and value["schema_version"]==1 and value["kind"]=="FOLDER_PATH_MAPPING"
            and uuid(value["installation_id"]) and hex64(value["transition_id"]),"FOLDER_MAPPING_FRAME")
    require(all(type(value[k]) is int and 1<=value[k]<=MAX_GENERATION
                for k in ("configuration_revision","base_setup_revision")),"FOLDER_MAPPING_FRAME")
    for key in IDENTITIES:
        v=value[key]
        require(type(v) is list and len(v)==2 and all(type(x) is int and x>=0 for x in v),
                "FOLDER_MAPPING_FRAME")
    require(type(value["authority"]) is dict and set(value["authority"])=={"root_id","domain_id"},
            "FOLDER_MAPPING_FRAME")
    FolderBinding(**value["authority"])
    require(all(hex64(value[k]) for k in ("base_setup_sha256","blueprint_sha256","handle_sha256",
            "marker_sha256","store_binding")),"FOLDER_MAPPING_FRAME")
    source,target=_path(value["source_path"]),_path(value["target_path"])
    require(source!=target and source not in target.parents and target not in source.parents,
            "FOLDER_MAPPING_PATH")
    require(value["source_parent"][0]==value["target_parent"][0]==value["root_identity"][0]
            ==value["db_identity"][0]==value["journal_identity"][0],"FOLDER_MAPPING_FILESYSTEM")
    validate_pin(value["pin"])
    require(len(encoded(value))<=64*1024,"FOLDER_MAPPING_SIZE")
    return copy.deepcopy(value)


class FolderPathMapping:
    """Read only one immutable native frame and exactly two pinned paths."""
    def __init__(self,store):
        require(sys.platform=="linux" and type(store) is PrivateSettings
                and type(store.native) is LinuxSettingsNative,"FOLDER_MAPPING_STORE")
        self.store=store

    def read(self):
        current=self.store.read()
        if current is None:
            return None
        require(current.revision==1 and current.previous is None,"FOLDER_MAPPING_IMMUTABLE")
        value=_shape(current.payload)
        require(value["store_binding"]==native_binding(self.store),"FOLDER_MAPPING_BINDING")
        return value

    def select(self,expected):
        require(type(expected) is FolderConfig,"FOLDER_MAPPING_CONFIG")
        value=self.read()
        if value is None:
            expected.verify()
            return expected
        require(value["authority"]==asdict(expected.binding)
                and value["source_path"]==str(expected.root)
                and all(tuple(value[k])==getattr(expected,k) for k in
                        ("root_identity","db_identity","journal_identity")),"FOLDER_MAPPING_CONFIG")
        source,target=_path(value["source_path"]),_path(value["target_path"])
        _parent(source,value["source_parent"]);_parent(target,value["target_parent"])
        found=[]
        for path in (source,target):
            try:
                actual=identity(path)
            except FileNotFoundError:
                continue
            # An occupied contradictory location cannot be ignored.
            require(actual==expected.root_identity,"FOLDER_MAPPING_CONFLICT")
            candidate=FolderConfig(path,expected.binding,expected.root_identity,
                                   expected.db_identity,expected.journal_identity)
            candidate.verify()
            found.append(candidate)
        require(len(found)==1,"FOLDER_MAPPING_UNAVAILABLE")
        _,raw=FolderStore(found[0]).read()
        from .docs_authority import validated
        document=validated(raw,expected.binding)
        row=document["records"]["global.commissioning"]
        require(row["retention"]=="RETAINED" and digest(row["body"])==value["marker_sha256"],
                "FOLDER_MAPPING_BLUEPRINT")
        return found[0]


@dataclass(frozen=True,repr=False)
class FolderMappingContext:
    maintenance: Maintenance
    resolution: ProtectedEvidence
    mapping: FolderPathMapping
    target: Path


class FolderMappingPreparation:
    """An actual fresh C1 gate prepares lookup, never a physical operation."""
    def __init__(self,context):
        require(type(context) is FolderMappingContext and type(context.maintenance) is Maintenance
                and type(context.resolution) is ProtectedEvidence
                and type(context.mapping) is FolderPathMapping
                and type(context.target) is type(Path()) and context.target.is_absolute(),
                "FOLDER_MAPPING_CONTEXT")
        self.context=context;self.ctx=context.maintenance.context
        require(type(self.ctx.storage_port) in {FolderCommissioning,FolderMappedCommissioning}
                and type(self.ctx.checkpoint) is NativeCheckpoint and type(self.ctx.effects) is Effects,
                "FOLDER_MAPPING_CONTEXT")
        stores=[self.ctx.setup.store,self.ctx.store,self.ctx.baseline.store,
                self.ctx.checkpoint.store,self.ctx.effects.store,context.resolution.store,context.mapping.store]
        require(all(type(s) is PrivateSettings and type(s.native) is LinuxSettingsNative for s in stores)
                and len({native_binding(s) for s in stores})==len(stores),"FOLDER_MAPPING_STORE_ALIAS")
        config=self.ctx.storage_port._config()
        for s in stores:
            require(s.native.root not in {config.root,context.target}
                    and config.root not in s.native.root.parents and context.target not in s.native.root.parents,
                    "FOLDER_MAPPING_STORE_ALIAS")

    def _fresh(self):
        context=self.context
        decision=context.maintenance.require_resolved(context.resolution)
        pin=context.maintenance._proof()
        require(hashlib.sha256(pin.read(SCHEMA)).hexdigest()==SCHEMA_SHA256,"FOLDER_MAPPING_INSTRUCTIONS")
        spec,handle=storage_spec(self.ctx.setup.private_choices()["storage"])
        require(spec==self.ctx.storage_port.spec and spec.mode=="FOLDER_SQLITE_V1"
                and self.ctx.checkpoint.read().maintenance==decision.transition_id,
                "FOLDER_MAPPING_CONTEXT")
        snapshot=self.ctx.leadership.backend.read()
        current=ledger(snapshot.document()["records"][SLOT])
        require(current is not None and current.get("root_plan") is None,
                "FOLDER_MAPPING_OTHER_PLAN")
        config=self.ctx.storage_port._config();config.verify()
        source,target=config.root,self.context.target
        require(_path(str(source))==source and _path(str(target))==target and source!=target
                and source not in target.parents and target not in source.parents,"FOLDER_MAPPING_PATH")
        parents=(_parent(source),_parent(target))
        require(parents[0][0]==parents[1][0]==config.root_identity[0],"FOLDER_MAPPING_FILESYSTEM")
        require(not os.path.lexists(target),"FOLDER_MAPPING_TARGET_OCCUPIED")
        return decision,pin,spec,handle,config,parents

    def _value(self):
        decision,pin,spec,handle,config,parents=self._fresh()
        return _shape(dict(schema_version=1,kind="FOLDER_PATH_MAPPING",
            installation_id=self.ctx.setup.installation_id,transition_id=decision.transition_id,
            configuration_revision=decision.revision,base_setup_revision=self.ctx.setup.snapshot.revision,
            base_setup_sha256=decision.setup_sha256,authority=asdict(config.binding),
            source_path=str(config.root),target_path=str(self.context.target),
            source_parent=parents[0],target_parent=parents[1],
            root_identity=list(config.root_identity),db_identity=list(config.db_identity),
            journal_identity=list(config.journal_identity),blueprint_sha256=spec.fingerprint,
            handle_sha256=digest(handle.record()),marker_sha256=digest(spec.marker("STORAGE_READY")),
            store_binding=native_binding(self.context.mapping.store),pin=pin_record(pin)))

    def prepare(self,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        store=self.context.mapping.store
        require(store.read() is None,"FOLDER_MAPPING_EXISTS")
        value=self._value()
        # Revalidate actual source/current role/profile/parents immediately
        # before this local fact write. It still grants no physical send.
        require(self._value()==value,"FOLDER_MAPPING_CHANGED")
        store.save(value,expected_revision=0)
        require(self.context.mapping.read()==value,"FOLDER_MAPPING_UNCONFIRMED")
        return "LOOKUP_PREPARED"

    def recover_local(self,*,owner_authorized=False):
        require(owner_authorized is True,"CONFIGURATION_OWNER_REQUIRED")
        value=self._value()
        store=self.context.mapping.store
        with store.native.locked() as port:
            pending,raw=port.read("settings.pending"),port.read("settings.json")
            if pending is None:
                return "NO_PENDING"
            candidate=store._decode(pending,port.binding)
            require(raw is None and candidate.revision==1 and candidate.previous is None
                    and _shape(candidate.payload)==value,"FOLDER_MAPPING_RECOVERY_CONFLICT")
            port.promote()
            require(port.read("settings.json")==pending,"FOLDER_MAPPING_UNCONFIRMED")
        require(self.context.mapping.read()==value,"FOLDER_MAPPING_UNCONFIRMED")
        return "LOOKUP_PREPARED"


class FolderMappedCommissioning:
    """Fresh path selection delegates to the actual original commissioning."""
    mode="FOLDER_SQLITE_V1"
    def __init__(self,base,expected,mapping):
        require(type(base) is FolderCommissioning and type(expected) is FolderConfig
                and type(mapping) is FolderPathMapping and base.root==expected.root
                and base.root_identity==expected.root_identity and base.binding==expected.binding,
                "FOLDER_MAPPING_CONTEXT")
        self.base,self.expected,self.mapping=base,expected,mapping
        self.spec,self.root_id,self.binding,self.llm_authorized=base.spec,base.root_id,base.binding,base.llm_authorized

    def _config(self):
        return self.mapping.select(self.expected)

    def _port(self):
        config=self._config()
        return FolderCommissioning(config.root,self.spec,root_identity=config.root_identity,
                                   llm_authorized=self.llm_authorized)

    @property
    def root(self):
        return self._config().root

    def check_root(self):return self._port().check_root()
    def inspect_authority(self,spec,known):return self._port().inspect_authority(spec,known)
    def authority(self,known):
        # An already composed role must resolve the same fixed authority on
        # each request, including after a path change. No new RPC operation.
        from .folder_protocol import FolderAccess,FolderAuthority,handle as serve
        require(self.inspect_authority(self.spec,known)==known,"FOLDER_MAPPING_CONFIG")
        owner=self
        class MappedPort:
            binding=owner.binding
            def call(self,raw):return serve(FolderStore(owner._config()),raw)
        return FolderAuthority(MappedPort(),self.binding,FolderAccess(self.binding,self.llm_authorized,True))
    def inspect(self,key,allocation):return self._port().inspect(key,allocation)
