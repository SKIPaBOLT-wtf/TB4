"""Synthetic service/request conformance. No credentials, network or processes."""
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from tb4.command_contract import binding, compact_record, make_result, operation_id, pack_record
from tb4.drive.docs_authority import (AuthorityBinding, AuthorityError, NativeDocsAuthority,
                                      WriteResult, document_bytes, units)
from tb4.drive.authority_transaction import OwnerGuard, RecordMutation, reconcile, terminal_publication
from tb4.exchange_layout import Capacity, empty_document, empty_record, encoded


DOMAIN = "10000000-0000-4000-8000-000000000001"
TARGET = "20000000-0000-4000-8000-000000000001"
BINDING = AuthorityBinding("synthetic-doc", "synthetic-tab", DOMAIN)
OWNER = OwnerGuard("synthetic-owner", 3)


def fixture_document():
    document = empty_document(DOMAIN, Capacity(1, 1, 1, 1))
    rows = document["records"]
    rows["global.leadership"] = dict(generation=3, operation_id="synthetic-claim",
        retention="BUSY", body=dict(owner=OWNER.owner, epoch=3, phase="ACTIVE", heartbeat=4))
    text = "print('synthetic')"
    request = dict(domain_id=DOMAIN, target_id=TARGET, operation_id=operation_id(DOMAIN,TARGET,7),
        generation=7, protocol_major=2, protocol_minor=0,
        payload_sha256=hashlib.sha256(text.encode()).hexdigest(), kind="SUBMIT",
        given_at=100, claim_deadline=150, run_limit_s=10,
        payload=dict(kind="INLINE",interpreter="python",size_bytes=len(text),text=text))
    result = make_result(request, stdout_tail="synthetic result")
    status = dict(binding=binding(request), receipt="ADMITTED", execution="EXITED", publication="PENDING",
        consumption="NOT_READY", stage="RETURNING", responsible="FETCHER", stage_at=110,
        last_progress_at=110, wait_reason="PUBLICATION", next_check_at=115, deadline_at=None,
        terminal=False, result_sha256=result["result_sha256"])
    rows["target.000.work"] = pack_record("target.000.work",request)
    rows["target.000.result"] = compact_record("result",result,binding(request),0)
    rows["target.000.status"] = compact_record("status_projection",status,binding(request),0)
    return document, request, result


def wire_document(document, revision="opaque-a-1", text=None):
    text = document_bytes(document).decode() + "\n" if text is None else text
    end = 1+units(text)
    paragraph = dict(startIndex=1,endIndex=end,paragraph=dict(elements=[
        dict(startIndex=1,endIndex=end,textRun=dict(content=text))]))
    tab = dict(tabProperties=dict(tabId=BINDING.tab_id), documentTab=dict(body=dict(
        content=[dict(endIndex=1,sectionBreak={}), paragraph])))
    return dict(documentId=BINDING.document_id, revisionId=revision, tabs=[tab])


class HttpError(Exception):
    def __init__(self, status):
        self.resp = SimpleNamespace(status=status)
        super().__init__("SYNTHETIC_PROVIDER_MESSAGE_NOT_FOR_PUBLIC_ERRORS")


