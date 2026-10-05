"""Portable boundary tests; synthetic replies never qualify physical AFTER."""
import base64
from dataclasses import asdict
import sys
import pytest

from tb4.drive.commissioning import digest
from tb4.drive.docs_authority import AuthorityError, document_bytes
from tb4.drive.folder_mapping_after_probe import (FolderMappingAfterProbe, after_header,
    after_request, handle_after_probe)
from tb4.drive.folder_probe import FolderProbe, handle_probe
from tb4.drive.folder_probe_transport import probe_request
from tb4.drive.folder_protocol import FolderAccess, flat_json, handle
from tb4.drive.folder_transport import FixedProcess
from tb4.exchange_layout import encoded
from tb4.reconfiguration_effects import SLOT, KEY
from tb4.reconfiguration_root_plan import stable_records
from tb4.timing_contract import TimingProfile
from tb4.watchdog.leadership_runtime import Action
from test_folder_probe import SPEC, HANDLE, BINDING, DOMAIN, document
from test_folder_protocol import SyntheticPort
from test_native_leadership import ACTORS, tid


def terminal():
    doc=document();transition=tid('mapping-after-portable');mapping='a'*64
    plan=dict(schema_version=1,mode='FOLDER_SQLITE_V1',transition_id=transition,
        operation_id=digest(['folder-relocation',transition,mapping]),
        authority=dict(root_id=BINDING.root_id,domain_id=BINDING.domain_id),
        blueprint_sha256=SPEC.fingerprint,handle_sha256=digest(HANDLE.record()),
        mapping_sha256=mapping,records_sha256='a'*64)
    doc['records']['global.settings']=dict(generation=1,operation_id=tid('mapping-after-config'),
        retention='RETAINED',body=dict(descriptor_state='VALIDATED',revision=1,
        timing=asdict(TimingProfile()),configuration=dict(schema_version=1,revision=1,
        phase='MAINTENANCE',transition_id=transition)))
    plan['records_sha256']=stable_records(doc)
    doc['records'][SLOT]=dict(generation=1,operation_id=plan['operation_id'],retention='RETAINED',
        body={KEY:dict(schema_version=1,coverage_epoch=1,entries={Action.IDENTITY.value:
        dict(owner=ACTORS[0],epoch=1,operation_id=plan['operation_id'],outcome='COMPLETE')},
        barrier=None,folder_plan=plan)})
    return doc,plan


def request(plan):
    return {**after_header(BINDING,'a'*32), 'operation':'VERIFY_AFTER',
        'blueprint':SPEC.fingerprint,'authority':HANDLE.seal,'mapping_sha256':plan['mapping_sha256']}


def client(monkeypatch,transform=lambda r:r):
    doc,plan=terminal();calls=[]
    def call(_port,raw):
        req=flat_json(raw);calls.append(req)
        return encoded(transform({**after_header(BINDING,req['nonce']), 'result':'VERIFIED',
            'revision':7,'body':base64.b64encode(document_bytes(doc)).decode(),
            'mapping_sha256':plan['mapping_sha256']}))
    monkeypatch.setattr(FixedProcess,'call',call)
    p=FolderMappingAfterProbe(FolderProbe(FixedProcess(BINDING,(sys.executable,)),
        SPEC,HANDLE,FolderAccess(BINDING,True,True)))
    return p,plan,calls


def test_exact_fresh_hash_attestation_has_no_mutating_or_activation_api(monkeypatch):
    p,plan,calls=client(monkeypatch);a,b=p.verify(plan),p.verify(plan)
    assert a.document()==b.document()==terminal()[0] and a.plan==encoded(plan)
    assert a._origin is b._origin is p._origin and calls[0]['nonce']!=calls[1]['nonce']
    assert len(calls[0])==9 and probe_request(BINDING,SPEC,HANDLE,encoded(calls[0]))==calls[0]
    assert not any(hasattr(p,n) for n in ('compare_replace','allocate','activate','request_force'))


def test_old_reply_cannot_attest_next_observation(monkeypatch):
    saved=[]
    def replay(row):
        if not saved:saved.append(row)
        return saved[0]
    p,plan,calls=client(monkeypatch,replay);p.verify(plan)
    with pytest.raises(AuthorityError,match='^MAPPING_AFTER_UNAVAILABLE$'):p.verify(plan)
    assert len(calls)==2


@pytest.mark.parametrize('field,value',[('mode','FOLDER_SQLITE_V1'),('nonce','b'*32),
    ('root',DOMAIN),('mapping_sha256','b'*64),('revision',True),('revision',0),
    ('result','UNKNOWN'),('body','bad'),('path','SYNTHETIC_PRIVATE_CANARY')])
def test_unmatched_or_untyped_reply_cannot_attest(monkeypatch,field,value):
    p,plan,_=client(monkeypatch,lambda r:{**r,field:value})
    with pytest.raises(AuthorityError,match='^MAPPING_AFTER_UNAVAILABLE$'):p.verify(plan)


