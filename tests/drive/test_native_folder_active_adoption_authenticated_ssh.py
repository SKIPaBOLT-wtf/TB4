"""Actual own native ACTIVE adoption/current runtime over fixed SSH, no old stores."""
from contextlib import contextmanager
from dataclasses import replace
import getpass
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

from tb4.commissioning_checks import detect_environment
from tb4.commissioning_state import Setup,DenyActivation,storage_spec
from tb4.configuration_contract import ConfigurationError
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority import FolderStore
from tb4.drive.folder_authority_transport import credential_authority_pair
from tb4.drive.folder_endpoint import NativeFolderEndpoint
from tb4.drive.folder_endpoint_attachment import NativeFolderEndpointAttachment
from tb4.drive.folder_prerequisites import native_folder_prerequisites
from tb4.drive.folder_probe_transport import ProbeEndpoint
from tb4.drive.leadership import Leadership
from tb4.linux_key_native import LinuxKeyNative
from tb4.private_settings import native_settings,SettingsError
from tb4.reconfiguration_active_adoption import ActiveAdoptionContext
from tb4.reconfiguration_effects import Effects
from tb4.reconfiguration_native_folder_adoption import NativeFolderActiveAdoption,native_current_folder_admission
from tb4.reconfiguration_retained import work_sha
from tb4.watchdog.leadership_runtime import Work,Action,NativeWatchdogContext,NativeWatchdogRuntime
from test_folder_commissioning import context
from test_folder_ssh import Server
from test_folder_candidate_authenticated_ssh import TARGET,TRUST,SCOPES
from test_native_leadership import ACTORS,tid
from tests.drive.folder_active_adoption_support import system as base

pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='Actual own native ACTIVE adoption/fixed SSH')


@pytest.fixture
def own(context,tmp_path,request):
    import shutil
    s=base(context,tmp_path,moved=getattr(request,'param',True))
    directory=tmp_path/'owned-native-current-role-server';directory.mkdir(mode=0o700)
    # Precommissioned server metadata remains independent of former client files.
    expected=s.former.ctx.storage_port.expected
    helper=directory/'helper.json'
    helper.write_text(json.dumps(dict(version=1,root=expected.binding.root_id,domain=expected.binding.domain_id,
        path=str(expected.root),root_dev=expected.root_identity[0],root_ino=expected.root_identity[1],
        db_dev=expected.db_identity[0],db_ino=expected.db_identity[1],
        journal_dev=expected.journal_identity[0],journal_ino=expected.journal_identity[1])),encoding='utf-8')
    helper.chmod(0o600)
    sshd=shutil.which('sshd') or '/usr/sbin/sshd';ssh=shutil.which('ssh')
    server=Server(directory,helper,sshd,ssh,dispatch=True,
        mapping_store=Path(s.former.ctx.storage_port.mapping.store.native.root))
    try:
        known=directory/'known';known.chmod(0o600);key=directory/'client-a'
        native=LinuxKeyNative()
        with native.open_key(str(known),native.identity().uid) as held:version=held.version
        endpoint=ProbeEndpoint(TARGET,TRUST,str(Path(ssh).resolve()),'127.0.0.1',server.port,getpass.getuser(),str(known),version)
        model=Setup(s.local.profile);now=[s.local.clock().utc]
        store,resolver=credential_authority_pair(model.installation_id,endpoint,s.local.leadership.backend.binding,clock=lambda:now[0])
        locator=store.select(path=str(key),target_id=TARGET,target_trust=TRUST,purposes=SCOPES,
            expires_at=now[0]+1000,access_mode='existing_key',launch_mode='headless',owner_authorized=True)
        handle=resolver.enroll(target_id=TARGET,target_trust=TRUST,store_locator=locator,purposes=SCOPES,
            expires_at=now[0]+1000,owner_authorized=True)
        model.persist_credentials(store,resolver,[dict(handle=handle,target_id=TARGET,target_trust=TRUST,
            purposes=sorted(p.value for p in SCOPES))])
        metadata=native_settings(tmp_path/'own-current-role-endpoint',create=True,owner_authorized=True)
        selected=NativeFolderEndpoint(metadata,model.installation_id)
        reference=selected.prepare(model,endpoint,handle,owner_authorized=True)
        NativeFolderEndpointAttachment(selected,model.store).attach(model,reference,owner_authorized=True)
        from tb4.drive.folder_protocol import FolderAccess
        access=FolderAccess(s.local.leadership.backend.binding,True,True)
        checker=native_folder_prerequisites(model.store,access=access,environment=lambda:detect_environment(launch_mode='EXTERNAL'),
            source=s.local.checker.source,runtime=s.local.checker.runtime,clock=lambda:now[0],normal_authority=True)
        _,authority=storage_spec(model.private_choices()['storage'])
        leader=Leadership(checker.storage.port.authority(authority),actor=model.installation_id,
            enrollment=s.local.leadership.enrollment,profile=s.local.leadership.profile)
        local=replace(s.local,leadership=leader,checker=checker)
        ctx=replace(s.context,local=local)
        before=local.profile.read()
        yield SimpleNamespace(s=s,local=local,ctx=ctx,adoption=NativeFolderActiveAdoption(ctx),
            before=before,metadata=metadata,handle=handle,key=key,server=server,now=now)
    finally:server.stop()


def finish(v):
    assert v.adoption.begin(owner_authorized=True)['phase']=='STAGED'
    assert v.adoption.prepare(owner_authorized=True,decided_at=v.local.clock().utc)=='PREPARED'
    assert v.adoption.advance(owner_authorized=True)=='PROFILE_PROMOTED'
    admission=native_current_folder_admission(v.local)
    assert admission.release(owner_authorized=True)==2 and admission.revision()==2
    return admission