class WireStore:
    def __init__(self, document):
        self.document, self.revision = copy.deepcopy(document), 1
        self.calls, self.commits, self.reads = [], 0, 0
        self.before_write = None
        self.after_write = None
        self.on_read = None
        self.response_filter = None
        self.raise_write = None

    def bump(self): self.revision += 1

    def client(self, caller="a"):
        store = self
        class Service:
            def documents(self): return self
            def get(self, **kwargs):
                assert kwargs == dict(documentId=BINDING.document_id, includeTabsContent=True,
                                     suggestionsViewMode="SUGGESTIONS_INLINE")
                def execute(*, num_retries):
                    assert num_retries == 0
                    store.reads += 1
                    response = wire_document(store.document,f"opaque-{caller}-{store.revision}")
                    if store.on_read: response = store.on_read(store.reads,response)
                    return response
                return SimpleNamespace(execute=execute)
            def batchUpdate(self, **kwargs):
                def execute(*, num_retries):
                    assert num_retries == 0
                    store.calls.append(copy.deepcopy(kwargs))
                    if store.before_write: store.before_write(len(store.calls))
                    if store.raise_write: raise HttpError(store.raise_write)
                    assert kwargs["documentId"] == BINDING.document_id
                    body = kwargs["body"]
                    assert set(body) == {"requests", "writeControl"}
                    assert set(body["writeControl"]) == {"requiredRevisionId"}
                    if body["writeControl"]["requiredRevisionId"] != f"opaque-{caller}-{store.revision}":
                        raise HttpError(400)
                    # Validate the WHOLE batch before mutating. No partial delete.
                    delete, insert = body["requests"]
                    assert delete == {"deleteContentRange":{"range":dict(tabId=BINDING.tab_id,
                        startIndex=1,endIndex=1+units(document_bytes(store.document).decode()))}}
                    assert insert["insertText"]["location"] == dict(tabId=BINDING.tab_id,index=1)
                    text = insert["insertText"]["text"]
                    assert not text.endswith("\n")
                    new = json.loads(text)
                    store.document = new
                    store.bump(); store.commits += 1
                    if store.after_write: store.after_write()
                    response = dict(documentId=BINDING.document_id,
                        writeControl=dict(requiredRevisionId=f"opaque-{caller}-{store.revision}"))
                    return store.response_filter(response) if store.response_filter else response
                return SimpleNamespace(execute=execute)
        return Service()


class MemoryAuthority:
    """Independent atomic model for the shared reconciler suite, not a backend option."""
    def __init__(self, store): self.store, self.origin = store, object()
    def read(self):
        store = self.store
        store.reads += 1
        response = wire_document(store.document,f"opaque-a-{store.revision}")
        if store.on_read: response = store.on_read(store.reads,response)
        # Share only the wire reader validation, not request mutation implementation.
        reader = NativeDocsAuthority(None,BINDING)
        return reader._decode(response)
    def compare_replace(self,snapshot,desired):
        store = self.store
        store.calls.append({"expected":snapshot.revision})
        if store.before_write: store.before_write(len(store.calls))
        if snapshot.revision != f"opaque-a-{store.revision}": return WriteResult.REJECTED
        store.document = copy.deepcopy(desired)
        store.bump(); store.commits += 1
        try:
            if store.after_write: store.after_write()
        except TimeoutError:
            return WriteResult.UNKNOWN
        return WriteResult.ACCEPTED


@pytest.fixture(params=["wire","atomic-model"])
def system(request):
    document, command, result = fixture_document()
    store = WireStore(document)
    backend = NativeDocsAuthority(store.client(),BINDING) if request.param=="wire" else MemoryAuthority(store)
    snapshot = backend.read()
    plan = terminal_publication(snapshot,target_index=0,expected_binding=binding(command),
                                result_sha256=result["result_sha256"],owner=OWNER,now=111)
    return store, backend, plan, snapshot


def test_success_and_idempotent_same_operation_require_full_readback(system):
    store,backend,plan,_ = system
    first = reconcile(backend,plan,mode="START")
    assert (first.outcome,first.reads,first.writes)==("CONFIRMED",2,1)
    second = reconcile(backend,plan,mode="START")
    assert (second.outcome,second.reads,second.writes)==("CONFIRMED",1,0)
    assert not first.execution_authorized and store.commits==1
    assert store.document["records"]["target.000.result"]["retention"]=="UNREAD"
    assert store.document["records"]["target.000.status"]["body"]["stage"]=="AWAITING_CONSUMPTION"


def test_required_invariant_same_owner_benign_metadata_change_does_not_strand_result(system):
    store,backend,plan,_ = system
    original = copy.deepcopy(store.document["records"]["target.000.result"]["body"])
    store.before_write = lambda count: store.bump() if count==1 else None
    outcome = reconcile(backend,plan,mode="START")
    assert (outcome.outcome,outcome.writes,store.commits)==("CONFIRMED",2,1)
    assert store.document["records"]["target.000.result"]["body"]==original


