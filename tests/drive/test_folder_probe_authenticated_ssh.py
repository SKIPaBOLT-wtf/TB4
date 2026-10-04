"""Required Linux native credential -> actual fixed SSH/helper -> actual first-run."""
from dataclasses import asdict
import getpass
import os
from pathlib import Path
import shutil
import sys

import pytest

from tb4.commissioning_checks import CommissionedStorage, Prerequisites, detect_environment, restore_setup_credentials
from tb4.commissioning_state import Setup, DenyActivation
from tb4.credential_contract import Outcome, Purpose
from tb4.credential_persistence import export_private
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority import FolderStore, identity
from tb4.drive.folder_first_run import RemoteFolderCommissioning
from tb4.drive.folder_probe import FolderProbe
from tb4.drive.folder_probe_transport import ProbeEndpoint, CredentialProbeProcess, credential_probe_pair
from tb4.drive.folder_protocol import FolderAccess, flat_json
from tb4.drive.folder_transport import FixedProcess
from tb4.private_settings import native_settings
from tb4.linux_key_native import LinuxKeyNative
from test_folder_commissioning import context
from test_folder_probe_native import prepared, helper_file
from test_folder_ssh import Server
from tests.security.test_first_run import Source, FACTS
from tests.security.test_ballpark_contract import fixture as descriptor_fixture

pytestmark=pytest.mark.skipif(sys.platform!="linux",reason="Actual Linux sealed-parent credential SSH proof")
TARGET="00000000-0000-4000-8000-000000000233"
TRUST="f"*64


@pytest.fixture
def authenticated(context,tmp_path):
    sshd=shutil.which("sshd") or ("/usr/sbin/sshd" if Path("/usr/sbin/sshd").exists() else None)
    ssh=shutil.which("ssh")
    if not sshd or not ssh:
        if os.environ.get("TB4_REQUIRE_FOLDER_SSH")=="1":pytest.fail("Required actual OpenSSH tools unavailable")
        pytest.skip("Optional local SSH fixture, required in CI")
    spec,port,bound,_=prepared(context)
    config=port._config()
    directory=tmp_path/"synthetic-ssh-private";directory.mkdir(mode=0o700)
    server=Server(directory,helper_file(tmp_path,config),sshd,ssh,probe=True)
    known=directory/"known";known.chmod(0o600)
    api=LinuxKeyNative()
    with api.open_key(str(known),api.identity().uid) as held:version=held.version
    endpoint=ProbeEndpoint(TARGET,TRUST,str(Path(ssh).resolve()),"127.0.0.1",
                           server.port,getpass.getuser(),str(known),version)
    private=tmp_path/"synthetic-first-run-private";private.mkdir(mode=0o700)
    profile=native_settings(private/"profile",create=True,owner_authorized=True)
    setup=Setup(profile,create=True)
    now=[100]
    def factory(installation):
        return credential_probe_pair(installation,endpoint,spec,bound,clock=lambda:now[0])
    store,resolver=factory(setup.installation_id)
    key=directory/"client-a"
    ref=store.select(path=str(key),target_id=TARGET,target_trust=TRUST,
        purposes=frozenset({Purpose.FOLDER_PROBE}),expires_at=200,access_mode="existing_key",
        launch_mode="headless",owner_authorized=True)
    handle=resolver.enroll(target_id=TARGET,target_trust=TRUST,store_locator=ref,
        purposes=frozenset({Purpose.FOLDER_PROBE}),expires_at=200,owner_authorized=True)
    setup.persist_credentials(store,resolver,[dict(handle=handle,target_id=TARGET,
        target_trust=TRUST,purposes=[Purpose.FOLDER_PROBE.value])])
    descriptor=descriptor_fixture()
    descriptor["installation_id"]=setup.installation_id;descriptor["domain_id"]=spec.domain_id
    setup.choose(dict(role="watchdog",storage={"spec":asdict(spec),"authority":bound.record()},
                      network_scope=[],descriptor=descriptor))
    def probe_for(selected):
        process=CredentialProbeProcess(selected,handle)
        return FolderProbe(process,spec,bound,FolderAccess(process.binding,True,True))
    def checker_for(selected):
        return Prerequisites(environment=lambda:detect_environment(launch_mode="DESKTOP_SESSION"),
            storage=CommissionedStorage(RemoteFolderCommissioning(probe_for(selected))),
            credentials=selected,source=Source(),runtime=FACTS,clock=lambda:now[0])
    try:
        yield dict(server=server,spec=spec,port=port,bound=bound,config=config,profile=profile,
            setup=setup,store=store,resolver=resolver,key=key,known=known,now=now,handle=handle,
            endpoint=endpoint,factory=factory,probe=probe_for,checker=checker_for)
    finally:server.stop()


