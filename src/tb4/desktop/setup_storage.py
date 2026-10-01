"""Deterministic first selection of an existing native Docs TB4 domain.

Only a trusted, already authorized Drive/Docs transport can construct this
selector. It never provisions, migrates, resets, or obtains credentials itself.
"""
from dataclasses import asdict

from tb4.drive.commissioning import SetupSpec, digest
from tb4.drive.commissioning_bootstrap import AuthorityHandle
from tb4.drive.commissioning_native import NativeCommissioning, DOC, FOLDER, FIELDS
from tb4.drive.docs_authority import AuthorityBinding, NativeDocsAuthority
from tb4.exchange_layout import encoded, validate_document
from tb4.commissioning_state import storage_spec
from tb4.commissioning_checks import CommissionedStorage
from tb4.private_settings import SettingsError, require
from .profile import drive_root_id
from .setup import StorageSelection


class ConnectedDocsSelection:
    def __init__(self, drive, docs, *, llm_authorized):
        require(llm_authorized is True, "STORAGE_UNAVAILABLE")
        self.drive,self.docs = drive,docs

    def _execute(self, request):
        result = request.execute(num_retries=0)
        require(type(result) is dict and len(encoded(result)) <= 2*1024*1024, "STORAGE_UNAVAILABLE")
        return result

    def __call__(self, choices):
        try:
            current = choices["storage"]
            if current is not None:
                spec,_ = storage_spec(current)
                require(spec.mode == "NATIVE_DOCS", "STORAGE_UNAVAILABLE")
                request = choices.get("storage_request")
                if request is not None:
                    require(request["mode"] == "NATIVE_DOCS"
                            and drive_root_id(request["location"]) == spec.root_id, "STORAGE_UNAVAILABLE")
                port=NativeCommissioning(self.drive,self.docs,spec,llm_authorized=True)
                return StorageSelection(current,CommissionedStorage(port))
            request=choices.get("storage_request")
            require(type(request) is dict and request["mode"] == "NATIVE_DOCS", "STORAGE_UNAVAILABLE")
            root=drive_root_id(request["location"])
            metadata=self._execute(self.drive.files().get(fileId=root,fields=FIELDS,supportsAllDrives=True))
            require(metadata.get("id")==root and metadata.get("mimeType")==FOLDER
                    and metadata.get("trashed") is False
                    and metadata.get("capabilities",{}).get("canEdit") is True, "STORAGE_UNAVAILABLE")
            # Bounded commissioning-only discovery in the owner-selected root.
            # Subsequent checks use the pinned exact document/tab, never scans.
            response=self._execute(self.drive.files().list(
                q=f"'{root}' in parents and trashed = false",pageSize=132,
                fields=f"files({FIELDS}),nextPageToken,incompleteSearch",
                supportsAllDrives=True,includeItemsFromAllDrives=True))
            require(not response.get("nextPageToken") and response.get("incompleteSearch") is not True
                    and type(response.get("files")) is list and len(response["files"])<=131,
                    "STORAGE_UNAVAILABLE")
            candidates=[x for x in response["files"] if type(x) is dict and
                        x.get("mimeType")==DOC and type(x.get("properties")) is dict and
                        x["properties"].get("tb4Slot")=="authority"]
            require(len(candidates)==1,"STORAGE_UNAVAILABLE")
            candidate=candidates[0]
            ref,domain=candidate["id"],candidate["properties"]["tb4Domain"]
            wire=self._execute(self.docs.documents().get(documentId=ref,includeTabsContent=True,
                                                        suggestionsViewMode="SUGGESTIONS_INLINE"))
            require(type(wire.get("tabs")) is list and len(wire["tabs"])==1,"STORAGE_UNAVAILABLE")
            tab=wire["tabs"][0]["tabProperties"]["tabId"]
            binding=AuthorityBinding(ref,tab,domain)
            document=NativeDocsAuthority(self.docs,binding)._decode(wire).document()
            marker=document["records"]["global.commissioning"]["body"]
            spec=SetupSpec(root,domain,marker["setup_id"],marker["bootstrap_actor"],
                           "NATIVE_DOCS",validate_document(document))
            handle=AuthorityHandle(ref,digest([spec.mode,root,domain,ref,tab]),tab)
            port=NativeCommissioning(self.drive,self.docs,spec,llm_authorized=True)
            record=dict(spec=asdict(spec),authority=handle.record())
            verifier=CommissionedStorage(port)
            verifier.verify(record)
            return StorageSelection(record,verifier)
        except Exception:
            raise SettingsError("STORAGE_UNAVAILABLE") from None

class BoundFolderSelection:
    """Installer-supplied server-local RP019 port; no inferred remote mount."""
    def __init__(self, port):
        self.port=port

    def __call__(self, choices):
        try:
            from pathlib import Path
            port=self.port
            request=choices.get("storage_request")
            require(port.mode=="FOLDER_SQLITE_V1", "STORAGE_UNAVAILABLE")
            if request is not None:
                require(request["mode"]==port.mode and Path(request["location"])==port.root,
                        "STORAGE_UNAVAILABLE")
            current=choices["storage"]
            known=None if current is None else storage_spec(current)[1]
            if current is not None:
                require(storage_spec(current)[0]==port.spec,"STORAGE_UNAVAILABLE")
            port.check_root()
            handle=port.inspect_authority(port.spec,known)
            require(handle is not None,"STORAGE_UNAVAILABLE")
            record=dict(spec=asdict(port.spec),authority=handle.record())
            verifier=CommissionedStorage(port)
            verifier.verify(record)
            return StorageSelection(record,verifier)
        except Exception:
            raise SettingsError("STORAGE_UNAVAILABLE") from None
