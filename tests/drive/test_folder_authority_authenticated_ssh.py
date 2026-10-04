"""Required Linux selected native credential -> real fixed SSH READ/CAS helper."""
from concurrent.futures import ThreadPoolExecutor
import getpass
import os
from pathlib import Path
from types import SimpleNamespace
import pytest

from tb4.credential_contract import Purpose
from tb4.credential_persistence import export_private, restore_private
from tb4.drive.docs_authority import AuthorityError, WriteResult
from tb4.drive.folder_authority import FolderStore
from tb4.drive.folder_authority_transport import CredentialAuthorityProcess, credential_authority_pair
from tb4.drive.folder_protocol import FolderAccess, FolderAuthority, flat_json
from tb4.drive.folder_probe_transport import ProbeEndpoint
from tb4.drive.folder_transport import FixedProcess
from tb4.drive.leadership import Leadership
from tb4.linux_key_native import LinuxKeyNative
from tb4.private_settings import native_settings
from folder_fixtures import BINDING, inventory
from test_folder_ssh import remote
from test_native_leadership import ACTORS, ENROLLMENT, clock, tid

pytestmark = pytest.mark.skipif(os.name!="posix" or not Path("/proc/self/fd").exists(),
    reason="Actual Linux native credential fixed SSH authority")
TARGET = "00000000-0000-4000-8000-000000000242"
TRUST = "e"*64


@pytest.fixture
def authenticated(remote,tmp_path):
    config,_,server = remote
    known=server.root/"known";known.chmod(0o600)
    native=LinuxKeyNative()
    with native.open_key(str(known),native.identity().uid) as held: version=held.version
    endpoint=ProbeEndpoint(TARGET,TRUST,str(Path(server.ssh).resolve()),"127.0.0.1",
        server.port,getpass.getuser(),str(known),version)
    now=[100]
    def pair(installation):
        return credential_authority_pair(installation,endpoint,BINDING,clock=lambda:now[0])
    def make(name,installation,purposes=frozenset({Purpose.FOLDER_AUTHORITY})):
        store,resolver=pair(installation);key=server.root/name
        ref=store.select(path=str(key),target_id=TARGET,target_trust=TRUST,purposes=purposes,
            expires_at=200,access_mode="existing_key",launch_mode="headless",owner_authorized=True)
        handle=resolver.enroll(target_id=TARGET,target_trust=TRUST,store_locator=ref,purposes=purposes,
            expires_at=200,owner_authorized=True)
        process=CredentialAuthorityProcess(resolver,handle)
        client=FolderAuthority(process,BINDING,FolderAccess(BINDING,True,True))
        return SimpleNamespace(store=store,resolver=resolver,key=key,reference=ref,
            handle=handle,process=process,client=client,installation=installation)
    return SimpleNamespace(config=config,server=server,known=known,now=now,pair=pair,make=make,tmp=tmp_path)


def desired(snapshot):
    value=snapshot.document()
    value["records"]["global.summary"].update(retention="BUSY",body={"synthetic-authenticated":True})
    return value


def test_actual_authenticated_parent_key_paths_native_restart_and_one_cas_winner_preserve_files(authenticated,monkeypatch,capsys):
    v=authenticated;a=v.make("client-a",ACTORS[0]);b=v.make("client-b",ACTORS[1])
    key_bytes=(a.key.read_bytes(),b.key.read_bytes());objects=inventory(v.config)
    profile=native_settings(v.tmp/"synthetic-authority-private",create=True,owner_authorized=True)
    profile.save({"registry":export_private(a.store,a.resolver),"history":{"kept":"UNKNOWN"}},expected_revision=0)
    before=profile.read();store,resolver=v.pair(a.installation)
    restore_private(before.payload["registry"],store,resolver)
    process=CredentialAuthorityProcess(resolver,a.handle)
    a.client=FolderAuthority(process,BINDING,FolderAccess(BINDING,True,True))
    original,calls=FixedProcess.call,[]
    def observe(transport,raw):
        assert transport.argv[-1]=="tb4-folder-v1"
        key=next(x for x in transport.argv if x.startswith("-oIdentityFile="))
        known=next(x for x in transport.argv if x.startswith("-oUserKnownHostsFile="))
        assert f"/proc/{os.getpid()}/fd/" in key and f"/proc/{os.getpid()}/fd/" in known
        assert str(a.key) not in key and str(b.key) not in key and str(v.known) not in known
        calls.append(flat_json(raw))
        return original(transport,raw)
    monkeypatch.setattr(FixedProcess,"call",observe)
    snapshots=[a.client.read(),b.client.read()];value=desired(snapshots[0])
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda n:(a.client,b.client)[n].compare_replace(snapshots[n],value),range(2)))
    assert results.count(WriteResult.ACCEPTED)==1
    assert set(results)<={WriteResult.ACCEPTED,WriteResult.REJECTED,WriteResult.UNAVAILABLE}
    assert a.client.read().document()==b.client.read().document()==value
    # Fresh readback proves the old conditional revision cannot commit again.
    assert b.client.compare_replace(snapshots[1],value) is WriteResult.REJECTED
    assert len(calls)==7 and len({x["nonce"] for x in calls})==7
    assert inventory(v.config)==objects and (a.key.read_bytes(),b.key.read_bytes())==key_bytes
    assert profile.read()==before and export_private(store,resolver)==before.payload["registry"]
    assert a.handle==process._handle and resolver._bindings[a.handle].store_locator==a.reference
    assert process._runner._pending is None and b.process._runner._pending is None
    assert all(key not in (v.tmp/"synthetic-authority-private"/"settings.json").read_bytes() for key in key_bytes)
    assert capsys.readouterr()==("","")


