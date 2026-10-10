"""Actual native keys/private metadata and closed normal replies; no authenticated SSH here."""
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import pytest

from tb4.credential_contract import Outcome, Purpose
from tb4.credential_persistence import export_private, restore_private
from tb4.drive.docs_authority import AuthorityError, WriteResult, document_bytes
from tb4.drive.folder_authority import FolderBinding
from tb4.drive.folder_authority_transport import CredentialAuthorityProcess, credential_authority_pair
from tb4.drive.folder_probe_transport import ProbeEndpoint
from tb4.drive.folder_protocol import FolderAccess, FolderAuthority, flat_json, header
from tb4.drive.folder_transport import FixedProcess
from tb4.exchange_layout import Capacity, empty_document, encoded
from tb4.key_policy import KeyAccessError
from tb4.private_settings import native_settings
from tests.security.test_private_settings_native import fixture, protect_fixture, SUPPORTED
from tests.security.test_folder_probe_transport_native import native, pinned_known

pytestmark = pytest.mark.skipif(not SUPPORTED, reason="Actual Windows/Linux protected authority transport")
INSTALLATION = "00000000-0000-4000-8000-000000000243"
TARGET = "00000000-0000-4000-8000-000000000242"
BINDING = FolderBinding("00000000-0000-4000-8000-000000000240", "00000000-0000-4000-8000-000000000241")
TRUST = "e"*64
CANARY = b"synthetic-native-authority-transport-key-never-public"
AUTH = frozenset({Purpose.FOLDER_AUTHORITY})


def system(fixture, monkeypatch, *, purposes=AUTH):
    root, settings = fixture
    key, known = root.parent/"synthetic-key", root.parent/"synthetic-known"
    key.write_bytes(CANARY); known.write_bytes(b"synthetic-pinned-known-file")
    protect_fixture(key); protect_fixture(known)
    endpoint = ProbeEndpoint(TARGET,TRUST,str(Path(sys.executable).resolve()),"storage.invalid",
        22222,"synthetic-user",str(known),pinned_known(known))
    now = [100]
    def pair():
        return credential_authority_pair(INSTALLATION,endpoint,BINDING,clock=lambda:now[0])
    store,resolver = pair()
    mode = dict(interactive_required=False) if os.name=="nt" else dict(
        access_mode="existing_key",launch_mode="headless")
    reference = store.select(path=str(key),target_id=TARGET,target_trust=TRUST,
        purposes=purposes,expires_at=200,owner_authorized=True,**mode)
    handle = resolver.enroll(target_id=TARGET,target_trust=TRUST,store_locator=reference,
        purposes=purposes,expires_at=200,owner_authorized=True)
    process = CredentialAuthorityProcess(resolver,handle)
    client = FolderAuthority(process,BINDING,FolderAccess(BINDING,True,True))
    state = dict(revision=7,document=empty_document(BINDING.domain_id,Capacity(1,1,1,1)),
                 reply="plain",last_read=None,writes=0)
    calls = []
    def wire(transport,raw):
        value = flat_json(raw); calls.append((transport,value))
        result = header(BINDING,value["nonce"])
        if value["operation"]=="READ":
            result.update(result="SNAPSHOT",revision=state["revision"],
                body=base64.b64encode(document_bytes(state["document"])).decode("ascii"))
            state["last_read"] = encoded(result)
        else:
            state["writes"] += 1
            if value["expected"]==state["revision"]:
                state["revision"] += 1
                state["document"] = json.loads(base64.b64decode(value["body"],validate=True))
                result.update(result=WriteResult.ACCEPTED.value)
            else: result.update(result=WriteResult.REJECTED.value)
            if state["reply"]=="lost": raise RuntimeError("SYNTHETIC_PRIVATE_AUTHORITY_CANARY")
            if state["reply"]=="unknown": result["result"]="UNKNOWN"
            if state["reply"]=="nonce": result["nonce"]="b"*32
            if state["reply"]=="extra": result["private"]="SYNTHETIC_PRIVATE_AUTHORITY_CANARY"
            if state["reply"]=="replay": return state["last_read"]
        return encoded(result)
    monkeypatch.setattr(FixedProcess,"call",wire)
    return SimpleNamespace(root=root,settings=settings,key=key,known=known,endpoint=endpoint,
        now=now,pair=pair,store=store,resolver=resolver,reference=reference,handle=handle,
        process=process,client=client,state=state,calls=calls,wire=wire)


