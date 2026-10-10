"""Actual native cold Main recovery; old in-memory transports are unavailable."""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import pytest

from tb4 import reconfiguration_native_folder_adoption as adoption_module
from tb4.configuration_contract import ConfigurationError
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority import FolderStore
from tb4.drive.folder_connection import NativeFolderConnection
from tb4.drive.folder_protocol import flat_json
from tb4.drive.folder_transport import FixedProcess
from tb4.drive.leadership import Leadership
from tb4.private_settings import PrivateSettings, SettingsError, encoded
from tb4.reconfiguration_native_folder_adoption import (
    NativeFolderActiveAdoption, _PendingMainProof, recover_native_folder_main,
    native_current_folder_admission)
from test_native_folder_active_adoption_authenticated_ssh import own
from test_folder_commissioning import context
from test_native_leadership import ACTORS, tid

pytestmark=pytest.mark.skipif(sys.platform!='linux',
    reason='Actual native cold Main pending recovery with fixed SSH')


def recover(v, *, authorized=True):
    local=v.local;old=local.checker;port=old.storage.port
    return recover_native_folder_main(local.profile,v.ctx.profile,v.ctx.archive,
        v.ctx.transaction,local.checkpoint,access=port._access,environment=old.environment,
        credential_clock=port._connection._clock,clock=local.clock,capabilities=local.capabilities,
        source=old.source,runtime=old.runtime,enrollment=local.leadership.enrollment,
        owner_authorized=authorized)


def cut(v, monkeypatch, *, after=False):
    assert v.adoption.begin(owner_authorized=True)['phase']=='STAGED'
    assert v.adoption.prepare(owner_authorized=True,decided_at=v.local.clock().utc)=='PREPARED'
    main=v.local.profile;locked=main.native.locked
    @contextmanager
    def interrupted():
        with locked() as port:
            promote=port.promote
            def stop():
                if after:promote()
                raise OSError('SYNTHETIC_OWN_MAIN_CUT')
            port.promote=stop
            yield port
    monkeypatch.setattr(main.native,'locked',interrupted)
    with pytest.raises(SettingsError,match='^SETTINGS_STORE_UNAVAILABLE$'):
        v.adoption.advance(owner_authorized=True)
    monkeypatch.setattr(main.native,'locked',locked)


def frames(v):
    with v.local.profile.native.locked() as port:
        return port.read('settings.json'),port.read('settings.pending')


def changed_child(v):
    main=v.local.profile
    with main.native.locked() as port:
        frame=json.loads(port.read('settings.pending'))
        frame['payload']['operations'][tid('synthetic-pending-child-change')]='UNKNOWN'
        frame.pop('digest')
        frame['digest']=hashlib.sha256(encoded(frame)).hexdigest()
        # Deliberate corruption of this existing owned fixture, never production IO.
        (Path(main.native.root)/'settings.pending').write_bytes(encoded(frame))


@pytest.mark.parametrize('after',[False,True])
def test_actual_cold_recovery_uses_frozen_own_stage_without_pending_main_connection_or_resave(
        own,monkeypatch,capsys,after):
    v=own;cut(v,monkeypatch,after=after)
    raw,pending=frames(v);cp=v.local.checkpoint.read()
    shared=FolderStore(v.s.port._config()).read()
    archive=v.ctx.archive.read();transaction=v.ctx.transaction.read()
    if not after:
        with pytest.raises(SettingsError):
            NativeFolderConnection(v.local.profile,clock=lambda:v.now[0])
    def unavailable(*_args,**_kwargs):pytest.fail('Cold recovery used old transport/adopter or wrote a new frame')
    monkeypatch.setattr(v.adoption,'_proof',unavailable)
    monkeypatch.setattr(v.local.leadership.backend,'read',unavailable)
    monkeypatch.setattr(v.local.checker.storage.port,'verify',unavailable)
    monkeypatch.setattr(PrivateSettings,'_save_locked',unavailable)
    original=FixedProcess.call;operations=[]
    def readonly(process,request):
        operation=flat_json(request)['operation'];operations.append(operation)
        assert operation in {'READ','VERIFY','VERIFY_AFTER','VERIFY_ACTIVE'}
        return original(process,request)
    monkeypatch.setattr(FixedProcess,'call',readonly)
    assert recover(v)==('NO_PENDING' if after else 'INSPECT_REQUIRED')
    assert frames(v)==((raw if after else pending),None)
    assert recover(v)=='NO_PENDING'
    frame=v.local.profile.read()
    assert frame.previous==v.before.payload and frame.payload['state']=='INCOMPLETE'
    assert v.local.checkpoint.read()==cp and cp.maintenance is not None
    assert v.ctx.archive.read()==archive and v.ctx.transaction.read()==transaction
    assert FolderStore(v.s.port._config()).read()==shared
    fresh=native_current_folder_admission(v.local)
    assert NativeFolderActiveAdoption(replace(v.ctx,local=fresh.context)).inspect()=='PROFILE_PROMOTED'
    assert not fresh.status()['runtime_active'] and capsys.readouterr()==('','')
    if not after:assert operations