def test_actual_sealed_parent_key_authenticates_then_restart_repeats_first_run_without_mutation(authenticated,monkeypatch,capsys):
    v=authenticated;before=FolderStore(v["config"]).read()
    original=FixedProcess.call;calls=[]
    def observe(process,raw):
        calls.append(flat_json(raw))
        # Actual OpenSSH must read the held parent fd, not inherit it or open the selected key.
        key_option=next(a for a in process.argv if a.startswith("-oIdentityFile="))
        known_option=next(a for a in process.argv if a.startswith("-oUserKnownHostsFile="))
        assert "/proc/"+str(os.getpid())+"/fd/" in key_option and "/proc/"+str(os.getpid())+"/fd/" in known_option
        assert str(v["key"]) not in key_option and str(v["known"]) not in known_option
        return original(process,raw)
    monkeypatch.setattr(FixedProcess,"call",observe)
    objects={p.name:identity(p) for p in v["config"].root.iterdir()}
    key_bytes=v["key"].read_bytes()
    assert v["setup"].review(v["checker"](v["resolver"]))["settings_validated"]
    saved=v["profile"].read()
    restarted=Setup(native_settings(v["profile"].native.root))
    restored=restore_setup_credentials(restarted,v["factory"])
    assert export_private(restored._store,restored)==saved.payload["credential_image"]
    result=restarted.activate(v["checker"](restored),DenyActivation())
    assert result["reason"]=="ACTIVATION_NOT_AUTHORIZED" and not result["runtime_active"]
    assert len(calls)==2 and calls[0]["nonce"]!=calls[1]["nonce"]
    after=v["profile"].read().payload
    for k in ("installation_id","setup_nonce","choices","operations","credential_image"):
        assert after[k]==saved.payload[k]
    assert FolderStore(v["config"]).read()==before
    assert objects=={p.name:identity(p) for p in v["config"].root.iterdir()}
    assert v["key"].read_bytes()==key_bytes
    assert key_bytes not in (v["profile"].native.root/"settings.json").read_bytes()
    assert capsys.readouterr()==("","")


@pytest.mark.parametrize("change",["key-version","key-permission","known-version","known-permission",
                                   "expired","revoked","disconnect","physical-missing"])
def test_actual_authenticated_prior_proof_does_not_allow_later_key_trust_or_physical_loss(authenticated,monkeypatch,change):
    v=authenticated;probe=v["probe"](v["resolver"]);probe.verify()
    prior=v["profile"].read();before=FolderStore(v["config"]).read()
    original=FixedProcess.call;calls=[]
    def observe(process,raw):
        calls.append(flat_json(raw))
        return original(process,raw)
    monkeypatch.setattr(FixedProcess,"call",observe)
    if change=="key-version":v["key"].write_bytes(b"synthetic-invalid-rotated-key")
    if change=="key-permission":v["key"].chmod(0o644)
    if change=="known-version":v["known"].write_bytes(b"synthetic-invalid-rotated-known")
    if change=="known-permission":v["known"].chmod(0o644)
    if change=="expired":v["now"][0]=200
    if change=="revoked":v["resolver"].revoke(v["handle"],owner_authorized=True)
    if change=="disconnect":v["server"].stop()
    if change=="physical-missing":
        slot=v["spec"].artifact_keys[0]
        path=v["port"].root/v["port"].prepare(slot,v["spec"].operation(slot)).object_id
        path.rename(v["port"].root/"held-synthetic-artifact")
    objects={p.name:identity(p) for p in v["config"].root.iterdir()}
    with pytest.raises(AuthorityError,match="^PROBE_UNAVAILABLE$"):probe.verify()
    assert len(calls)==(1 if change in {"disconnect","physical-missing"} else 0)
    assert probe.transport._runner._pending is None and v["profile"].read()==prior
    assert FolderStore(v["config"]).read()==before
    assert objects=={p.name:identity(p) for p in v["config"].root.iterdir()}
