"""Commissioning-only Google request adapter; no credentials or normal creation.

Injected Drive/Docs SDK transports must provide qualified credentials, bounded
response bytes/time and no lower-layer mutation retries. No raw provider error is
returned. Native Docs creation uses an exact operation marker, not a guessed ID.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, replace

from tb4.exchange_layout import encoded
from .commissioning import Allocation, RAW_LIMIT, digest, object_id
from .commissioning_bootstrap import AuthorityHandle
from .docs_authority import AuthorityBinding, AuthorityError, NativeDocsAuthority, require, units

DOC = "application/vnd.google-apps.document"
BLOB = "application/octet-stream"
FOLDER = "application/vnd.google-apps.folder"
FIELDS = "id,mimeType,parents,trashed,properties,size,capabilities(canEdit)"


class NativeCommissioning:
    mode = "NATIVE_DOCS"

    def __init__(self, drive, docs, spec, *, llm_authorized):
        require(spec.mode==self.mode and llm_authorized is True,"SETUP_ACCESS")
        self.drive,self.docs,self.spec=drive,docs,spec
        self.root_id,self.llm_authorized=spec.root_id,llm_authorized

    def _execute(self,request,limit=2*1024*1024,*,missing_ok=False):
        try:
            result=request.execute(num_retries=0)
            require(type(result) is dict and len(encoded(result))<=limit,"SETUP_PROVIDER_RESPONSE")
            return result
        except Exception as exc:
            if missing_ok and getattr(getattr(exc,"resp",None),"status",None)==404:
                return None
            raise AuthorityError("SETUP_PROVIDER_UNAVAILABLE") from None

    def _props(self,key,op):
        return dict(tb4Domain=self.spec.domain_id,tb4Setup=self.spec.setup_id,tb4Slot=key,tb4Operation=op)

    def _metadata(self,ref,*,missing_ok=False):
        require(object_id(ref),"SETUP_OBJECT")
        return self._execute(self.drive.files().get(fileId=ref,fields=FIELDS,supportsAllDrives=True),
                             missing_ok=missing_ok)

    def check_root(self):
        value=self._metadata(self.root_id)
        require(value.get("id")==self.root_id and value.get("mimeType")==FOLDER
                and value.get("trashed") is False and type(value.get("capabilities")) is dict
                and value["capabilities"].get("canEdit") is True,
                "SETUP_ROOT")

    def _verify(self,value,key,ref=None):
        mime=DOC if key=="authority" else BLOB
        require(type(value) is dict and object_id(value.get("id")) and (ref is None or value["id"]==ref)
                and value.get("mimeType")==mime and value.get("parents")==[self.root_id]
                and value.get("trashed") is False and value.get("properties")==self._props(key,self.spec.operation(key))
                and type(value.get("capabilities")) is dict
                and value["capabilities"].get("canEdit") is True,"SETUP_OBJECT_BINDING")
        if key!="authority":
            size=value.get("size")
            require(type(size) is str and size.isascii() and size.isdecimal()
                    and len(size)<=8 and int(size)<=RAW_LIMIT,"SETUP_ARTIFACT_SIZE")
        return value["id"]

    def _document(self,ref):
        return self._execute(self.docs.documents().get(documentId=ref,includeTabsContent=True,
                          suggestionsViewMode="SUGGESTIONS_INLINE"))

    def _handle(self,ref):
        value=self._document(ref)
        require(value.get("documentId")==ref and type(value.get("tabs")) is list
                and len(value["tabs"])==1,"SETUP_DOCUMENT")
        tab=value["tabs"][0]
        require(type(tab) is dict and not tab.get("childTabs"),"SETUP_DOCUMENT")
        require(type(tab.get("tabProperties")) is dict,"SETUP_DOCUMENT")
        tab_id=tab["tabProperties"].get("tabId")
        require(object_id(tab_id),"SETUP_DOCUMENT")
        return AuthorityHandle(ref,digest([self.mode,self.root_id,self.spec.domain_id,ref,tab_id]),tab_id)

    def inspect_authority(self,spec,known):
        require(spec==self.spec,"SETUP_SPEC")
        if known is not None:
            value=self._metadata(known.object_id,missing_ok=True)
            if value is None:return None
            self._verify(value,"authority",known.object_id)
            found=self._handle(known.object_id)
            require(found==known,"BOOTSTRAP_HANDLE_CHANGED")
            return found
        # Initial commissioning only. An unmarked/foreign nonempty root is not
        # silently adopted as a fresh TB4 domain or migrated.
        response=self._execute(self.drive.files().list(
            q=f"'{self.root_id}' in parents and trashed = false",pageSize=132,
            fields=f"files({FIELDS}),nextPageToken,incompleteSearch",
            supportsAllDrives=True,includeItemsFromAllDrives=True))
        require(not response.get("nextPageToken") and response.get("incompleteSearch") is not True
                and type(response.get("files")) is list and len(response["files"])<=131,
                "SETUP_ROOT_AMBIGUOUS")
        authorities=[]
        seen_keys,seen_ids=set(),set()
        for value in response["files"]:
            require(type(value) is dict and type(value.get("properties")) is dict,"SETUP_ROOT_FOREIGN")
            key=value["properties"].get("tb4Slot")
            require(key in ("authority",)+self.spec.artifact_keys,"SETUP_ROOT_FOREIGN")
            ref=self._verify(value,key)
            require(key not in seen_keys and ref not in seen_ids,"SETUP_ROOT_AMBIGUOUS")
            seen_keys.add(key);seen_ids.add(ref)
            if key=="authority":authorities.append(ref)
        require(len(authorities)<=1,"SETUP_ROOT_AMBIGUOUS")
        require(authorities or not response["files"],"SETUP_AUTHORITY_MISSING")
        return self._handle(authorities[0]) if authorities else None

    def create_authority(self,spec):
        require(spec==self.spec,"SETUP_SPEC")
        self.check_root()
        # Called once, only after durable UNKNOWN. Google Workspace IDs cannot
        # be supplied from generateIds. Properties travel in the same request.
        value=self._execute(self.drive.files().create(body=dict(
            name="TB4 authority",mimeType=DOC,parents=[self.root_id],
            properties=self._props("authority",spec.operation("authority"))),
            fields=FIELDS,supportsAllDrives=True))
        ref=self._verify(value,"authority")
        return self._handle(ref)

    def _binding(self,handle):
        require(type(handle) is AuthorityHandle and handle.tab_id is not None,"BOOTSTRAP_HANDLE")
        return AuthorityBinding(handle.object_id,handle.tab_id,self.spec.domain_id)

    def authority(self,handle):
        return NativeDocsAuthority(self.docs,self._binding(handle))

    def _blank_revision(self,response,handle,seed):
        # Reuse the qualified rich-structure validator after checking that the
        # actual original paragraph is exactly one terminal newline. The cooked
        # copy is only structural validation, never evidence of a committed seed.
        try:
            require(response.get("documentId")==handle.object_id,"SETUP_DOCUMENT")
            para=response["tabs"][0]["documentTab"]["body"]["content"][1]
            require(para["startIndex"]==1 and para["endIndex"]==2,"SETUP_NOT_BLANK")
            elements=para["paragraph"]["elements"]
            require(len(elements)==1 and elements[0]["startIndex"]==1 and elements[0]["endIndex"]==2
                    and elements[0]["textRun"]["content"]=="\n","SETUP_NOT_BLANK")
            cooked=copy.deepcopy(response)
            paragraph=cooked["tabs"][0]["documentTab"]["body"]["content"][1]
            end=units(seed.decode("utf-8"))+2
            paragraph["endIndex"]=end
            paragraph["paragraph"]["elements"][0]["endIndex"]=end
            paragraph["paragraph"]["elements"][0]["textRun"]["content"]=seed.decode("utf-8")+"\n"
            observed=self.authority(handle)._decode(cooked)
            return observed.revision
        except (KeyError,IndexError,TypeError):
            raise AuthorityError("SETUP_DOCUMENT") from None

    def inspect_seed(self,spec,handle):
        require(spec==self.spec,"SETUP_SPEC")
        response=self._document(handle.object_id)
        try:
            snapshot=self.authority(handle)._decode(response)
        except AuthorityError:
            # A canonical synthetic seed is used only to validate blank shape.
            from .commissioning import seed_document
            from .leadership import ClockSample
            probe=seed_document(spec,"synthetic-structure-check",ClockSample(0,0,True))
            self._blank_revision(response,handle,probe)
            return False
        document=snapshot.document()
        marker=document["records"]["global.commissioning"]
        phase=marker["body"].get("state") if type(marker["body"]) is dict else None
        require(document["capacity"]==asdict(spec.capacity)
                and phase in {"PREPARING","STORAGE_READY"} and marker["body"]==spec.marker(phase)
                and marker["operation_id"]==spec.setup_id and marker["retention"]=="RETAINED",
                "SETUP_SEED_CONFLICT")
        return True

    def seed(self,spec,handle,raw):
        require(spec==self.spec,"SETUP_SPEC")
        from .docs_authority import validated
        validated(raw,self._binding(handle))
        response=self._document(handle.object_id)
        revision=self._blank_revision(response,handle,raw)
        self._execute(self.docs.documents().batchUpdate(documentId=handle.object_id,body=dict(
            writeControl=dict(requiredRevisionId=revision),requests=[
                dict(insertText=dict(location=dict(tabId=handle.tab_id,index=1),text=raw.decode("utf-8")))])))

    def prepare(self,key,op):
        require(key in self.spec.artifact_keys and op==self.spec.operation(key),"ALLOCATION")
        value=self._execute(self.drive.files().generateIds(count=1,space="drive",type="files"))
        require(type(value.get("ids")) is list and len(value["ids"])==1
                and value.get("space")=="drive","ALLOCATION")
        return Allocation(value["ids"][0],op)

    def create(self,key,allocation):
        require(key in self.spec.artifact_keys and type(allocation) is Allocation
                and allocation.operation_id==self.spec.operation(key) and allocation.seal is None,"ALLOCATION")
        self.check_root()
        value=self._execute(self.drive.files().create(body=dict(
            id=allocation.object_id,name=key,mimeType=BLOB,parents=[self.root_id],
            properties=self._props(key,allocation.operation_id)),fields=FIELDS,supportsAllDrives=True))
        self._verify(value,key,allocation.object_id)

    def inspect(self,key,allocation):
        require(key in self.spec.artifact_keys and type(allocation) is Allocation
                and allocation.operation_id==self.spec.operation(key),"ALLOCATION")
        value=self._metadata(allocation.object_id,missing_ok=True)
        if value is None:return None
        self._verify(value,key,allocation.object_id)
        # A Google file ID is never reused for another object. Contents/version
        # can change in the same allocated slot during later artifact operation.
        seal=digest([self.mode,self.root_id,self.spec.domain_id,allocation.object_id,allocation.operation_id])
        require(allocation.seal is None or allocation.seal==seal,"ALLOCATION_IDENTITY")
        return replace(allocation,seal=seal)