def request():
    return dict(purpose=Purpose.FOLDER_AUTHORITY,target_id=TARGET,target_trust=TRUST)


def desired(snapshot):
    value = snapshot.document()
    value["records"]["global.summary"].update(retention="BUSY",body={"synthetic":True})
    return value


def test_native_borrowed_key_paths_one_use_reply_nonce_and_closed_public_outcome(fixture,monkeypatch,capsys):
    v = system(fixture,monkeypatch)
    v.settings.save({"registry":export_private(v.store,v.resolver),"history":{"kept":"UNKNOWN"}},expected_revision=0)
    before = v.settings.read()
    if os.name=="nt":
        from tb4.windows_key_native import HeldKey
    else:
        from tb4.linux_key_native import HeldKey
    original,borrowed = HeldKey.process_path,[]
    def path(held):
        value=original(held); borrowed.append((held,value))
        assert Path(value).read_bytes() in {CANARY,b"synthetic-pinned-known-file"}
        return value
    monkeypatch.setattr(HeldKey,"process_path",path)
    first,second=v.client.read(),v.client.read()
    assert first.raw==second.raw and v.calls[0][1]["nonce"]!=v.calls[1][1]["nonce"]
    assert v.client.compare_replace(first,desired(first)) is WriteResult.ACCEPTED
    assert v.client.read().document()==desired(first) and v.state["writes"]==1
    assert all(p.argv[-1]=="tb4-folder-v1" for p,_ in v.calls)
    assert v.process._runner._pending is None
    for held,path in borrowed:
        with pytest.raises(KeyAccessError): _=held.handle
        if os.name!="nt": assert not Path(path).exists()
    assert v.resolver.invoke(v.handle,**request()).report()==dict(
        outcome="DENIED",retry_automatically=False,inspection_required=False)
    assert len(v.calls)==4 and v.key.read_bytes()==CANARY
    assert native_settings(v.root).read()==before and CANARY not in (v.root/"settings.json").read_bytes()
    report=v.resolver.capability(v.handle,**request()).report()
    assert report["available"] and all(x not in json.dumps(report) for x in (
        str(v.key),str(v.known),v.handle,v.reference,TRUST,CANARY.decode()))
    assert capsys.readouterr()==("","")


@pytest.mark.parametrize("change,expected",[
    ("key-version",Outcome.REVOKED),("key-permission",Outcome.DENIED),
    ("known-version",Outcome.DENIED),("known-permission",Outcome.DENIED),
    ("expired",Outcome.EXPIRED),("revoked",Outcome.REVOKED)])
def test_native_previous_success_cannot_authorize_later_credential_or_trust_loss(fixture,monkeypatch,change,expected):
    v=system(fixture,monkeypatch);before_read=v.client.read()
    if change=="key-version": v.key.write_bytes(b"synthetic-changed-key")
    if change=="key-permission": protect_fixture(v.key,broad=True)
    if change=="known-version": v.known.write_bytes(b"synthetic-changed-known")
    if change=="known-permission": protect_fixture(v.known,broad=True)
    if change=="expired": v.now[0]=200
    if change=="revoked": v.resolver.revoke(v.handle,owner_authorized=True)
    v.settings.save({"registry":export_private(v.store,v.resolver),"history":{"kept":"UNKNOWN"}},expected_revision=0)
    saved=v.settings.read()
    assert v.resolver.capability(v.handle,**request()).outcome is expected
    assert v.client.compare_replace(before_read,desired(before_read)) is WriteResult.UNKNOWN
    assert len(v.calls)==1 and v.state["writes"]==0 and v.process._runner._pending is None
    assert native_settings(v.root).read()==saved


def test_native_private_restart_restores_same_selection_without_enrollment_or_profile_rewrite(fixture,monkeypatch):
    v=system(fixture,monkeypatch)
    v.settings.save({"registry":export_private(v.store,v.resolver),"history":{"kept":"UNKNOWN"}},expected_revision=0)
    before=v.settings.read();store,resolver=v.pair()
    restore_private(before.payload["registry"],store,resolver)
    process=CredentialAuthorityProcess(resolver,v.handle)
    client=FolderAuthority(process,BINDING,FolderAccess(BINDING,True,True))
    assert resolver._bindings[v.handle].store_locator==v.reference
    assert export_private(store,resolver)==before.payload["registry"]
    assert client.read().revision==7 and len(v.calls)==1
    v.key.write_bytes(b"synthetic-later-key")
    with pytest.raises(AuthorityError,match="^HELPER_UNAVAILABLE$"): client.read()
    assert len(v.calls)==1 and native_settings(v.root).read()==before


