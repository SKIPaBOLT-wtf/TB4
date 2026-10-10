"""Portable ACTIVE mapping boundaries; no synthetic physical acceptance."""
import base64
import sys
import pytest

from tb4.drive.docs_authority import AuthorityError, document_bytes
from tb4.drive.folder_mapping_active_probe import (
    FolderMappingActiveProbe, active_header, active_request, active_response)
from tb4.drive.folder_mapping_after_probe import after_response
from tb4.drive.folder_probe import FolderProbe
from tb4.drive.folder_probe_transport import FolderProbeRunner, probe_request
from tb4.drive.folder_protocol import FolderAccess, flat_json, handle
from tb4.drive.folder_transport import FixedProcess
from tb4.exchange_layout import encoded
from tb4.reconfiguration_effects import SLOT, KEY
from tb4.reconfiguration_root_plan import stable_records
from test_folder_mapping_after_probe import terminal, request as after_request
from test_folder_probe import SPEC, HANDLE, BINDING, DOMAIN
from test_folder_protocol import SyntheticPort
from test_native_leadership import ACTORS


def published():
    doc, plan = terminal()
    doc['records']['global.settings']['body']['configuration'].update(phase='ACTIVE', revision=2)
    summary = doc['records'][SLOT]['body'][KEY]
    del summary['folder_plan']
    summary['barrier'] = dict(transition_id=plan['transition_id'], source_owner=ACTORS[0],
                              source_epoch=1, local_clear=True)
    return doc, plan


def request(plan):
    return {**active_header(BINDING, 'a'*32), 'operation': 'VERIFY_ACTIVE',
            'blueprint': SPEC.fingerprint, 'authority': HANDLE.seal,
            'mapping_sha256': plan['mapping_sha256']}


def response(doc, plan, nonce='a'*32):
    return {**active_header(BINDING, nonce), 'result': 'VERIFIED', 'revision': 9,
            'body': base64.b64encode(document_bytes(doc)).decode(),
            'mapping_sha256': plan['mapping_sha256']}


def client(monkeypatch, transform=lambda r:r, document=None):
    doc, plan = published()
    if document is not None:doc = document
    calls = []
    runner = object.__new__(FolderProbeRunner)
    runner.binding, runner.spec, runner.authority = BINDING, SPEC, HANDLE
    def call(_port, raw):
        req = probe_request(BINDING, SPEC, HANDLE, raw);calls.append(req)
        reply = encoded(transform(response(doc, plan, req['nonce'])))
        runner._response(reply, req)
        return reply
    monkeypatch.setattr(FixedProcess, 'call', call)
    probe = FolderMappingActiveProbe(FolderProbe(FixedProcess(BINDING, (sys.executable,)),
        SPEC, HANDLE, FolderAccess(BINDING, True, True)))
    return probe, plan, calls


def test_current_active_observation_is_fresh_and_does_not_reconstruct_old_stable_records(monkeypatch):
    p, plan, calls = client(monkeypatch)
    a, b = p.verify(plan), p.verify(plan)
    assert a.document() == b.document() == published()[0]
    assert a.plan == encoded(plan) and stable_records(a.document()) != plan['records_sha256']
    assert a._origin is b._origin is p._origin and calls[0]['nonce'] != calls[1]['nonce']
    assert len(calls[0]) == len(response(a.document(), plan)) == 9
    assert not any(hasattr(p, n) for n in ('compare_replace','activate','allocate','request_force'))
    with pytest.raises(AuthorityError):
        after_response(BINDING, SPEC, HANDLE, encoded(response(a.document(), plan)), after_request(plan))
    with pytest.raises(AuthorityError):
        active_response(BINDING, SPEC, HANDLE, encoded(response(a.document(), plan)), after_request(plan))


def test_saved_active_reply_cannot_attest_a_second_observation(monkeypatch):
    saved = []
    def replay(row):
        if not saved:saved.append(row)
        return saved[0]
    p, plan, calls = client(monkeypatch, replay)
    p.verify(plan)
    with pytest.raises(AuthorityError, match='^MAPPING_ACTIVE_UNAVAILABLE$'):p.verify(plan)
    assert len(calls) == 2