def test_actual_authenticated_stale_and_forced_takeover_need_no_previous_owner_ack_and_preserve_unknown(authenticated):
    v=authenticated;a=v.make("client-a",ACTORS[0]);b=v.make("client-b",ACTORS[1])
    snapshot=a.client.read();value=snapshot.document()
    value["records"]["target.000.work"].update(generation=7,operation_id="old-unknown",
        retention="BUSY",body={"unknown":True})
    assert a.client.compare_replace(snapshot,value) is WriteResult.ACCEPTED
    preserved=a.client.read().document()["records"]["target.000.work"]
    x,y=(Leadership(p,actor=k,enrollment=ENROLLMENT) for p,k in ((a.client,ACTORS[0]),(b.client,ACTORS[1])))
    plan=x.acquire(x.observe(clock()),transition=tid("authenticated-initial"),commissioning=True)
    grant=x.confirmed_grant(plan,x.commit(plan,mode="START"))
    plan=y.acquire(y.observe(clock(220)),transition=tid("authenticated-stale"))
    new=y.confirmed_grant(plan,y.commit(plan,mode="START"))
    assert new.epoch==2 and not x.current_before_dispatch(grant,clock(220))
    force=x.request_force(x.observe(clock(221)),request_id=tid("authenticated-force"),user_requested=True)
    assert x.commit(force,mode="START").outcome=="CONFIRMED"
    assert not y.current_before_dispatch(new,clock(221))
    claim=x.claim_requested(x.observe(clock(221)),request_id=tid("authenticated-force"))
    newest=x.confirmed_grant(claim,x.commit(claim,mode="START"))
    assert newest.epoch==3 and a.client.read().document()["records"]["target.000.work"]==preserved


def test_actual_authenticated_lost_after_commit_reply_is_unknown_and_inspection_never_resends(authenticated,monkeypatch):
    v=authenticated;a=v.make("client-a",ACTORS[0]);objects=inventory(v.config)
    before=a.client.read();value=desired(before);original=FixedProcess.call;writes=[]
    def lost(transport,raw):
        reply=original(transport,raw)
        if flat_json(raw)["operation"]=="CAS":
            writes.append(raw)
            raise RuntimeError("SYNTHETIC_PRIVATE_CANARY")
        return reply
    monkeypatch.setattr(FixedProcess,"call",lost)
    assert a.client.compare_replace(before,value) is WriteResult.UNKNOWN and len(writes)==1
    assert FolderStore(v.config).read()[0]==before.revision+1
    assert a.client.read().document()==value and len(writes)==1
    assert inventory(v.config)==objects and a.process._runner._pending is None


@pytest.mark.parametrize("change",["key-version","key-permission","known-version","known-permission","expired","revoked"])
def test_actual_authenticated_later_credential_loss_refuses_cas_without_process_or_profile_reset(authenticated,monkeypatch,change):
    v=authenticated;a=v.make("client-a",ACTORS[0]);snapshot=a.client.read()
    before=FolderStore(v.config).read();objects=inventory(v.config)
    profile=native_settings(v.tmp/"synthetic-lost-private",create=True,owner_authorized=True)
    if change=="revoked": a.resolver.revoke(a.handle,owner_authorized=True)
    profile.save({"registry":export_private(a.store,a.resolver),"history":{"kept":"UNKNOWN"}},expected_revision=0)
    saved=profile.read()
    if change=="key-version": a.key.write_bytes(b"synthetic-later-key")
    if change=="key-permission": a.key.chmod(0o644)
    if change=="known-version": v.known.write_bytes(b"synthetic-later-known")
    if change=="known-permission": v.known.chmod(0o644)
    if change=="expired": v.now[0]=200
    def refused(*_): pytest.fail("lost credential reached an authenticated process")
    monkeypatch.setattr(FixedProcess,"call",refused)
    assert a.client.compare_replace(snapshot,desired(snapshot)) is WriteResult.UNKNOWN
    assert FolderStore(v.config).read()==before and inventory(v.config)==objects
    assert profile.read()==saved and a.process._runner._pending is None