@pytest.mark.parametrize('fault',['owner','stage','archive','child','endpoint','key','source','force'])
def test_actual_cold_recovery_keeps_pending_and_parent_when_current_facts_no_longer_qualify(
        own,monkeypatch,fault):
    v=own;cut(v,monkeypatch)
    if fault=='stage':
        frame=v.ctx.profile.read();value=frame.payload;value['choices']['network_scope']=['203.0.113.0/24']
        v.ctx.profile.save(value,expected_revision=frame.revision)
    if fault=='archive':
        frame=v.ctx.archive.read()
        v.ctx.archive.save(frame.payload,expected_revision=frame.revision)
    if fault=='child':changed_child(v)
    if fault=='endpoint':
        with v.metadata.native.locked() as port:port.stage(port.read('settings.json'))
    if fault=='key':v.key.chmod(0o644)
    if fault=='source':
        v.s.source.catalog['profiles'][0]['status']='REVOKED';v.s.source.save()
    if fault=='force':
        other=Leadership(v.s.local.leadership.backend,actor=ACTORS[0],
            enrollment=v.local.leadership.enrollment,profile=v.local.leadership.profile)
        plan=other.request_force(other.observe(v.local.clock()),request_id=tid('pending-own-main-force'),
                                 user_requested=True)
        assert other.commit(plan,mode='START').outcome=='CONFIRMED'
    before=frames(v);cp=v.local.checkpoint.read();shared=FolderStore(v.s.port._config()).read()
    def forbidden(*_args,**_kwargs):pytest.fail('Unqualified pending recovery reached transport')
    if fault in {'owner','stage','archive','child'}:monkeypatch.setattr(FixedProcess,'call',forbidden)
    with pytest.raises((SettingsError,ConfigurationError,AuthorityError)):
        recover(v,authorized=fault!='owner')
    assert frames(v)==before and v.local.checkpoint.read()==cp
    assert FolderStore(v.s.port._config()).read()==shared


def test_actual_cold_recovery_checks_same_pending_bytes_after_final_readonly_proof(own,monkeypatch):
    v=own;cut(v,monkeypatch);raw,_=frames(v)
    original=_PendingMainProof._qualified;guard=adoption_module.require
    changed_pending=[];failed=[]
    def changed(proof,*args,**kwargs):
        result=original(proof,*args,**kwargs)
        changed_child(v)
        changed_pending.append(frames(v)[1])
        return result
    def observe(condition,code='CONFIGURATION_INVALID'):
        if not condition:failed.append(code)
        return guard(condition,code)
    monkeypatch.setattr(_PendingMainProof,'_qualified',changed)
    monkeypatch.setattr(adoption_module,'require',observe)
    shared=FolderStore(v.s.port._config()).read()
    with pytest.raises(SettingsError,match='^SETTINGS_STORE_UNAVAILABLE$'):recover(v)
    assert len(changed_pending)==1 and changed_pending[0] is not None
    assert failed==['ACTIVE_ADOPTION_RECOVERY']
    assert frames(v)==(raw,changed_pending[0])
    assert FolderStore(v.s.port._config()).read()==shared


def test_native_adoption_cannot_silently_change_own_endpoint_in_stage(own):
    v=own
    assert v.adoption.begin(owner_authorized=True)['phase']=='STAGED'
    frame=v.ctx.profile.read();value=frame.payload;value['folder_endpoint']=None
    v.ctx.profile.save(value,expected_revision=frame.revision)
    before=v.local.profile.read();shared=FolderStore(v.s.port._config()).read()
    with pytest.raises(ConfigurationError,match='^ACTIVE_ADOPTION_PROFILE$'):
        v.adoption.prepare(owner_authorized=True,decided_at=v.local.clock().utc)
    assert v.local.profile.read()==before and FolderStore(v.s.port._config()).read()==shared

