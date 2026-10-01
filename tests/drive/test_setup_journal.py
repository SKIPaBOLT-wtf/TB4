"""Real private journal durability and process locking on Windows and Linux."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tb4.drive.commissioning import digest
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.setup_journal import SetupJournal, JournalSection

ACTOR="10000000-0000-4000-8000-000000000001"
SETUP=digest("synthetic-journal")

def journal(root,**kwargs):
    return SetupJournal(root,installation_id=ACTOR,setup_id=SETUP,
                        verify_protection=lambda _:True,**kwargs)

def test_restart_sections_and_truncated_staging_preserve_committed_state(tmp_path):
    with journal(tmp_path) as j:
        first,second=JournalSection(j,"bootstrap"),JournalSection(j,"commissioning")
        first.save({"phase":"UNKNOWN"})
        second.save({"pending":"synthetic"})
        j.temp.write_bytes(b'{"truncated"')
        j.temp.chmod(0o600)
    with journal(tmp_path) as j:
        assert JournalSection(j,"bootstrap").read()=={"phase":"UNKNOWN"}
        assert JournalSection(j,"commissioning").read()=={"pending":"synthetic"}
        JournalSection(j,"commissioning").save({"pending":None})
        assert JournalSection(j,"bootstrap").read()=={"phase":"UNKNOWN"}
        assert not j.temp.exists()

def test_lock_excludes_second_process_and_releases_after_owner_exit(tmp_path):
    script="""from pathlib import Path
import sys
from tb4.drive.setup_journal import SetupJournal
from tb4.drive.docs_authority import AuthorityError
try:
    with SetupJournal(Path(sys.argv[1]),installation_id=sys.argv[2],setup_id=sys.argv[3],
                      verify_protection=lambda _:True):
        print("ACQUIRED")
except AuthorityError:
    print("REFUSED")
"""
    def child():
        return subprocess.run([sys.executable,"-c",script,str(tmp_path),ACTOR,SETUP],
                              capture_output=True,text=True,timeout=10,check=True).stdout.strip()
    with journal(tmp_path) as j:
        j.save({"phase":"UNKNOWN"})
        assert child()=="REFUSED"
    assert child()=="ACQUIRED"

@pytest.mark.parametrize("damage",["corrupt","oversize","binding","digest","hardlink"])
def test_untrusted_checkpoint_refuses_without_replacement(tmp_path,damage):
    with journal(tmp_path) as j:j.save({"phase":"UNKNOWN"})
    path=tmp_path/(SETUP+".json")
    before=path.read_bytes()
    if damage=="corrupt":path.write_bytes(b"{")
    if damage=="oversize":path.write_bytes(b" "* (512*1024+1))
    if damage=="binding":path.write_bytes(before.replace(ACTOR.encode(),b"20000000-0000-4000-8000-000000000001"))
    if damage=="digest":path.write_bytes(before.replace(b"UNKNOWN",b"CHANGED"))
    if damage=="hardlink":os.link(path,tmp_path/"duplicate")
    altered=path.read_bytes()
    with pytest.raises(AuthorityError):
        with journal(tmp_path) as j:j.read()
    assert path.read_bytes()==altered

def test_failed_replace_keeps_previous_authoritative_checkpoint(tmp_path,monkeypatch):
    with journal(tmp_path) as j:
        j.save({"phase":"OLD"})
        def failed(*_):raise OSError("SYNTHETIC_PRIVATE_CANARY")
        with monkeypatch.context() as m:
            m.setattr(os,"replace",failed)
            with pytest.raises(AuthorityError) as error:j.save({"phase":"NEW"})
        assert "SYNTHETIC_PRIVATE_CANARY" not in str(error.value)
        assert j.read()=={"phase":"OLD"}
        j.save({"phase":"RECOVERED"})
        assert j.read()=={"phase":"RECOVERED"}

def test_protection_revocation_and_unheld_lock_refuse_before_write(tmp_path):
    allowed=[True]
    j=SetupJournal(tmp_path,installation_id=ACTOR,setup_id=SETUP,
                   verify_protection=lambda _:allowed[0])
    with pytest.raises(AuthorityError):j.save({})
    with j:
        j.save({"phase":"OLD"})
        allowed[0]=False
        with pytest.raises(AuthorityError):j.save({"phase":"NEW"})
    allowed[0]=True
    with j:assert j.read()=={"phase":"OLD"}
