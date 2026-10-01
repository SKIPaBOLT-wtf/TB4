"""Real SQLite/helper conformance: independent connections, clients and processes."""
import base64
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from tb4.command_contract import binding
from tb4.drive.authority_transaction import reconcile, terminal_publication
from tb4.drive.docs_authority import AuthorityError, WriteResult, document_bytes
from tb4.drive.folder_authority import DB, JOURNAL, FolderStore, identity
from tb4.drive.folder_helper import load_config
from tb4.drive.folder_protocol import FolderAccess, FolderAuthority, handle, flat_json
from tb4.drive.folder_transport import FixedProcess
from tb4.drive.leadership import Leadership
from tb4.exchange_layout import Capacity, empty_document, encoded
from folder_fixtures import BINDING, DOMAIN, provision, inventory
from test_native_docs_transport import fixture_document, OWNER
from test_native_leadership import ACTORS, ENROLLMENT, clock, tid

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux server-local folder mode")


class InProcess:
    binding = BINDING
    def __init__(self, config): self.store=FolderStore(config)
    def call(self, raw): return handle(self.store,raw)


class Intercept:
    binding = BINDING
    def __init__(self, port):
        self.port, self.calls, self.writes = port,0,0
        self.lost, self.offline = False,False
    def call(self, raw):
        self.calls += 1
        if self.offline: raise TimeoutError("SYNTHETIC_PRIVATE_CANARY")
        write = flat_json(raw)["operation"] == "CAS"
        self.writes += int(write)
        reply = self.port.call(raw)
        if write and self.lost: raise TimeoutError("SYNTHETIC_PRIVATE_CANARY")
        return reply


def client(port): return FolderAuthority(port,BINDING,FolderAccess(BINDING,True,True))


@pytest.fixture(params=["in-process","independent-helper"])
def setup(request,tmp_path):
    config,path = provision(tmp_path)
    def make():
        port = InProcess(config) if request.param=="in-process" else FixedProcess(BINDING,
            (sys.executable,"-X","utf8","-m","tb4.drive.folder_helper","--config",str(path)))
        port = Intercept(port)
        return client(port),port
    return config,path,make


def test_two_clients_atomic_compare_and_fixed_inventory(setup):
    config,_,make=setup
    a,_=make();b,_=make()
    objects=inventory(config);first=a.read();stale=b.read()
    desired=first.document();desired["records"]["global.summary"].update(retention="BUSY",body={"ok":True})
    assert a.compare_replace(first,desired)==WriteResult.ACCEPTED
    assert b.compare_replace(stale,desired)==WriteResult.REJECTED
    assert b.read().document()==desired and a.read().revision==2
    assert inventory(config)==objects and set(objects)=={DB,JOURNAL}


def test_stale_takeover_first_successful_cas_no_sink_ack_preserves_unknown(setup):
    config,_,make=setup
    a,_=make();b,_=make()
    old=a.read();doc=old.document()
    doc["records"]["target.000.work"].update(generation=7,operation_id="old-unknown",
        retention="UNKNOWN",body={"effects":"UNKNOWN","reachable":False})
    assert a.compare_replace(old,doc)==WriteResult.ACCEPTED
    x,y=(Leadership(p,actor=k,enrollment=ENROLLMENT) for p,k in ((a,ACTORS[0]),(b,ACTORS[1])))
    plan=x.acquire(x.observe(clock()),transition=tid("first"),commissioning=True)
    grant=x.confirmed_grant(plan,x.commit(plan,mode="START"))
    with pytest.raises(AuthorityError,match="INCUMBENT_FRESH"):
        y.acquire(y.observe(clock(219)),transition=tid("early"))
    candidates=[l.acquire(l.observe(clock(220)),transition=tid("take-"+str(i))) for i,l in enumerate((y,x))]
    assert y.commit(candidates[0],mode="START").outcome=="CONFIRMED"
    assert x.commit(candidates[1],mode="START").outcome=="SUPERSEDED"
    assert not x.current_before_dispatch(grant,clock(220))
    assert b.read().document()["records"]["target.000.work"]==doc["records"]["target.000.work"]


def test_force_request_stops_incumbent_before_claim_without_ack(setup):
    _,_,make=setup;a,_=make();b,_=make()
    x,y=(Leadership(p,actor=k,enrollment=ENROLLMENT) for p,k in ((a,ACTORS[0]),(b,ACTORS[1])))
    first=x.acquire(x.observe(clock()),transition=tid("initial"),commissioning=True)
    grant=x.confirmed_grant(first,x.commit(first,mode="START"))
    renew=x.renew(x.observe(clock(101)),grant,transition=tid("old-renew"))
    request=y.request_force(y.observe(clock(101)),request_id=tid("force"),user_requested=True)
    assert y.commit(request,mode="START").outcome=="CONFIRMED"
    assert x.commit(renew,mode="START").outcome=="SUPERSEDED"
    assert not x.current_before_dispatch(grant,clock(101))
    claim=y.claim_requested(y.observe(clock(101)),request_id=tid("force"))
    new=y.confirmed_grant(claim,y.commit(claim,mode="START"))
    assert new.epoch==2 and y.current_before_dispatch(new,clock(101))


def test_lost_reply_reconnect_inspection_does_not_repeat_mutation(setup):
    _,_,make=setup;a,port=make()
    leader=Leadership(a,actor=ACTORS[0],enrollment=ENROLLMENT)
    plan=leader.acquire(leader.observe(clock()),transition=tid("unknown"),commissioning=True)
    port.lost=True
    result=leader.commit(plan,mode="START")
    assert result.outcome=="CONFIRMED" and port.writes==1
    port.offline=True
    assert leader.commit(plan,mode="INSPECT").outcome=="UNKNOWN"
    port.offline=False
    fresh,p2=make(); resumed=Leadership(fresh,actor=ACTORS[0],enrollment=ENROLLMENT)
    assert resumed.commit(plan,mode="INSPECT").outcome=="CONFIRMED" and p2.writes==0


