"""Actual Linux native mapping/physical AFTER and isolated fixed SSH."""
import base64
import os
from pathlib import Path
import sys
import pytest

from tb4.drive.commissioning import digest
from tb4.drive.commissioning_folder import ATTR
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority import DB, JOURNAL, FolderStore, identity
from tb4.drive.folder_connection import NativeFolderConnection
from tb4.drive.folder_mapping_after_probe import FolderMappingAfterProbe, after_header, handle_after_probe
from tb4.drive.folder_protocol import flat_json
from tb4.exchange_layout import encoded
from tb4.commissioning_state import storage_spec
from tb4.reconfiguration_effects import SLOT, KEY, ledger
from tests.drive.folder_retained_support import system
from tests.drive.folder_relocation_support import system as relocation_system
from test_folder_candidate_authenticated_ssh import staged
from test_folder_commissioning import context

pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='Actual native mapping AFTER/physical/fixed SSH')


def facts(s, *, expected=None):
    port=s.ctx.storage_port;config=port._config()
    row=FolderStore(config).read();doc=s.ctx.leadership.backend.read().document()
    plan=ledger(doc['records'][SLOT])['folder_plan'] if expected is None else expected
    _,handle=storage_spec(s.ctx.setup.private_choices()['storage'])
    req={**after_header(config.binding,'a'*32),'operation':'VERIFY_AFTER',
        'blueprint':port.spec.fingerprint,'authority':handle.seal,'mapping_sha256':plan['mapping_sha256']}
    return config,row,plan,req


def observe(config):
    return (FolderStore(config).read(),{p.name:identity(p) for p in config.root.iterdir()},
        {p.name:p.read_bytes() for p in config.root.iterdir() if p.name not in {DB,JOURNAL}})


def test_actual_native_after_attestation_retains_mapping_payload_and_physical_objects(context,tmp_path,monkeypatch):
    s=system(context,tmp_path);config,row,plan,req=facts(s)
    before,mapping=observe(config),s.ctx.storage_port.mapping.store.read()
    monkeypatch.setattr(FolderStore,'compare_replace',lambda *_:pytest.fail('AFTER proof attempted CAS'))
    result=flat_json(handle_after_probe(config,encoded(req),mapping_store=s.ctx.storage_port.mapping.store.native.root))
    assert result['result']=='VERIFIED' and result['mapping_sha256']==plan['mapping_sha256']
    assert result['revision']==row[0] and base64.b64decode(result['body'])==row[1]
    assert observe(config)==before and s.ctx.storage_port.mapping.store.read()==mapping


@pytest.mark.parametrize('fault',['before','missing-pointer','pending','hash','artifact','terminal'])
def test_actual_after_proof_refuses_unfinished_or_lost_native_mapping_and_seal_without_writes(context,tmp_path,fault):
    if fault=='before':
        s=relocation_system(context,tmp_path)
        assert s.relocation.begin(owner_authorized=True)=='PREPARED'
        expected=s.relocation._intent(s.relocation._state()[0])
    else:
        s=system(context,tmp_path)
        expected=None
    config,row,plan,req=facts(s,expected=expected)
    mapping=s.ctx.storage_port.mapping.store
    if fault=='hash':req['mapping_sha256']='c'*64
    if fault=='pending':
        with mapping.native.locked() as port:port.stage(port.read('settings.json'))
    if fault=='artifact':
        local=s.ctx.storage_port._port();key=local.spec.artifact_keys[0]
        path=local.root/local.prepare(key,local.spec.operation(key)).object_id
        os.setxattr(path,ATTR,b'SYNTHETIC_PRIVATE_CANARY')
    if fault=='terminal':
        doc=s.ctx.leadership.backend.read().document()
        doc['records'][SLOT]['body'][KEY]['entries']['IDENTITY']['outcome']='UNKNOWN'
        doc['records'][SLOT]['retention']='UNKNOWN'
        FolderStore(config).compare_replace(row[0],encoded(doc))
    before=observe(config)
    root=None if fault=='missing-pointer' else mapping.native.root
    reply=handle_after_probe(config,encoded(req),mapping_store=root)
    assert flat_json(reply)['result']=='UNKNOWN' and b'body' not in reply and b'SYNTHETIC_PRIVATE_CANARY' not in reply
    assert observe(config)==before


def test_actual_fixed_ssh_after_probe_returns_fresh_current_native_mapping_witness(staged,capsys):
    v=staged;before=observe(v.current);main,archive=v.s.ctx.setup.store.read(),v.s.candidate.context.archive.read()
    connection=NativeFolderConnection(v.profile,clock=lambda:v.now[0])
    probe=FolderMappingAfterProbe(connection.probe(v.access))
    plan=ledger(v.s.ctx.leadership.backend.read().document()['records'][SLOT])['folder_plan']
    first,second=probe.verify(plan),probe.verify(plan)
    assert first.plan==encoded(plan) and first.document()==second.document()
    assert first._origin is second._origin is probe._origin and observe(v.current)==before
    assert v.s.ctx.setup.store.read()==main and v.s.candidate.context.archive.read()==archive
    assert not v.s.candidate.view()['runtime_active'] and capsys.readouterr()==('','')


@pytest.mark.parametrize('fault',['key-permission','revoked','pending-mapping'])
def test_actual_fixed_ssh_after_proof_refuses_late_current_capability_or_mapping_loss(staged,fault):
    v=staged;connection=NativeFolderConnection(v.profile,clock=lambda:v.now[0])
    probe=FolderMappingAfterProbe(connection.probe(v.access))
    plan=ledger(v.s.ctx.leadership.backend.read().document()['records'][SLOT])['folder_plan']
    if fault=='key-permission':v.key.chmod(0o644)
    if fault=='revoked':
        current=v.profile.read();payload=current.payload;payload['credential_image']['bindings'][v.handle]['revoked']=True
        v.profile.save(payload,expected_revision=current.revision)
    if fault=='pending-mapping':
        store=v.port.mapping.store
        with store.native.locked() as port:port.stage(port.read('settings.json'))
    before,profile=observe(v.current),v.profile.read()
    with pytest.raises(AuthorityError,match='^MAPPING_AFTER_UNAVAILABLE$'):probe.verify(plan)
    assert observe(v.current)==before and v.profile.read()==profile

