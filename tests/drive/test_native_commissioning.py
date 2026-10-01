"""Actual native Docs/Drive request construction against a synthetic atomic service."""
import copy
import json
from types import SimpleNamespace

import pytest

from tb4.drive.commissioning import SetupSpec, Commissioner
from tb4.drive.commissioning_bootstrap import Bootstrap, AuthorityHandle
from tb4.drive.commissioning_native import NativeCommissioning, DOC, BLOB, FOLDER
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.leadership import Leadership, Grant
from tb4.exchange_layout import Capacity, empty_document
from test_native_docs_transport import BINDING, DOMAIN, WireStore, wire_document, HttpError
from test_native_leadership import ACTORS, ENROLLMENT, clock, tid
from test_fixed_slot_commissioning import Journal, finish


class BootstrapJournal:
    locked=protected=True
    def __init__(self,spec,actor=ACTORS[0]):
        self.installation_id,self.setup_id,self.value=actor,spec.setup_id,None
    def read(self):return copy.deepcopy(self.value)
    def save(self,value):self.value=copy.deepcopy(value)


class Provider:
    def __init__(self,spec):
        self.spec=spec
        self.store=WireStore(empty_document(DOMAIN,spec.capacity))
        self.blank=True;self.created=[];self.calls=[]
        self.lost_create=self.lost_seed=self.before_create=False
        self.metadata={spec.root_id:dict(id=spec.root_id,mimeType=FOLDER,trashed=False,
                                        capabilities=dict(canEdit=True))}
        self.store.on_read=lambda _,v:wire_document(self.store.document,v["revisionId"],text="\n") if self.blank else v
        self.base=self.store.client()
        self.extra_list={}
        self.counter=0

    def request(self,method,kwargs,work):
        def execute(*,num_retries):
            assert num_retries==0
            self.calls.append((method,copy.deepcopy(kwargs)))
            return work()
        return SimpleNamespace(execute=execute)

    def files(self):return self

    def get(self,**kwargs):
        assert set(kwargs)=={"fileId","fields","supportsAllDrives"} and kwargs["supportsAllDrives"] is True
        def run():
            if kwargs["fileId"] not in self.metadata:raise HttpError(404)
            return copy.deepcopy(self.metadata[kwargs["fileId"]])
        return self.request("files.get",kwargs,run)

    def list(self,**kwargs):
        assert kwargs["q"]==f"'{self.spec.root_id}' in parents and trashed = false"
        assert kwargs["pageSize"]==132 and kwargs["includeItemsFromAllDrives"] is True
        return self.request("files.list",kwargs,lambda:dict(files=[copy.deepcopy(v) for k,v in self.metadata.items()
                                                        if k!=self.spec.root_id],**self.extra_list))

    def generateIds(self,**kwargs):
        assert kwargs==dict(count=1,space="drive",type="files")
        def run():
            self.counter+=1
            return dict(ids=[f"raw-{self.counter:03d}"],space="drive")
        return self.request("files.generateIds",kwargs,run)

    def create(self,**kwargs):
        assert set(kwargs)=={"body","fields","supportsAllDrives"}
        body=kwargs["body"]
        def run():
            if self.before_create:raise TimeoutError("SYNTHETIC_PRIVATE_CANARY")
            ref=BINDING.document_id if body["mimeType"]==DOC else body["id"]
            if ref in self.metadata:raise RuntimeError("synthetic conflict")
            assert body["parents"]==[self.spec.root_id]
            if body["mimeType"]==DOC:assert "id" not in body
            else:assert body["mimeType"]==BLOB and "id" in body
            self.metadata[ref]={**body,"id":ref,"trashed":False,"capabilities":{"canEdit":True}}
            if body["mimeType"]==BLOB:self.metadata[ref]["size"]="0"
            self.created.append(ref)
            if self.lost_create:raise TimeoutError("SYNTHETIC_PRIVATE_CANARY")
            return copy.deepcopy(self.metadata[ref])
        return self.request("files.create",kwargs,run)

    def documents(self):
        provider=self
        class Documents:
            def get(self,**kwargs):return provider.base.documents().get(**kwargs)
            def batchUpdate(self,**kwargs):
                requests=kwargs["body"]["requests"]
                if len(requests)!=1:return provider.base.documents().batchUpdate(**kwargs)
                def run():
                    assert kwargs["documentId"]==BINDING.document_id
                    assert kwargs["body"]["writeControl"]==dict(requiredRevisionId=f"opaque-a-{provider.store.revision}")
                    assert requests[0]["insertText"]["location"]==dict(tabId=BINDING.tab_id,index=1)
                    assert provider.blank
                    provider.store.document=json.loads(requests[0]["insertText"]["text"])
                    provider.store.bump();provider.blank=False
                    if provider.lost_seed:raise TimeoutError("SYNTHETIC_PRIVATE_CANARY")
                    return dict(documentId=BINDING.document_id)
                return provider.request("documents.seed",kwargs,run)
        return Documents()