@pytest.mark.parametrize("change",["heartbeat","unrelated-record"])
def test_fresh_retry_preserves_unrelated_updates_and_same_owner(system,change):
    store,backend,plan,_ = system
    def change_once(count):
        if count!=1: return
        if change=="heartbeat": store.document["records"]["global.leadership"]["body"]["heartbeat"]+=1
        else: store.document["records"]["global.summary"]=dict(generation=1,operation_id="s",retention="RETAINED",body={"value":"keep"})
        store.bump()
    store.before_write=change_once
    assert reconcile(backend,plan,mode="START").outcome=="CONFIRMED"
    rows=store.document["records"]
    assert rows["global.leadership"]["body"]["heartbeat"]== (5 if change=="heartbeat" else 4)
    if change=="unrelated-record": assert rows["global.summary"]["body"]=={"value":"keep"}


@pytest.mark.parametrize("change",["owner","epoch","force-request","work","result","status"])
def test_changes_between_check_and_atomic_write_are_never_overwritten(system,change):
    store,backend,plan,_=system
    def competing(count):
        if count!=1:return
        rows=store.document["records"]
        if change=="owner": rows["global.leadership"]["body"]["owner"]="other"
        elif change=="epoch": rows["global.leadership"]["generation"]=4; rows["global.leadership"]["body"]["epoch"]=4
        elif change=="force-request": rows["global.force_request"]=dict(generation=1,operation_id="request",retention="BUSY",body={"requester":"other"})
        elif change=="work": rows["target.000.work"]["generation"]=8
        elif change=="result": rows["target.000.result"]["body"]["stdout_tail"]="foreign result"
        else: rows["target.000.status"]["body"]["stage"]="READY"
        store.bump()
    store.before_write=competing
    outcome=reconcile(backend,plan,mode="START")
    assert outcome.outcome==("SUPERSEDED" if change in {"owner","epoch","force-request"} else "CONFLICT")
    assert outcome.writes==1 and store.commits==0


def test_repeated_contention_is_bounded_and_never_executes_payload(system):
    store,backend,plan,_=system
    store.before_write=lambda _:store.bump()
    outcome=reconcile(backend,plan,mode="START",max_writes=3,max_reads=6)
    assert (outcome.outcome,outcome.writes,outcome.reads)==("CONFLICT",3,4)
    assert store.commits==0 and not outcome.execution_authorized


@pytest.mark.parametrize("lost",[False,True])
def test_success_or_lost_reply_with_delayed_readback_never_rewrites(system,lost):
    store,backend,plan,_=system
    old=wire_document(store.document,"opaque-a-1")
    def after():
        if lost:raise TimeoutError("synthetic response loss")
    store.after_write=after
    # Fixture read1, reconciliation read2, readback3/4 stale, read5 current.
    store.on_read=lambda count,response:copy.deepcopy(old) if count in {3,4} else response
    outcome=reconcile(backend,plan,mode="START")
    assert (outcome.outcome,outcome.writes,outcome.reads)==("CONFIRMED",1,4)
    assert store.commits==1


def test_unknown_outcome_only_inspects_and_recovers_same_transition(system):
    store,backend,plan,_=system
    old=wire_document(store.document,"opaque-a-1")
    store.after_write=lambda:(_ for _ in ()).throw(TimeoutError())
    store.on_read=lambda count,response:copy.deepcopy(old) if count>=3 else response
    first=reconcile(backend,plan,mode="START",max_reads=3)
    assert first.outcome=="UNKNOWN" and first.inspect_required and first.writes==1
    store.on_read=None
    second=reconcile(backend,plan,mode="INSPECT")
    assert second.outcome=="CONFIRMED" and second.writes==0 and store.commits==1


def test_inspect_mode_never_treats_absence_as_permission_to_replay(system):
    store,backend,plan,_=system
    outcome=reconcile(backend,plan,mode="INSPECT",max_reads=3)
    assert outcome.outcome=="UNKNOWN" and outcome.inspect_required
    assert outcome.writes==0 and not store.calls


def test_new_metadata_revision_after_applied_write_does_not_invalidate_readback(system):
    store,backend,plan,_=system
    store.after_write=store.bump
    assert reconcile(backend,plan,mode="START").outcome=="CONFIRMED"
    assert store.commits==1 and len(store.calls)==1


def test_applied_but_superseded_before_readback_does_not_authorize_work(system):
    store,backend,plan,_=system
    def supersede():
        store.document["records"]["global.leadership"]["body"]["owner"]="other"
        store.bump()
    store.after_write=supersede
    outcome=reconcile(backend,plan,mode="START")
    assert outcome.outcome=="SUPERSEDED" and outcome.inspect_required and not outcome.execution_authorized
    assert store.commits==1


