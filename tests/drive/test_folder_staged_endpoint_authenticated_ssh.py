"""Actual C1/native candidate endpoint replacement and isolated SSH proof."""
from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from tb4.commissioning_checks import detect_environment
from tb4.commissioning_state import Setup, DenyActivation
from tb4.configuration_contract import ConfigurationError
from tb4.credential_persistence import restore_private
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority_transport import credential_authority_pair
from tb4.drive.folder_endpoint import NativeFolderEndpoint
import tb4.drive.folder_endpoint_attachment as attachment_module
from tb4.drive.folder_endpoint_attachment import NativeFolderEndpointAttachment
from tb4.drive.folder_prerequisites import native_folder_prerequisites
from tb4.drive.folder_transport import FixedProcess
from tb4.linux_key_native import LinuxKeyNative
from tb4.private_settings import SettingsError, encoded, native_settings
from tb4.reconfiguration_candidate import Candidate
from tb4.reconfiguration_folder_endpoint import StagedFolderEndpoint
from test_folder_candidate_authenticated_ssh import staged, retained, SCOPES, TARGET, TRUST
from test_folder_commissioning import context
from test_folder_ssh import Server
from test_native_leadership import ACTORS, clock, tid

pytestmark = pytest.mark.skipif(sys.platform != "linux",
    reason="Actual C1/native staged endpoint and fixed loopback SSH")


def replacement(v, tmp_path, *, endpoint=None):
    metadata = native_settings(tmp_path/'replacement-endpoint', create=True, owner_authorized=True)
    selected = NativeFolderEndpoint(metadata, v.model.installation_id)
    reference = selected.prepare(Setup(v.profile), endpoint or v.endpoint, v.handle, owner_authorized=True)
    selected_port = StagedFolderEndpoint(v.s.candidate, selected)
    return SimpleNamespace(metadata=metadata, endpoint=selected, reference=reference,
        port=selected_port, expected=v.profile.read().payload['folder_endpoint'])


def checker(v):
    return native_folder_prerequisites(v.profile, access=v.access,
        environment=lambda:detect_environment(launch_mode='EXTERNAL'),
        source=v.s.ctx.source, runtime=v.s.ctx.runtime, clock=lambda:v.now[0])


def no_transport(monkeypatch):
    def forbidden(*_args, **_kwargs): pytest.fail('Metadata selection reached SSH or a credential key')
    monkeypatch.setattr(FixedProcess, 'call', forbidden)
    monkeypatch.setattr(LinuxKeyNative, 'open_key', forbidden)


def pending_bytes(v):
    with v.profile.native.locked() as port: return port.read('settings.pending')


def current_snapshot(store):
    # Private fixture observation only. Production Setup never accepts pending.
    with store.native.locked() as port: return store._decode(port.read('settings.json'),port.binding)


def cut(v, r, monkeypatch, *, after=False):
    locked = v.profile.native.locked
    @contextmanager
    def interrupted():
        with locked() as port:
            promote = port.promote
            def stop():
                if after: promote()
                raise OSError('SYNTHETIC_STAGED_ENDPOINT_COMMIT_CUT')
            port.promote = stop
            yield port
    monkeypatch.setattr(v.profile.native, 'locked', interrupted)
    with pytest.raises(SettingsError, match='^SETTINGS_STORE_UNAVAILABLE$'):
        r.port.select(r.reference, expected_selection=r.expected, owner_authorized=True)
    monkeypatch.setattr(v.profile.native, 'locked', locked)