def system():
    spec=SetupSpec("synthetic-root",DOMAIN,tid("native-setup"),ACTORS[0],"NATIVE_DOCS",Capacity(1,1,1,1))
    provider=Provider(spec)
    port=NativeCommissioning(provider,provider,spec,llm_authorized=True)
    journal=BootstrapJournal(spec)
    bootstrap=Bootstrap(spec,port,journal,owner_authorized=True)
    return spec,provider,port,journal,bootstrap


def seed(bootstrap):
    for _ in range(8):
        state=bootstrap.advance(computer_name=ENROLLMENT[ACTORS[0]],clock=clock())
        if state=="AUTHORITY_READY":return
        assert state in {"INSPECT_REQUIRED","PROGRESS"}
    pytest.fail("Bootstrap did not finish")


def test_native_complete_bootstrap_and_allocation_with_exact_request_bodies():
    spec,provider,port,journal,bootstrap=system()
    seed(bootstrap)
    handle=AuthorityHandle.parse(journal.read()["handle"])
    leader=Leadership(port.authority(handle),actor=ACTORS[0],enrollment=ENROLLMENT)
    grant=bootstrap.initial_grant(leader,clock())
    assert leader.current_before_dispatch(grant,clock())
    c=Commissioner(spec,leader,grant,port,Journal(spec,ACTORS[0]))
    finish(c)
    assert len(provider.created)==3
    assert sum(name=="documents.seed" for name,_ in provider.calls)==1
    assert sum(name=="files.generateIds" for name,_ in provider.calls)==2
    before=copy.deepcopy(provider.created)
    seed(bootstrap)
    assert c.advance(clock())=="STORAGE_READY" and provider.created==before
    # Ordinary role transitions on the commissioned authority must not use the
    # creation port. A real provider creation call now fails instrumentation.
    provider.before_create=True
    renewal=leader.renew(leader.observe(clock(101)),grant,transition=tid("renew"))
    assert leader.commit(renewal,mode="START").outcome=="CONFIRMED"
    assert provider.created==before


@pytest.mark.parametrize("failure",["create-after","create-before","seed-after"])
def test_native_unknown_never_repeats_a_possibly_applied_request(failure):
    _,provider,_,journal,bootstrap=system()
    if failure=="create-after":provider.lost_create=True
    if failure=="create-before":provider.before_create=True
    if failure=="seed-after":provider.lost_seed=True
    if failure.startswith("create"):
        assert bootstrap.advance(computer_name="synthetic",clock=clock())=="UNKNOWN"
        assert journal.read()["phase"]=="UNKNOWN"
        provider.lost_create=provider.before_create=False
        if failure=="create-before":
            for _ in range(3):
                assert bootstrap.advance(computer_name="synthetic",clock=clock())=="UNKNOWN"
            assert not provider.created
            assert sum(n=="files.create" for n,_ in provider.calls)==1
            return
    for _ in range(8):
        result=bootstrap.advance(computer_name="synthetic",clock=clock())
        if result=="AUTHORITY_READY":break
        assert result in {"PROGRESS","INSPECT_REQUIRED","UNKNOWN"}
    assert result=="AUTHORITY_READY" and len(provider.created)==1
    assert sum(n=="files.create" for n,_ in provider.calls)==1
    assert sum(n=="documents.seed" for n,_ in provider.calls)==1