def test_doc_indices_are_utf16_and_terminal_newline_is_preserved():
    document,_,_=fixture_document()
    document["records"]["global.summary"]=dict(generation=1,operation_id="s",retention="RETAINED",body={"text":"synthetic \U0001f436"})
    store=WireStore(document);backend=NativeDocsAuthority(store.client(),BINDING)
    snapshot=backend.read();desired=snapshot.document();desired["records"]["global.summary"]["body"]["text"]="changed \U0001f436"
    assert backend.compare_replace(snapshot,desired)==WriteResult.ACCEPTED
    request=store.calls[0]["body"]
    assert request["requests"][0]["deleteContentRange"]["range"]["endIndex"]==len(snapshot.raw.decode())+2
    assert request["writeControl"]=={"requiredRevisionId":"opaque-a-1"}
    assert backend.read().document()==desired


def test_principal_specific_revision_is_read_locally_and_never_compared_as_epoch():
    document,_,_=fixture_document();store=WireStore(document)
    a=NativeDocsAuthority(store.client("a"),BINDING);b=NativeDocsAuthority(store.client("b"),BINDING)
    sa,sb=a.read(),b.read()
    assert sa.revision!=sb.revision
    desired=sb.document();desired["records"]["global.leadership"]["body"]["heartbeat"]+=1
    with pytest.raises(AuthorityError,match="SNAPSHOT_ORIGIN"): a.compare_replace(sb,desired)
    assert b.compare_replace(sb,desired)==WriteResult.ACCEPTED
    assert a.compare_replace(sa,desired)==WriteResult.REJECTED


@pytest.mark.parametrize("status,expected",[(400,"REJECTED"),(409,"REJECTED"),(412,"REJECTED"),
    (401,"UNAVAILABLE"),(403,"UNAVAILABLE"),(404,"UNAVAILABLE"),(429,"UNKNOWN"),(500,"UNKNOWN"),(503,"UNKNOWN")])
def test_provider_errors_are_closed_and_never_expose_raw_message(status,expected):
    document,_,_=fixture_document();store=WireStore(document);backend=NativeDocsAuthority(store.client(),BINDING)
    snapshot=backend.read();store.raise_write=status
    assert backend.compare_replace(snapshot,snapshot.document()).value==expected
    assert store.commits==0 and len(store.calls)==1


def test_unchanged_revision_after_generic_400_is_not_misdiagnosed_as_race():
    document,command,result=fixture_document();store=WireStore(document);backend=NativeDocsAuthority(store.client(),BINDING)
    plan=terminal_publication(backend.read(),target_index=0,expected_binding=binding(command),result_sha256=result["result_sha256"],owner=OWNER,now=111)
    store.raise_write=400
    outcome=reconcile(backend,plan,mode="START")
    assert outcome.outcome=="REJECTED" and outcome.writes==1 and store.commits==0


def test_failed_atomic_batch_never_exposes_deleted_control_or_requires_final_rename():
    document,command,result=fixture_document();store=WireStore(document);backend=NativeDocsAuthority(store.client(),BINDING)
    plan=terminal_publication(backend.read(),target_index=0,expected_binding=binding(command),result_sha256=result["result_sha256"],owner=OWNER,now=111)
    store.raise_write=400
    assert reconcile(backend,plan,mode="START").outcome=="REJECTED"
    assert store.document==document and store.commits==0
    assert len(store.calls[0]["body"]["requests"])==2
    assert "rename" not in json.dumps(store.calls)


@pytest.mark.parametrize("bad",["wrong-document","wrong-tab","second-tab","missing-revision","table",
    "suggestion","wrong-index","no-newline","extra-newline","wrong-domain","duplicate-key","noncanonical","surrogate","oversize"])
