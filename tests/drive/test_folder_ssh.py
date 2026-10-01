"""Isolated loopback OpenSSH, two synthetic client identities, one forced helper."""
from concurrent.futures import ThreadPoolExecutor
import getpass
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import time

import pytest

from tb4.drive.docs_authority import AuthorityError, WriteResult
from tb4.drive.folder_authority import DB, JOURNAL
from tb4.drive.folder_protocol import FolderAccess, FolderAuthority
from tb4.drive.folder_transport import FixedProcess
from folder_fixtures import BINDING, provision, inventory
from test_folder_store import Intercept
from tb4.drive.leadership import Leadership
from test_native_leadership import ACTORS, ENROLLMENT, clock, tid


def run_owned(argv):
    result=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL,timeout=10)
    assert result.returncode==0, "Synthetic SSH fixture preparation failed"


class Server:
    def __init__(self, root, helper_config, sshd, ssh):
        self.root,self.sshd,self.ssh=root,sshd,ssh
        self.child=None
        with socket.socket() as port:
            port.bind(("127.0.0.1",0));self.port=port.getsockname()[1]
        keygen=shutil.which("ssh-keygen")
        assert keygen, "Synthetic SSH key generator required"
        for name in ("host","client-a","client-b"):
            run_owned([keygen,"-q","-t","ed25519","-N","","-f",str(root/name)])
        (root/"authorized").write_text("".join("restrict "+(root/(name+".pub")).read_text()
                                              for name in ("client-a","client-b")))
        (root/"authorized").chmod(0o600)
        host_key=(root/"host.pub").read_text().split()[:2]
        (root/"known").write_text(f"[127.0.0.1]:{self.port} "+" ".join(host_key)+"\n")
        helper=shlex.join([sys.executable,"-X","utf8","-m","tb4.drive.folder_helper","--config",str(helper_config)])
        # StrictModes=no is confined to generated fixture keys under pytest's
        # temporary parent. It is not a supported deployment recommendation.
        configuration=f"""ListenAddress 127.0.0.1
Port {self.port}
HostKey {root/'host'}
PidFile {root/'sshd.pid'}
AuthorizedKeysFile {root/'authorized'}
AllowUsers {getpass.getuser()}
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
UsePAM no
StrictModes no
PermitRootLogin prohibit-password
AllowTcpForwarding no
AllowAgentForwarding no
X11Forwarding no
PermitTunnel no
PermitTTY no
ForceCommand {helper}
LogLevel ERROR
"""
        (root/"sshd.config").write_text(configuration)
        self.start()

    def start(self):
        self.child=subprocess.Popen([self.sshd,"-D","-e","-f",str(self.root/"sshd.config")],
                                    stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(50):
            if self.child.poll() is not None:break
            try:
                with socket.create_connection(("127.0.0.1",self.port),timeout=.1):return
            except OSError: time.sleep(.05)
        self.stop()
        pytest.fail("Isolated SSH server unavailable")

    def stop(self):
        if self.child and self.child.poll() is None:
            self.child.terminate()
            try:self.child.wait(timeout=3)
            except subprocess.TimeoutExpired:self.child.kill();self.child.wait(timeout=3)

    def transport(self, name):
        return FixedProcess(BINDING,(self.ssh,"-F","none","-T","-o","BatchMode=yes",
            "-o","IdentitiesOnly=yes","-o","StrictHostKeyChecking=yes","-o","PasswordAuthentication=no",
            "-o","KbdInteractiveAuthentication=no","-o","ConnectTimeout=2","-o","ConnectionAttempts=1",
            "-o","UserKnownHostsFile="+str(self.root/"known"),"-o","GlobalKnownHostsFile=/dev/null",
            "-p",str(self.port),"-i",str(self.root/name),"-l",getpass.getuser(),
            "127.0.0.1","tb4-folder-v1"))

    def client(self,name):return FolderAuthority(self.transport(name),BINDING,FolderAccess(BINDING,True,True))


@pytest.fixture
def remote(tmp_path):
    if sys.platform!="linux":
        if os.environ.get("TB4_REQUIRE_FOLDER_SSH")=="1":pytest.fail("Required Linux SSH test unavailable")
        pytest.skip("Linux loopback SSH fixture")
    sshd=shutil.which("sshd") or ("/usr/sbin/sshd" if Path("/usr/sbin/sshd").exists() else None)
    ssh=shutil.which("ssh")
    if not sshd or not ssh:
        if os.environ.get("TB4_REQUIRE_FOLDER_SSH")=="1":pytest.fail("Required OpenSSH tools unavailable")
        pytest.skip("Optional local fixture requires OpenSSH; required in CI")
    config,path=provision(tmp_path)
    server=Server(tmp_path,path,sshd,ssh)
    try:yield config,path,server
    finally:server.stop()


def test_remote_clients_one_cas_winner_readback_and_no_new_exchange_objects(remote):
    config,_,server=remote
    a,b=server.client("client-a"),server.client("client-b")
    objects=inventory(config);old=[a.read(),b.read()]
    desired=old[0].document();desired["records"]["global.summary"].update(retention="BUSY",body={"remote":True})
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda n:(a,b)[n].compare_replace(old[n],desired),range(2)))
    assert results.count(WriteResult.ACCEPTED)==1
    assert set(results)<={WriteResult.ACCEPTED,WriteResult.REJECTED,WriteResult.UNAVAILABLE}
    assert b.compare_replace(old[1],desired)==WriteResult.REJECTED
    assert a.read().document()==b.read().document()==desired
    assert inventory(config)==objects and set(objects)=={DB,JOURNAL}