@pytest.mark.parametrize("reply",["lost","unknown","nonce","extra","replay"])
def test_native_ambiguous_after_cas_reply_is_unknown_once_and_later_read_inspects_same_effect(fixture,monkeypatch,reply,capsys):
    v=system(fixture,monkeypatch)
    v.settings.save({"registry":export_private(v.store,v.resolver),"history":{"kept":"UNKNOWN"}},expected_revision=0)
    before=v.settings.read();snapshot=v.client.read();value=desired(snapshot)
    v.state["reply"]=reply
    assert v.client.compare_replace(snapshot,value) is WriteResult.UNKNOWN
    assert len(v.calls)==2 and v.state["writes"]==1 and v.state["revision"]==8
    assert v.process._runner._pending is None and v.client.read().document()==value
    assert v.state["writes"]==1 and len(v.calls)==3 and native_settings(v.root).read()==before
    assert CANARY not in (v.root/"settings.json").read_bytes() and capsys.readouterr()==("","")


@pytest.mark.parametrize("change",["verify","extra","root","cas-body"])
def test_native_invalid_request_refuses_before_any_native_credential_access(fixture,monkeypatch,change):
    v=system(fixture,monkeypatch)
    raw={**header(BINDING,"a"*32),"operation":"READ"}
    if change=="verify": raw["operation"]="VERIFY"
    if change=="extra": raw["command"]="SYNTHETIC_PRIVATE_CANARY"
    if change=="root": raw["root"]=TARGET
    if change=="cas-body": raw.update(operation="CAS",expected=7,body="not-base64")
    def denied(*_): pytest.fail("invalid request opened a native file")
    monkeypatch.setattr(v.store._native,"open_key",denied)
    with pytest.raises(AuthorityError,match="^HELPER_UNAVAILABLE$"): v.process.call(encoded(raw))
    assert not v.calls and v.process._runner._pending is None


@pytest.mark.parametrize("change",["endpoint","binding","store"])
def test_native_changed_trusted_composition_pin_refuses_without_another_process_call(fixture,monkeypatch,change):
    v=system(fixture,monkeypatch);v.client.read()
    if change=="endpoint": v.process._runner.endpoint=replace(v.endpoint,host="changed.invalid")
    if change=="binding": v.process._runner.binding=FolderBinding(TARGET,BINDING.domain_id)
    if change=="store": v.resolver._store=v.pair()[0]
    with pytest.raises(AuthorityError,match="^HELPER_UNAVAILABLE$"): v.client.read()
    assert len(v.calls)==1 and v.process._runner._pending is None


def test_native_pending_authority_slot_refuses_parallel_reader_without_replacing_first(fixture,monkeypatch):
    v=system(fixture,monkeypatch);entered,release=threading.Event(),threading.Event()
    def blocked(process,raw):
        entered.set()
        assert release.wait(5)
        return v.wire(process,raw)
    monkeypatch.setattr(FixedProcess,"call",blocked)
    with ThreadPoolExecutor(1) as pool:
        first=pool.submit(v.client.read)
        try:
            assert entered.wait(5)
            with pytest.raises(AuthorityError,match="^HELPER_UNAVAILABLE$"): v.client.read()
            assert not v.calls and v.process._runner._pending is not None
        finally: release.set()
        assert first.result(timeout=5).revision==7
    assert len(v.calls)==1 and v.process._runner._pending is None


@pytest.mark.parametrize("purposes",[
    frozenset({Purpose.FOLDER_PROBE}),frozenset({Purpose.FETCHER_STATUS,Purpose.FETCHER_START})])
def test_native_historical_probe_or_fetcher_scope_cannot_invoke_normal_authority(fixture,monkeypatch,purposes):
    v=system(fixture,monkeypatch,purposes=purposes)
    with pytest.raises(AuthorityError,match="^HELPER_UNAVAILABLE$"): v.client.read()
    assert not v.calls and v.process._runner._pending is None

