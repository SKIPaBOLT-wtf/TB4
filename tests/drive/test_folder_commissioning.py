"""Actual isolated Linux ext4/xfs commissioning; never a deployment fixture."""
from dataclasses import replace
import os
from pathlib import Path
import sys

import pytest

from tb4.drive.commissioning import SetupSpec,Commissioner,RAW_LIMIT
from tb4.drive.commissioning_bootstrap import Bootstrap,AuthorityHandle
from tb4.drive.commissioning_folder import FolderCommissioning,ATTR
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority import DB,JOURNAL,identity,filesystem_type
from tb4.drive.leadership import Leadership
from tb4.drive.setup_journal import SetupJournal,JournalSection
from tb4.exchange_layout import Capacity
from test_native_leadership import ACTORS,ENROLLMENT,clock,tid
from test_native_commissioning import seed
from test_fixed_slot_commissioning import finish

pytestmark=pytest.mark.skipif(sys.platform!="linux",reason="Linux server-local commissioning")

@pytest.fixture
def context(tmp_path):
    root=tmp_path/"exchange";root.mkdir(mode=0o700)
    private=tmp_path/"private";private.mkdir(mode=0o700)
    try:filesystem_type(root,Path("/proc/self/mountinfo").read_text())
    except AuthorityError:
        if os.environ.get("TB4_REQUIRE_FOLDER_SSH")=="1":pytest.fail("Required filesystem unsupported")
        pytest.skip("Requires local ext4/xfs")
    spec=SetupSpec("40000000-0000-4000-8000-000000000001",
        "10000000-0000-4000-8000-000000000001",tid("folder-setup"),ACTORS[0],
        "FOLDER_SQLITE_V1",Capacity(1,1,1,1))
    port=FolderCommissioning(root,spec,root_identity=identity(root),llm_authorized=True)
    with SetupJournal(private,installation_id=ACTORS[0],setup_id=spec.setup_id,
                      verify_protection=lambda _:True) as j:
        yield spec,port,j

def initialized(context):
    spec,port,j=context
    b=Bootstrap(spec,port,JournalSection(j,"bootstrap"),owner_authorized=True)
    seed(b)
    handle=AuthorityHandle.parse(JournalSection(j,"bootstrap").read()["handle"])
    leader=Leadership(port.authority(handle),actor=ACTORS[0],enrollment=ENROLLMENT)
    grant=b.initial_grant(leader,clock())
    c=Commissioner(spec,leader,grant,port,JournalSection(j,"commissioning"))
    return b,handle,c

def test_complete_native_folder_restart_reuses_files_and_preserves_used_payload(context,monkeypatch):
    spec,port,j=context
    b,handle,c=initialized(context)
    finish(c)
    inventory={p.name:identity(p) for p in port.root.iterdir()}
    assert len(inventory)==4 and DB in inventory and JOURNAL in inventory
    allocation=port.prepare(spec.artifact_keys[0],spec.operation(spec.artifact_keys[0]))
    payload=port.root/allocation.object_id
    payload.write_bytes(b"synthetic already-used payload")
    # Explicit repeat must inspect existing objects without create/delete.
    def forbidden(*_):pytest.fail("Normal operation attempted allocation")
    monkeypatch.setattr(port,"create",forbidden)
    monkeypatch.setattr(port,"create_authority",forbidden)
    seed(b)
    assert c.advance(clock())=="STORAGE_READY"
    assert payload.read_bytes()==b"synthetic already-used payload"
    assert inventory=={p.name:identity(p) for p in port.root.iterdir()}

@pytest.mark.parametrize("failure",["authority-after","artifact-after","artifact-before","partial-db"])
def test_interruption_preserves_same_objects_without_recreate(context,monkeypatch,failure):
    spec,port,j=context
    b=Bootstrap(spec,port,JournalSection(j,"bootstrap"),owner_authorized=True)
    if failure in {"authority-after","partial-db"}:
        original=port.create_authority
        def interrupted(s):
            if failure=="partial-db":
                (port.root/DB).write_bytes(b"")
                (port.root/DB).chmod(0o600)
            else:original(s)
            raise TimeoutError("SYNTHETIC_PRIVATE_CANARY")
        monkeypatch.setattr(port,"create_authority",interrupted)
        assert b.advance(computer_name=ENROLLMENT[ACTORS[0]],clock=clock())=="UNKNOWN"
        monkeypatch.setattr(port,"create_authority",lambda *_:pytest.fail("Repeated unknown create"))
        if failure=="partial-db":
            for _ in range(3):assert b.advance(computer_name="synthetic",clock=clock())=="UNKNOWN"
            assert list(port.root.iterdir())==[port.root/DB]
            return
        seed(b)
        return
    _,_,c=initialized(context)
    original=port.create
    calls=[]
    def interrupted(key,allocation):
        calls.append(key)
        if failure=="artifact-after":original(key,allocation)
        raise TimeoutError("SYNTHETIC_PRIVATE_CANARY")
    monkeypatch.setattr(port,"create",interrupted)
    assert c.advance(clock())=="UNKNOWN"
    monkeypatch.setattr(port,"create",original)
    if failure=="artifact-after":
        assert c.advance(clock())=="CONFIRMED"
        finish(c)
    else:
        for _ in range(3):assert c.advance(clock())=="UNKNOWN"
    assert len(calls)==1

@pytest.mark.parametrize("change",["replace","marker","oversize","permissions","hardlink"])
def test_allocated_payload_identity_and_capacity_tampering_refuse(context,change):
    spec,port,_=context
    _,_,c=initialized(context)
    finish(c)
    key=spec.artifact_keys[0]
    ref=port.prepare(key,spec.operation(key))
    confirmed=port.inspect(key,ref)
    path=port.root/ref.object_id
    if change=="replace":
        path.rename(port.root/"old-synthetic")
        port.create(key,ref)
    if change=="marker":os.setxattr(path,ATTR,b"synthetic-invalid")
    if change=="oversize":
        with path.open("wb") as stream:stream.truncate(RAW_LIMIT+1)
    if change=="permissions":path.chmod(0o644)
    if change=="hardlink":os.link(path,port.root/"duplicate")
    with pytest.raises(AuthorityError):port.inspect(key,confirmed)

def test_foreign_nonempty_root_is_never_initialized(context):
    spec,port,j=context
    foreign=port.root/"unrelated";foreign.write_bytes(b"synthetic")
    b=Bootstrap(spec,port,JournalSection(j,"bootstrap"),owner_authorized=True)
    with pytest.raises(AuthorityError):b.advance(computer_name="synthetic",clock=clock())
    assert foreign.read_bytes()==b"synthetic" and not (port.root/DB).exists()