def test_remote_stale_and_forced_takeover_share_same_leadership_conformance(remote):
    _,_,server=remote
    a,b=server.client("client-a"),server.client("client-b")
    x,y=(Leadership(p,actor=k,enrollment=ENROLLMENT) for p,k in ((a,ACTORS[0]),(b,ACTORS[1])))
    initial=x.acquire(x.observe(clock()),transition=tid("initial"),commissioning=True)
    grant=x.confirmed_grant(initial,x.commit(initial,mode="START"))
    takeover=y.acquire(y.observe(clock(220)),transition=tid("stale"))
    new=y.confirmed_grant(takeover,y.commit(takeover,mode="START"))
    assert new.epoch==2 and not x.current_before_dispatch(grant,clock(220))
    force=x.request_force(x.observe(clock(221)),request_id=tid("force"),user_requested=True)
    assert x.commit(force,mode="START").outcome=="CONFIRMED"
    assert not y.current_before_dispatch(new,clock(221))
    claim=x.claim_requested(x.observe(clock(221)),request_id=tid("force"))
    newest=x.confirmed_grant(claim,x.commit(claim,mode="START"))
    assert newest.epoch==3 and x.current_before_dispatch(newest,clock(221))


def test_remote_disconnect_reconnect_permissions_rename_and_lost_reply(remote):
    config,_,server=remote
    a=server.client("client-a");before=a.read();objects=inventory(config)
    server.stop()
    with pytest.raises(AuthorityError):a.read()
    assert inventory(config)==objects
    server.start()
    assert a.read().raw==before.raw
    journal=config.root/JOURNAL;journal.chmod(0)
    try:
        with pytest.raises(AuthorityError):a.read()
    finally:journal.chmod(0o600)
    held=config.root/"held-journal";journal.rename(held)
    try:
        with pytest.raises(AuthorityError):a.read()
        assert not journal.exists()
    finally:held.rename(journal)
    port=Intercept(server.transport("client-b"));b=FolderAuthority(port,BINDING,FolderAccess(BINDING,True,True))
    prior=b.read();desired=prior.document()
    desired["records"]["global.summary"].update(retention="BUSY",body={"lost_reply":True})
    port.lost=True
    assert b.compare_replace(prior,desired)==WriteResult.UNKNOWN
    assert a.read().document()==desired and port.writes==1 and inventory(config)==objects
    known=server.root/"known";saved=known.read_bytes()
    key=(server.root/"client-a.pub").read_text().split()[:2]
    known.write_text(f"[127.0.0.1]:{server.port} "+" ".join(key)+"\n")
    try:
        with pytest.raises(AuthorityError):a.read()
    finally:known.write_bytes(saved)
    assert a.read().document()==desired