def test_malformed_or_human_edited_control_is_rejected_without_write(bad):
    document,_,_=fixture_document();response=wire_document(document)
    para=response["tabs"][0]["documentTab"]["body"]["content"][1]
    if bad=="wrong-document":response["documentId"]="wrong"
    elif bad=="wrong-tab":response["tabs"][0]["tabProperties"]["tabId"]="wrong"
    elif bad=="second-tab":response["tabs"].append(copy.deepcopy(response["tabs"][0]))
    elif bad=="missing-revision":del response["revisionId"]
    elif bad=="table":para["table"]={}
    elif bad=="suggestion":para["paragraph"]["elements"][0]["textRun"]["suggestedInsertionIds"]=["s"]
    elif bad=="wrong-index":para["endIndex"]-=1
    else:
        text=encoded(document).decode()+"\n"
        if bad=="no-newline":text=text[:-1]
        elif bad=="extra-newline":text+="\n"
        elif bad=="wrong-domain":text=text.replace(DOMAIN,TARGET)
        elif bad=="duplicate-key":text=text.replace('"layout_version":1','"layout_version":1,"layout_version":1')
        elif bad=="noncanonical":text=" "+text
        elif bad=="surrogate":text=text.replace('"UNRELEASED"','"\\ud800"')
        elif bad=="oversize":text='{"x":"'+'a'*524288+'"}\n'
        response=wire_document(document,text=text)
    store=WireStore(document);store.on_read=lambda _,r:response
    with pytest.raises(AuthorityError):NativeDocsAuthority(store.client(),BINDING).read()
    assert not store.calls


@pytest.mark.parametrize("bad",["domain","target","operation","generation","payload","result-hash","body-corrupt","state","owner","force"])
def test_terminal_plan_never_accepts_a_matching_name_without_complete_binding(bad):
    document,command,result=fixture_document();expected=binding(command);sha=result["result_sha256"]
    if bad in {"domain","target"}:expected[bad+"_id"]="30000000-0000-4000-8000-000000000001"
    elif bad=="operation":expected["operation_id"]="f"*64
    elif bad=="generation":expected["generation"]+=1
    elif bad=="payload":expected["payload_sha256"]="f"*64
    elif bad=="result-hash":sha="f"*64
    elif bad=="body-corrupt":document["records"]["target.000.result"]["body"]["exit_code"]=9
    elif bad=="state":document["records"]["target.000.status"]["body"]["stage"]="READY"
    elif bad=="owner":document["records"]["global.leadership"]["body"]["owner"]="other"
    else:document["records"]["global.force_request"]=dict(generation=1,operation_id="r",retention="BUSY",body={})
    store=WireStore(document);backend=NativeDocsAuthority(store.client(),BINDING)
    with pytest.raises(AuthorityError):terminal_publication(backend.read(),target_index=0,expected_binding=expected,
        result_sha256=sha,owner=OWNER,now=111)
    assert not store.calls


def test_caller_cannot_mutate_snapshot_by_alias_or_elect_with_record_helper():
    document,_,_=fixture_document();store=WireStore(document);backend=NativeDocsAuthority(store.client(),BINDING)
    snapshot=backend.read();external=snapshot.document();external["records"].clear()
    assert snapshot.document()==document
    with pytest.raises(AuthorityError,match="ELECTION_SEPARATE"):
        RecordMutation.prepare(snapshot,owner=OWNER,changes={"global.leadership":empty_record()},protect=set())


def test_private_use_characters_survive_docs_insertion_without_hash_or_data_loss():
    document,_,_=fixture_document();store=WireStore(document);backend=NativeDocsAuthority(store.client(),BINDING)
    snapshot=backend.read();desired=snapshot.document()
    desired["records"]["global.summary"]=dict(generation=1,operation_id="s",retention="RETAINED",body={"text":"\ue000\uf8ff\U0001f436"})
    assert backend.compare_replace(snapshot,desired)==WriteResult.ACCEPTED
    text=store.calls[0]["body"]["requests"][1]["insertText"]["text"]
    assert "\ue000" not in text and "\\ue000" in text
    assert backend.read().document()==desired


@pytest.mark.parametrize("mode,reads,writes",[("RETRY",6,3),("START",1,3),("START",13,3),("START",6,5),("START",True,3)])
def test_reconciliation_rejects_unsupported_mode_or_unbounded_budget(system,mode,reads,writes):
    store,backend,plan,_=system
    with pytest.raises(AuthorityError):reconcile(backend,plan,mode=mode,max_reads=reads,max_writes=writes)
    assert not store.calls
