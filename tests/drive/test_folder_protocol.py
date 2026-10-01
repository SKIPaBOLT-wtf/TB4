"""Cross-platform protocol/port checks, with no installed profile or secret IO."""
from dataclasses import replace
import base64
import copy
import sys
import time
from types import SimpleNamespace

import pytest

from tb4.drive.docs_authority import AuthorityError, WriteResult, document_bytes
from tb4.drive.folder_authority import FolderBinding, filesystem_type
from tb4.drive.folder_protocol import (FolderAccess, FolderAuthority, MAX_WIRE, flat_json,
                                       handle, header)
from tb4.drive.folder_transport import FixedProcess
from tb4.exchange_layout import Capacity, empty_document, encoded
from folder_fixtures import BINDING, DOMAIN


class SyntheticPort:
    binding = BINDING
    def __init__(self):
        self.document = empty_document(DOMAIN, Capacity(1,1,1,1))
        self.revision, self.calls, self.commits = 1, 0, 0
        self.transform = lambda value: value
        self.lost = False
    def read(self): return self.revision, document_bytes(self.document)
    def compare_replace(self, expected, raw):
        if expected != self.revision: return WriteResult.REJECTED
        self.document = __import__("json").loads(raw)
        self.revision += 1; self.commits += 1
        if self.lost: raise TimeoutError("SYNTHETIC_PRIVATE_CANARY")
        return WriteResult.ACCEPTED
    def call(self, raw):
        self.calls += 1
        return self.transform(handle(self, raw))


def client(port): return FolderAuthority(port, BINDING, FolderAccess(BINDING, True, True))

def changed(snapshot):
    doc = snapshot.document()
    doc["records"]["global.summary"].update(retention="BUSY", body={"synthetic":True})
    return doc


def test_distinct_clients_strict_revision_and_readback():
    port = SyntheticPort(); a,b = client(port),client(port)
    first, stale = a.read(),b.read()
    assert a.compare_replace(first, changed(first)) == WriteResult.ACCEPTED
    assert b.compare_replace(stale, changed(stale)) == WriteResult.REJECTED
    assert b.read().raw == document_bytes(changed(first)) and port.commits == 1


def test_lost_commit_reply_is_unknown_and_reconnect_inspects_same_object():
    port = SyntheticPort(); a = client(port); old = a.read()
    port.lost = True
    assert a.compare_replace(old, changed(old)) == WriteResult.UNKNOWN
    assert client(port).read().document() == changed(old) and port.commits == 1


@pytest.mark.parametrize("access", [None, FolderAccess(BINDING,False,True), FolderAccess(BINDING,True,False),
    FolderAccess(BINDING,1,True), FolderAccess(FolderBinding(DOMAIN,DOMAIN),True,True)])
def test_no_same_exchange_authorized_llm_no_activation_or_io(access):
    port = SyntheticPort()
    with pytest.raises(AuthorityError,match="SAME_EXCHANGE_ACCESS_REQUIRED"):
        FolderAuthority(port,BINDING,access)
    assert port.calls == 0


@pytest.mark.parametrize("field,value", [("root",DOMAIN),("domain",BINDING.root_id),("nonce","a"*32),
    ("mode","DRIVE"),("version",True),("revision",True),("revision",0),("body","***"),
    ("extra","unexpected"),("result","ACCEPTED")])
def test_read_rejects_foreign_replayed_or_malformed_response(field,value):
    port = SyntheticPort()
    port.transform = lambda raw: encoded({**flat_json(raw),field:value})
    with pytest.raises(AuthorityError): client(port).read()
    assert port.calls == 1 and port.commits == 0


@pytest.mark.parametrize("raw", [b'{"version":1,"version":1}',b'{"x":NaN}',b'{"x":true}',
    b'[[[[]]]]', b'{"x":{}}', b'"string"',b'\xff', b' '*(MAX_WIRE+1)],
    ids=["duplicate","nan","bool","depth","nested","scalar","encoding","oversize"])
def test_closed_decoder(raw):
    with pytest.raises(AuthorityError): flat_json(raw)


def test_helper_rejects_paths_commands_and_mismatched_root_before_mutation():
    port = SyntheticPort()
    request = {**header(BINDING,"a"*32),"operation":"READ","path":"SYNTHETIC_PRIVATE_CANARY"}
    assert flat_json(handle(port,encoded(request)))["result"]=="UNKNOWN"
    request.pop("path"); request["operation"]="CREATE"
    assert flat_json(handle(port,encoded(request)))["result"]=="UNKNOWN"
    request["operation"]="READ";request["root"]=DOMAIN
    assert flat_json(handle(port,encoded(request)))=={"result":"UNKNOWN"}
    assert port.commits == 0


def test_snapshot_origin_layout_and_canonical_validation():
    port = SyntheticPort(); a,b=client(port),client(port)
    old = a.read()
    with pytest.raises(AuthorityError,match="SNAPSHOT_ORIGIN"): b.compare_replace(old,changed(old))
    doc = changed(old);doc["layout_revision"] += 1
    with pytest.raises((AuthorityError,ValueError)): a.compare_replace(old,doc)
    assert port.commits == 0


@pytest.mark.parametrize("output", ["print('SYNTHETIC_PRIVATE_CANARY',file=sys.stderr); sys.exit(2)",
    "sys.stdout.buffer.write(b'x' * (1048576+1)); sys.stdout.flush(); time.sleep(3)", "time.sleep(3)"],
    ids=["nonzero-private-stderr","bounded-stdout","timeout"])
def test_fixed_process_failure_bounded_and_sanitized(output):
    port = FixedProcess(BINDING,(sys.executable,"-X","utf8","-c","import sys,time; "+output),timeout=.3)
    start = time.monotonic()
    with pytest.raises(AuthorityError,match="^HELPER_UNAVAILABLE$"): port.call(b"{}")
    assert time.monotonic() - start < 2


def test_fixed_process_success_and_input_bound():
    port = FixedProcess(BINDING,(sys.executable,"-X","utf8","-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"))
    assert port.call(b"{}") == b"{}"
    with pytest.raises(AuthorityError,match="RPC_SIZE"): port.call(b"x"*(MAX_WIRE+1))


@pytest.mark.parametrize("fs",["nfs","nfs4","cifs","fuse","overlay","tmpfs","9p"])
def test_network_sync_and_unqualified_filesystems_cannot_activate(fs):
    from pathlib import Path
    with pytest.raises(AuthorityError,match="FILESYSTEM_UNQUALIFIED"):
        filesystem_type(Path("/exchange"), f"1 0 1:1 / / rw - {fs} source rw")


def test_nested_mount_overrides_parent_filesystem():
    from pathlib import Path
    info = "1 0 1:1 / / rw - ext4 source rw\\n2 1 1:2 / /exchange rw - nfs source rw".replace("\\n","\n")
    with pytest.raises(AuthorityError): filesystem_type(Path("/exchange/sub"), info)