@pytest.mark.parametrize("case",["standby","unauthorized","llm-missing","foreign-root","pagination","duplicate"])
def test_native_initial_authority_refuses_ambiguous_or_unauthorized_setup(case):
    spec,provider,port,journal,bootstrap=system()
    if case=="standby":
        with pytest.raises(AuthorityError):Bootstrap(spec,port,BootstrapJournal(spec,ACTORS[1]),owner_authorized=True)
    elif case=="unauthorized":
        with pytest.raises(AuthorityError):Bootstrap(spec,port,journal,owner_authorized=False)
    elif case=="llm-missing":
        with pytest.raises(AuthorityError):NativeCommissioning(provider,provider,spec,llm_authorized=False)
    else:
        if case=="foreign-root":
            provider.metadata["foreign"]={"id":"foreign","mimeType":DOC,"properties":{}}
        if case=="pagination":provider.extra_list["nextPageToken"]="synthetic"
        if case=="duplicate":
            seed(bootstrap)
            duplicate=copy.deepcopy(provider.metadata[BINDING.document_id]);duplicate["id"]="duplicate"
            provider.metadata["duplicate"]=duplicate
            journal.value=None  # Simulate unavailable local navigation, not a resend.
        with pytest.raises(AuthorityError):
            bootstrap.advance(computer_name="synthetic",clock=clock())
    assert len(provider.created)==(1 if case=="duplicate" else 0)


@pytest.mark.parametrize("field,value",[("capabilities",None),("properties",None),("parents",["foreign"]),
    ("mimeType",FOLDER),("size",str(8*1024*1024+1)),("trashed",True)])
def test_raw_metadata_is_not_trusted_or_replaced(field,value):
    spec,provider,port,_,bootstrap=system()
    seed(bootstrap)
    key=spec.artifact_keys[0]
    allocation=port.prepare(key,spec.operation(key))
    port.create(key,allocation)
    provider.metadata[allocation.object_id][field]=value
    with pytest.raises(AuthorityError):port.inspect(key,allocation)
    assert len(provider.created)==2

def test_missing_pinned_authority_or_raw_file_is_inspect_only():
    spec,provider,port,journal,bootstrap=system()
    seed(bootstrap)
    key=spec.artifact_keys[0]
    allocation=port.prepare(key,spec.operation(key))
    assert port.inspect(key,allocation) is None
    del provider.metadata[BINDING.document_id]
    for _ in range(3):
        assert bootstrap.advance(computer_name="synthetic",clock=clock())=="UNKNOWN"
    assert len(provider.created)==1

def test_completed_bootstrap_cannot_restore_superseded_grant():
    spec,provider,port,journal,bootstrap=system()
    seed(bootstrap)
    handle=AuthorityHandle.parse(journal.read()["handle"])
    original=Leadership(port.authority(handle),actor=ACTORS[0],enrollment=ENROLLMENT)
    successor=Leadership(port.authority(handle),actor=ACTORS[1],enrollment=ENROLLMENT)
    plan=successor.acquire(successor.observe(clock(220)),transition=tid("successor"))
    assert successor.commit(plan,mode="START").outcome=="CONFIRMED"
    with pytest.raises(AuthorityError,match="OWNER_SUPERSEDED"):bootstrap.initial_grant(original,clock(220))
    assert len(provider.created)==1