@pytest.mark.parametrize('staged', [False, True], indirect=True)
def test_actual_candidate_switches_to_second_server_only_after_fresh_proof(staged, tmp_path, monkeypatch, capsys):
    v = staged
    directory = tmp_path/'second-owned-server'; directory.mkdir(mode=0o700)
    server = Server(directory, v.server.root/'helper.json', v.server.sshd, v.server.ssh,
        dispatch=True, mapping_store=v.mapping)
    try:
        known = directory/'known'; known.chmod(0o600)
        native = LinuxKeyNative()
        with native.open_key(str(known), native.identity().uid) as held: version = held.version
        endpoint = replace(v.endpoint, port=server.port, known_hosts=str(known), known_version=version)
        store, resolver = credential_authority_pair(v.model.installation_id, endpoint,
            v.port.binding, clock=lambda:v.now[0])
        old = v.profile.read().payload['credential_image']
        restore_private(old, store, resolver)
        ref = store.select(path=str(directory/'client-a'), target_id=TARGET, target_trust=TRUST,
            purposes=SCOPES, expires_at=1000, access_mode='existing_key', launch_mode='headless',
            owner_authorized=True)
        handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator=ref,
            purposes=SCOPES, expires_at=1000, owner_authorized=True)
        v.s.candidate.persist_credentials(store, resolver, [dict(handle=handle, target_id=TARGET,
            target_trust=TRUST, purposes=sorted(p.value for p in SCOPES))], owner_authorized=True)
        v.handle = handle
        r = replacement(v, tmp_path, endpoint=endpoint)
        before, profile, metadata = retained(v), v.profile.read(), r.metadata.read()
        with monkeypatch.context() as blocked:
            no_transport(blocked)
            result = r.port.select(r.reference, expected_selection=r.expected, owner_authorized=True)
            assert not result['settings_validated'] and not result['runtime_active']
            selected = v.profile.read()
            assert selected.previous == profile.payload and selected.revision == profile.revision+1
            assert {k:x for k,x in selected.payload.items() if k!='folder_endpoint'} == {
                k:x for k,x in profile.payload.items() if k!='folder_endpoint'}
            assert r.port.select(r.reference, expected_selection=r.expected, owner_authorized=True) == result
            assert v.profile.read() == selected
        assert r.metadata.read() == metadata and retained(v) == before
        v.server.stop()  # The new first-run proof cannot reach the former endpoint.
        restarted = Candidate(v.s.candidate.context)
        assert not restarted.view()['settings_validated']
        assert restarted.require_validated(checker(v)).revision == v.profile.read().revision
        assert retained(v) == before
        assert Setup(v.profile).activate(checker(v), DenyActivation())['reason']=='ACTIVATION_NOT_AUTHORIZED'
        assert capsys.readouterr()==('', '')
    finally:
        server.stop()


@pytest.mark.parametrize('fault', ['known-version', 'key-permission', 'revoked', 'expired'])
def test_new_pointer_metadata_does_not_hide_current_first_run_loss(staged, tmp_path, monkeypatch, fault):
    v = staged
    endpoint = replace(v.endpoint, known_version=v.endpoint.known_version+1) if fault=='known-version' else v.endpoint
    r = replacement(v, tmp_path, endpoint=endpoint)
    before = retained(v)
    r.port.select(r.reference, expected_selection=r.expected, owner_authorized=True)
    if fault=='key-permission': v.key.chmod(0o644)
    if fault=='expired': v.now[0]=1001
    if fault=='revoked':
        current=v.profile.read(); payload=current.payload
        payload['credential_image']['bindings'][v.handle]['revoked']=True
        v.profile.save(payload, expected_revision=current.revision)
    def forbidden(*_args, **_kwargs): pytest.fail('Lost current capability reached SSH')
    monkeypatch.setattr(FixedProcess, 'call', forbidden)
    report=Candidate(v.s.candidate.context).review(checker(v))
    assert not report['settings_validated'] and not report['runtime_active']
    assert retained(v)==before


@pytest.mark.parametrize('after', [False, True])
def test_actual_native_cut_recovers_same_child_without_resave_key_or_transport(staged, tmp_path, monkeypatch, after):
    v=staged; r=replacement(v,tmp_path); before,profile=retained(v),v.profile.read()
    cut(v,r,monkeypatch,after=after)
    pending=pending_bytes(v)
    if not after: assert pending is not None and current_snapshot(v.profile)==profile
    else: assert pending is None and v.profile.read().previous==profile.payload
    with monkeypatch.context() as blocked:
        no_transport(blocked)
        def forbidden(*_args, **_kwargs):pytest.fail('Recovery resaved a profile')
        blocked.setattr(v.profile.__class__, '_save_locked', forbidden)
        reopened=StagedFolderEndpoint(Candidate(v.s.candidate.context), r.endpoint)
        assert reopened.recover(r.reference,expected_selection=r.expected,owner_authorized=True)['status']=='SELECTED'
        selected=v.profile.read()
        assert reopened.recover(r.reference,expected_selection=r.expected,owner_authorized=True)['status']=='SELECTED'
        assert v.profile.read()==selected
    assert selected.previous==profile.payload and pending_bytes(v) is None
    if pending is not None:
        with v.profile.native.locked() as port:assert port.read('settings.json')==pending
    assert retained(v)==before and not v.s.candidate.view()['settings_validated']
    assert Candidate(v.s.candidate.context).require_validated(checker(v)).revision==v.profile.read().revision


@pytest.mark.parametrize('fault', ['owner', 'stale-selection', 'untyped-selection', 'ready',
    'unknown', 'revoked', 'pending-metadata', 'forced'])