def runtime(v,a):
    effects=Effects(a.context.leadership,v.local.checkpoint,v.s.effects.store)
    return NativeWatchdogRuntime(NativeWatchdogContext(a.context.leadership,v.local.checkpoint,
        v.local.capabilities,v.local.clock,lambda:None,configuration_revision=a.revision,effects=effects))


@pytest.mark.parametrize('own',[False,True],indirect=True)
def test_actual_native_current_role_adopts_active_without_former_client_and_retains_own_full_history(own,capsys):
    v=own;shared=v.local.leadership.backend.read().document();cp=v.local.checkpoint.read()
    a=finish(v);frame=v.local.profile.read()
    assert frame.previous==v.before.payload and v.ctx.archive.read().payload['profile']==v.before.payload
    for field in ('installation_id','setup_nonce','operations','credential_image','network_table','folder_endpoint'):
        assert frame.payload.get(field)==v.before.payload.get(field)
    assert frame.payload['choices']['timing']==v.s.timing and a.context.leadership.profile.control_s==7
    assert v.local.checkpoint.read().grant.epoch==cp.grant.epoch==2
    assert v.local.leadership.backend.read().document()==shared
    assert Setup(v.local.profile).activate(a.context.checker,DenyActivation())['reason']=='ACTIVATION_NOT_AUTHORIZED'
    assert not a.status()['runtime_active'] and capsys.readouterr()==('','')


@pytest.mark.parametrize('outcome',['COMPLETE','UNKNOWN'])
def test_actual_current_native_main_runtime_uses_fresh_admission_once_after_adoption_stores_unavailable(own,outcome):
    v=own;a=finish(v);frame=v.local.profile.read();before=v.local.leadership.backend.read().document()
    def absent(*_args,**_kwargs):raise OSError('SYNTHETIC_OWN_ADOPTION_STORE_UNAVAILABLE')
    for store in (v.ctx.profile,v.ctx.archive,v.ctx.transaction):store.read=store.save=absent
    a=native_current_folder_admission(v.local);runner=runtime(v,a);assert runner.tick()
    calls=[];work=Work(Action.SSH,tid('own-native-active-new-work'),lambda *_args:calls.append(True) or outcome)
    assert runner.perform(work)==outcome and runner.perform(work)==outcome and calls==[True]
    assert a.revision()==2 and v.local.profile.read()==frame
    assert work_sha(v.local.leadership.backend.read().document())==work_sha(before)


@pytest.mark.parametrize('fault',['owner','forced','revoked','pending-endpoint'])
def test_actual_native_adoption_refuses_late_owner_role_or_current_capability_loss_before_stage_write(own,fault):
    v=own
    if fault=='forced':
        other=Leadership(v.local.leadership.backend,actor=ACTORS[0],enrollment=v.local.leadership.enrollment,profile=v.local.leadership.profile)
        plan=other.request_force(other.observe(v.local.clock()),request_id=tid('own-native-active-forced'),user_requested=True)
        assert other.commit(plan,mode='START').outcome=='CONFIRMED'
    if fault=='revoked':
        current=v.local.profile.read();payload=current.payload;payload['credential_image']['bindings'][v.handle]['revoked']=True
        v.local.profile.save(payload,expected_revision=current.revision)
    if fault=='pending-endpoint':
        with v.metadata.native.locked() as port:port.stage(port.read('settings.json'))
    profile,cp=v.local.profile.read(),v.local.checkpoint.read()
    with pytest.raises((AuthorityError,ConfigurationError,SettingsError)):
        v.adoption.begin(owner_authorized=fault!='owner')
    assert v.local.profile.read()==profile and v.local.checkpoint.read()==cp
    assert all(s.read() is None for s in (v.ctx.profile,v.ctx.archive,v.ctx.transaction))


@pytest.mark.parametrize('field',['profile','archive','transaction'])
def test_native_endpoint_metadata_cannot_alias_own_adoption_store_before_mutation(own,field):
    v=own;before=v.local.profile.read()
    with pytest.raises(ConfigurationError,match='^ACTIVE_ADOPTION_STORE_ALIAS$'):
        NativeFolderActiveAdoption(replace(v.ctx,**{field:v.metadata}))
    assert v.local.profile.read()==before


@pytest.mark.parametrize('after',[False,True])
def test_actual_native_adoption_transaction_cut_recovers_same_child_without_main_resave(own,monkeypatch,after):
    v=own
    assert v.adoption.begin(owner_authorized=True)['phase']=='STAGED'
    assert v.adoption.prepare(owner_authorized=True,decided_at=v.local.clock().utc)=='PREPARED'
    locked=v.ctx.transaction.native.locked
    @contextmanager
    def interrupted():
        with locked() as port:
            promote=port.promote
            def stop():
                if after:promote()
                raise OSError('SYNTHETIC_NATIVE_ADOPTION_TRANSACTION_CUT')
            port.promote=stop
            yield port
    monkeypatch.setattr(v.ctx.transaction.native,'locked',interrupted)
    with pytest.raises(SettingsError,match='^SETTINGS_STORE_UNAVAILABLE$'):
        v.adoption.advance(owner_authorized=True)
    monkeypatch.setattr(v.ctx.transaction.native,'locked',locked)
    main=v.local.profile.read()
    with v.ctx.transaction.native.locked() as port:
        pending,current=port.read('settings.pending'),port.read('settings.json')
    v.adoption.recover_local('transaction',owner_authorized=True)
    assert v.local.profile.read()==main
    with v.ctx.transaction.native.locked() as port:
        assert port.read('settings.pending') is None and port.read('settings.json')==(pending if pending is not None else current)
    assert v.adoption.inspect()=='PROFILE_PROMOTED'