@pytest.mark.parametrize('field,value',[('operation','CAS'),('path','SYNTHETIC_PRIVATE_CANARY'),
    ('blueprint','bad'),('authority','bad'),('mapping_sha256','bad'),('mapping_sha256',True),
    ('mode','FOLDER_SQLITE_V1'),('root',DOMAIN),('domain',BINDING.root_id),('nonce','invalid')])
def test_closed_request_refuses_before_transport_or_mapping_io(monkeypatch,field,value):
    _,plan=terminal();raw=encoded({**request(plan),field:value})
    with pytest.raises(AuthorityError):after_request(BINDING,SPEC,HANDLE,raw)
    with pytest.raises(AuthorityError):probe_request(BINDING,SPEC,HANDLE,raw)


@pytest.mark.parametrize('field',['blueprint_sha256','handle_sha256','authority','schema_version'])
def test_invalid_expected_plan_refuses_before_transport(monkeypatch,field):
    p,plan,calls=client(monkeypatch)
    plan[field]=dict(root_id=DOMAIN,domain_id=BINDING.root_id) if field=='authority' else (
        True if field=='schema_version' else 'b'*64)
    with pytest.raises(AuthorityError,match='^MAPPING_AFTER_UNAVAILABLE$'):p.verify(plan)
    assert not calls


@pytest.mark.parametrize('fault',['probe','transport','origin'])
def test_changed_trusted_composition_refuses_before_transport(monkeypatch,fault):
    p,plan,calls=client(monkeypatch)
    if fault=='probe':p.probe=object()
    elif fault=='transport':p.probe.transport=object()
    else:p._origin=object()
    with pytest.raises(AuthorityError,match='^MAPPING_AFTER_UNAVAILABLE$'):p.verify(plan)
    assert not calls


def test_default_authority_handler_rejects_after_probe_without_cas():
    _,plan=terminal();port=SyntheticPort()
    assert flat_json(handle(port,encoded(request(plan))))==dict(result='UNKNOWN') and port.commits==0


def runner_response():
    # Pure parser boundary only; no key, native runner or SSH invocation.
    from tb4.drive.folder_probe_transport import FolderProbeRunner
    doc,plan=terminal()
    runner=object.__new__(FolderProbeRunner)
    runner.binding,runner.spec,runner.authority=BINDING,SPEC,HANDLE
    reply={**after_header(BINDING,'a'*32), 'result':'VERIFIED', 'revision':7,
        'body':base64.b64encode(document_bytes(doc)).decode(), 'mapping_sha256':plan['mapping_sha256']}
    return runner,doc,plan,reply


def test_actual_runner_validates_after_pair_and_retains_old_normal_response_guard():
    from tb4.drive.folder_probe import probe_header
    runner,_,plan,reply=runner_response()
    runner._response(encoded(reply),request(plan))
    normal={**probe_header(BINDING,'a'*32), 'result':'VERIFIED', 'revision':7,
        'body':reply['body'], 'blueprint':SPEC.fingerprint, 'authority':HANDLE.seal}
    normal_request={**probe_header(BINDING,'a'*32), 'operation':'VERIFY',
        'blueprint':SPEC.fingerprint, 'authority':HANDLE.seal}
    runner._response(encoded(normal),normal_request)
    with pytest.raises(AuthorityError,match='^PROBE_MODE$'):
        runner._response(encoded(reply),normal_request)
    with pytest.raises(AuthorityError,match='^MAPPING_AFTER_RESPONSE$'):
        runner._response(encoded(normal),request(plan))


@pytest.mark.parametrize('field,value',[('mode','FOLDER_SQLITE_V1'),('nonce','b'*32),
    ('root',DOMAIN),('domain',BINDING.root_id),('mapping_sha256','b'*64),
    ('revision',True),('revision',0),('result','UNKNOWN'),('body','bad'),
    ('path','SYNTHETIC_PRIVATE_CANARY'),('blueprint',SPEC.fingerprint),('authority',HANDLE.seal)])
def test_actual_runner_refuses_malformed_or_uncorrelated_after_reply(field,value):
    runner,_,plan,reply=runner_response()
    with pytest.raises(AuthorityError):
        runner._response(encoded({**reply,field:value}),request(plan))


@pytest.mark.parametrize('fault',['identity-unknown','configuration-active','handle'])
def test_actual_runner_after_reply_requires_terminal_exact_current_plan(fault):
    runner,doc,plan,reply=runner_response()
    if fault=='identity-unknown':
        doc['records'][SLOT]['body'][KEY]['entries'][Action.IDENTITY.value]['outcome']='UNKNOWN'
        doc['records'][SLOT]['retention']='UNKNOWN'
    elif fault=='configuration-active':
        doc['records']['global.settings']['body']['configuration']['phase']='ACTIVE'
    else:
        doc['records'][SLOT]['body'][KEY]['folder_plan']['handle_sha256']='b'*64
    reply['body']=base64.b64encode(document_bytes(doc)).decode()
    with pytest.raises(AuthorityError):runner._response(encoded(reply),request(plan))