def test_staged_pointer_refuses_missing_current_permission_identity_or_resolution(staged, tmp_path, monkeypatch, fault):
    v=staged; r=replacement(v,tmp_path); expected=r.expected; owner=True
    if fault=='owner':owner=False
    if fault=='stale-selection':expected={**expected,'binding_digest':'b'*64}
    if fault=='untyped-selection':expected=object()
    if fault=='ready':assert v.s.candidate.review(v.checker)['settings_validated']
    if fault in {'unknown','revoked'}:
        current=v.profile.read(); payload=current.payload
        if fault=='unknown':payload['operations']['f'*64]='UNKNOWN'
        else:payload['credential_image']['bindings'][v.handle]['revoked']=True
        v.profile.save(payload,expected_revision=current.revision)
    if fault=='pending-metadata':
        with r.metadata.native.locked() as port:port.stage(port.read('settings.json'))
    if fault=='forced':
        from tb4.drive.leadership import Leadership
        successor=Leadership(v.s.ctx.leadership.backend,actor=ACTORS[1],
            enrollment=v.s.ctx.leadership.enrollment)
        plan=successor.request_force(successor.observe(clock(220)),request_id=tid('staged-endpoint-force'),
            user_requested=True)
        assert successor.commit(plan,mode='START').outcome=='CONFIRMED'
    before,profile,metadata=retained(v),v.profile.read(),current_snapshot(r.metadata)
    no_transport(monkeypatch)
    with pytest.raises((AuthorityError,ConfigurationError,SettingsError)):
        r.port.select(r.reference,expected_selection=expected,owner_authorized=owner)
    assert v.profile.read()==profile and retained(v)==before and current_snapshot(r.metadata)==metadata


@pytest.mark.parametrize('fault', ['pointer', 'parent', 'revision', 'history'])
def test_altered_native_pending_child_refuses_recovery_without_promotion(staged,tmp_path,monkeypatch,fault):
    import hashlib
    v=staged;r=replacement(v,tmp_path);before,profile=retained(v),v.profile.read()
    cut(v,r,monkeypatch)
    with v.profile.native.locked() as port:
        raw=port.read('settings.pending');frame=json.loads(raw)
        if fault=='pointer':frame['payload']['folder_endpoint']['binding_digest']='c'*64
        if fault=='parent':frame['previous']['setup_nonce']='d'*64
        if fault=='revision':frame['revision']+=1
        if fault=='history':frame['payload']['operations']['e'*64]='CONFIRMED'
        frame.pop('digest');frame['digest']=hashlib.sha256(encoded(frame)).hexdigest()
        changed=encoded(frame)
        (Path(v.profile.native.root)/'settings.pending').write_bytes(changed)
    no_transport(monkeypatch)
    with pytest.raises((AuthorityError,ConfigurationError,SettingsError)):
        r.port.recover(r.reference,expected_selection=r.expected,owner_authorized=True)
    assert pending_bytes(v)==changed and current_snapshot(v.profile)==profile and retained(v)==before


def test_ordinary_attachment_cannot_replace_and_staged_context_cannot_use_original_main(staged,tmp_path,monkeypatch):
    v=staged;r=replacement(v,tmp_path);before,profile=retained(v),v.profile.read()
    no_transport(monkeypatch)
    ordinary=NativeFolderEndpointAttachment(r.endpoint,v.profile)
    failed=[]; original=attachment_module.require
    def observe(condition,code):
        if not condition:failed.append(code)
        return original(condition,code)
    monkeypatch.setattr(attachment_module,'require',observe)
    with pytest.raises(SettingsError,match='^SETTINGS_STORE_UNAVAILABLE$'):
        ordinary.attach(Setup(v.profile),r.reference,owner_authorized=True)
    assert failed==['FOLDER_ENDPOINT_ATTACHMENT_CONFLICT']
    with pytest.raises(AuthorityError,match='^STAGED_FOLDER_ENDPOINT_CONTEXT$'):
        StagedFolderEndpoint(Setup(v.s.ctx.setup.store),r.endpoint)
    assert v.profile.read()==profile and retained(v)==before


@pytest.mark.parametrize('fault',['alias','candidate','endpoint','link'])
def test_staged_composition_or_store_alias_cannot_change_native_pointer(staged,tmp_path,monkeypatch,fault):
    v=staged;r=replacement(v,tmp_path);before,profile=retained(v),v.profile.read()
    no_transport(monkeypatch)
    if fault=='alias':
        with pytest.raises(AuthorityError,match='^FOLDER_ENDPOINT_ATTACHMENT_ALIAS$'):
            StagedFolderEndpoint(v.s.candidate,NativeFolderEndpoint(v.profile,v.model.installation_id))
    else:
        setattr(r.port,fault,object())
        with pytest.raises(AuthorityError,match='^STAGED_FOLDER_ENDPOINT_CHANGED$'):
            r.port.select(r.reference,expected_selection=r.expected,owner_authorized=True)
    assert v.profile.read()==profile and retained(v)==before