def test_same_terminal_publication_as_native_docs_and_unknown_readback(tmp_path):
    document,request,result=fixture_document()
    config,_=provision(tmp_path,document)
    port=Intercept(InProcess(config));a=client(port)
    plan=terminal_publication(a.read(),target_index=0,expected_binding=binding(request),
        result_sha256=result["result_sha256"],owner=OWNER,now=111)
    port.lost=True
    assert reconcile(a,plan,mode="START").outcome=="CONFIRMED"
    assert port.writes==1
    assert reconcile(a,plan,mode="INSPECT").outcome=="CONFIRMED" and port.writes==1
    doc=client(InProcess(config)).read().document()
    assert doc["records"]["target.000.result"]["retention"]=="UNREAD"
    assert doc["records"]["target.000.status"]["body"]["stage"]=="AWAITING_CONSUMPTION"


@pytest.mark.parametrize("target",["root","db","journal"])
def test_missing_renamed_identity_not_recreated_or_discovered(tmp_path,target):
    config,_=provision(tmp_path);store=FolderStore(config)
    path={"root":config.root,"db":config.root/DB,"journal":config.root/JOURNAL}[target]
    held=path.with_name("held-"+path.name);path.rename(held)
    try:
        with pytest.raises(AuthorityError): store.read()
        assert not path.exists()
        # Even an identical-looking replacement is rejected, not silently adopted.
        if target!="root":
            path.write_bytes(held.read_bytes());path.chmod(0o600)
            with pytest.raises(AuthorityError,match="FIXED_IDENTITY"):store.read()
            path.unlink()  # Only this test-created impostor; never an installed file.
    finally: held.rename(path)
    assert store.read()[0]==1


@pytest.mark.parametrize("target",["root","db","journal"])
def test_permission_loss_and_restore(tmp_path,target):
    config,_=provision(tmp_path);store=FolderStore(config)
    path={"root":config.root,"db":config.root/DB,"journal":config.root/JOURNAL}[target]
    mode=path.stat().st_mode & 0o777
    path.chmod(0)
    try:
        with pytest.raises(AuthorityError):store.read()
        doc=document_bytes(empty_document(DOMAIN,Capacity(1,1,1,1)))
        assert store.compare_replace(1,doc)==WriteResult.UNAVAILABLE
    finally:path.chmod(mode)
    assert store.read()[0]==1


def test_wrong_domain_schema_and_foreign_wal_rejected(tmp_path):
    config,_=provision(tmp_path)
    with pytest.raises(AuthorityError):
        FolderStore(replace(config,binding=replace(BINDING,root_id=DOMAIN))).read()
    foreign=config.root/(DB+"-wal");foreign.write_bytes(b"synthetic")
    with pytest.raises(AuthorityError,match="FOREIGN_JOURNAL"): FolderStore(config).read()
    foreign.unlink()
    with FolderStore(config).connection() as conn:
        conn.execute("CREATE TABLE extra (value)")
    with pytest.raises(AuthorityError,match="DATABASE_SCHEMA"):FolderStore(config).read()


def test_config_private_and_closed(tmp_path):
    _,path=provision(tmp_path)
    assert load_config(path).binding==BINDING
    path.chmod(0o644)
    with pytest.raises(AuthorityError,match="HELPER_CONFIG"):load_config(path)
    path.chmod(0o600);data=json.loads(path.read_text());data["extra"]="not allowed"
    path.write_text(json.dumps(data))
    with pytest.raises(AuthorityError,match="RPC_INVALID"):load_config(path)


def test_contending_independent_helpers_have_one_winner_then_stale_rejected(tmp_path):
    config,path=provision(tmp_path);objects=inventory(config)
    ports=[FixedProcess(BINDING,(sys.executable,"-X","utf8","-m","tb4.drive.folder_helper",
                                "--config",str(path))) for _ in range(2)]
    clients=[client(p) for p in ports];old=[c.read() for c in clients]
    desired=old[0].document();desired["records"]["global.summary"].update(retention="BUSY",body={"win":True})
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda n:clients[n].compare_replace(old[n],desired),range(2)))
    assert results.count(WriteResult.ACCEPTED)==1
    assert set(results)<={WriteResult.ACCEPTED,WriteResult.REJECTED,WriteResult.UNAVAILABLE}
    assert clients[0].compare_replace(old[0],desired)==WriteResult.REJECTED
    assert clients[1].read().document()==desired and inventory(config)==objects


def test_killed_owned_writer_rolls_back_hot_journal_same_fixed_files(tmp_path):
    config,path=provision(tmp_path);store=FolderStore(config)
    before=store.read();objects=inventory(config);db_before=(config.root/DB).read_bytes()
    script = """import sys
from tb4.drive.folder_authority import FolderStore
from tb4.drive.folder_helper import load_config
with FolderStore(load_config(sys.argv[1])).connection() as conn:
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("UPDATE authority SET revision=revision+1,body=? WHERE id=1",(b"X"*(384*1024),))
    print("READY",flush=True)
    sys.stdin.buffer.read(1)
"""
    child=subprocess.Popen([sys.executable,"-X","utf8","-c",script,str(path)],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    with ThreadPoolExecutor(1) as pool:
        try:
            assert pool.submit(child.stdout.readline).result(timeout=5).strip()==b"READY"
            assert (config.root/DB).read_bytes()!=db_before
            assert (config.root/JOURNAL).stat().st_size>0
        finally:
            if child.poll() is None:child.kill()
            child.communicate(timeout=5)
    assert store.read()==before and inventory(config)==objects