@pytest.mark.parametrize('field,value', [
    ('mode','FOLDER_MAPPING_AFTER_PROBE_V1'), ('nonce','b'*32), ('root',DOMAIN),
    ('domain',BINDING.root_id), ('mapping_sha256','b'*64), ('revision',True),
    ('revision',0), ('result','UNKNOWN'), ('body','bad'), ('path','SYNTHETIC_PRIVATE_CANARY'),
    ('blueprint',SPEC.fingerprint), ('authority',HANDLE.seal)])
def test_runner_and_client_refuse_uncorrelated_or_untyped_active_reply(monkeypatch, field, value):
    p, plan, _ = client(monkeypatch, lambda r:{**r, field:value})
    with pytest.raises(AuthorityError, match='^MAPPING_ACTIVE_UNAVAILABLE$'):p.verify(plan)


@pytest.mark.parametrize('field,value', [
    ('operation','VERIFY_AFTER'), ('mode','FOLDER_MAPPING_AFTER_PROBE_V1'),
    ('path','SYNTHETIC_PRIVATE_CANARY'), ('blueprint','b'*64), ('authority','b'*64),
    ('mapping_sha256',True), ('mapping_sha256','bad'), ('root',DOMAIN), ('nonce','bad')])
def test_closed_active_request_refuses_before_native_or_transport_io(field, value):
    _, plan = published();raw = encoded({**request(plan), field:value})
    with pytest.raises(AuthorityError):active_request(BINDING, SPEC, HANDLE, raw)
    with pytest.raises(AuthorityError):probe_request(BINDING, SPEC, HANDLE, raw)


@pytest.mark.parametrize('fault', ['maintenance','missing-barrier','unresolved','identity',
                                   'old-plan','transition'])
def test_active_reply_needs_exact_terminal_current_transition(monkeypatch, fault):
    doc, plan = published();summary = doc['records'][SLOT]['body'][KEY]
    if fault == 'maintenance':doc['records']['global.settings']['body']['configuration']['phase'] = 'MAINTENANCE'
    if fault == 'missing-barrier':summary['barrier'] = None
    if fault == 'unresolved':
        summary['entries']['IDENTITY']['outcome'] = 'UNKNOWN'
        doc['records'][SLOT]['retention'] = 'UNKNOWN'
    if fault == 'identity':summary['entries']['IDENTITY']['operation_id'] = 'b'*64
    if fault == 'old-plan':summary['folder_plan'] = plan
    if fault == 'transition':doc['records']['global.settings']['body']['configuration']['transition_id'] = 'b'*64
    p, plan, _ = client(monkeypatch, document=doc)
    with pytest.raises(AuthorityError, match='^MAPPING_ACTIVE_UNAVAILABLE$'):p.verify(plan)


@pytest.mark.parametrize('fault', ['probe','transport','origin'])
def test_changed_trusted_active_composition_never_calls_transport(monkeypatch, fault):
    p, plan, calls = client(monkeypatch)
    if fault == 'probe':p._after = object()
    if fault == 'transport':p._after.probe.transport = object()
    if fault == 'origin':p._origin = object()
    with pytest.raises(AuthorityError, match='^MAPPING_ACTIVE_UNAVAILABLE$'):p.verify(plan)
    assert not calls


@pytest.mark.parametrize('field', ['blueprint_sha256','handle_sha256','authority','schema_version'])
def test_invalid_expected_plan_never_calls_transport(monkeypatch, field):
    p, plan, calls = client(monkeypatch)
    plan[field] = dict(root_id=DOMAIN, domain_id=BINDING.root_id) if field == 'authority' else (
        True if field == 'schema_version' else 'b'*64)
    with pytest.raises(AuthorityError, match='^MAPPING_ACTIVE_UNAVAILABLE$'):p.verify(plan)
    assert not calls


def test_default_authority_cannot_execute_active_probe():
    _, plan = published();port = SyntheticPort()
    assert flat_json(handle(port, encoded(request(plan)))) == dict(result='UNKNOWN')
    assert port.commits == 0

