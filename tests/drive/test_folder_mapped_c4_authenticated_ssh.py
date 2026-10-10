"""Actual mapped native C4, Main promotion and restart through fixed SSH."""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import sys
import pytest

from tb4.commissioning_state import Setup, DenyActivation
from tb4.configuration_contract import ConfigurationError
from tb4.credential_persistence import restore_private
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority import FolderStore
from tb4.drive.folder_authority_transport import credential_authority_pair
from tb4.drive.folder_mapping_active_probe import FolderMappingActiveProbe
from tb4.drive.folder_mapping_after_probe import FolderMappingAfterProbe
from tb4.drive.leadership import Leadership
from tb4.linux_key_native import LinuxKeyNative
from tb4.private_settings import SettingsError
from tb4.reconfiguration_effects import Effects, SLOT, ledger
from tb4.reconfiguration_folder_runtime import native_folder_admission
from tb4.reconfiguration_retained import RetainedConfigurationCommit, work_sha
from tb4.reconfiguration_retained_promotion import RetainedProfilePromotion
from tb4.watchdog.leadership_runtime import Work, Action, NativeWatchdogContext, NativeWatchdogRuntime
from test_folder_candidate_authenticated_ssh import staged, retained, TARGET, TRUST, SCOPES
from test_folder_commissioning import context
from test_folder_retained_authenticated_ssh import native
from test_folder_staged_endpoint_authenticated_ssh import replacement
from test_folder_ssh import Server
from test_native_leadership import ACTORS, clock, tid

pytestmark = pytest.mark.skipif(sys.platform != 'linux',
    reason='Actual mapped native C4 and current Main over fixed SSH')


def mapped(v):
    a = native(v)
    a.commit = RetainedConfigurationCommit(replace(a.commit.context, native_mapping_after=True))
    a.promotion = RetainedProfilePromotion(replace(a.promotion.context, commit=a.commit))
    return a


def publish(a):
    before = a.ctx.setup.store.read()
    plan = ledger(a.ctx.leadership.backend.read().document()['records'][SLOT])['folder_plan']
    assert a.controller.refresh()['settings_validated']
    assert a.commit.begin(a.checker, owner_authorized=True, decided_at=220) == 'PREPARED'
    assert a.commit.advance(a.checker, owner_authorized=True) == 'PUBLISHED'
    assert a.ctx.setup.store.read() == before
    return plan


def current_admission(a):
    return native_folder_admission(a.ctx.setup.store, a.ctx.checkpoint, access=a.v.access,
        environment=a.environment, credential_clock=lambda:a.v.now[0], clock=a.ctx.clock,
        capabilities=a.ctx.capabilities, source=a.ctx.source, runtime=a.ctx.runtime,
        enrollment=a.ctx.leadership.enrollment)


def second_endpoint(v, tmp_path):
    directory = tmp_path/'mapped-c4-second-server';directory.mkdir(mode=0o700)
    server = Server(directory, v.server.root/'helper.json', v.server.sshd, v.server.ssh,
                    dispatch=True, mapping_store=v.mapping)
    try:
        known = directory/'known';known.chmod(0o600)
        native = LinuxKeyNative()
        with native.open_key(str(known), native.identity().uid) as held:version = held.version
        endpoint = replace(v.endpoint, port=server.port, known_hosts=str(known), known_version=version)
        store, resolver = credential_authority_pair(v.model.installation_id, endpoint,
            v.port.binding, clock=lambda:v.now[0])
        restore_private(v.profile.read().payload['credential_image'], store, resolver)
        ref = store.select(path=str(directory/'client-a'), target_id=TARGET, target_trust=TRUST,
            purposes=SCOPES, expires_at=1000, access_mode='existing_key', launch_mode='headless',
            owner_authorized=True)
        handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator=ref,
            purposes=SCOPES, expires_at=1000, owner_authorized=True)
        v.s.candidate.persist_credentials(store, resolver, [dict(handle=handle, target_id=TARGET,
            target_trust=TRUST, purposes=sorted(p.value for p in SCOPES))], owner_authorized=True)
        v.handle = handle
        r = replacement(v, tmp_path, endpoint=endpoint)
        r.port.select(r.reference, expected_selection=r.expected, owner_authorized=True)
        v.server.stop()
        return server
    except BaseException:
        server.stop()
        raise


@pytest.mark.parametrize('switch,outcome', [(False,'COMPLETE'), (True,'UNKNOWN')])
def test_actual_mapped_c4_staged_endpoint_main_promotion_and_restart_preserve_work(
        staged, tmp_path, monkeypatch, capsys, switch, outcome):
    v = staged;server = second_endpoint(v, tmp_path) if switch else None
    try:
        a = mapped(v);before = retained(v);shared = a.ctx.leadership.backend.read().document()
        folder = publish(a)
        probe = FolderMappingActiveProbe(a.checker.storage.port._connection.probe(v.access))
        proof = probe.verify(folder)
        assert proof.document() == a.ctx.leadership.backend.read().document()
        with pytest.raises(AuthorityError, match='^MAPPING_AFTER_UNAVAILABLE$'):
            FolderMappingAfterProbe(a.checker.storage.port._connection.probe(v.access)).verify(folder)
        assert a.promotion.begin(a.checker, owner_authorized=True) == 'PREPARED'
        assert a.promotion.advance(a.checker, owner_authorized=True) == 'PROFILE_PROMOTED'
        main = a.ctx.setup.store;frame = main.read()
        assert frame.previous == before[0].payload and v.s.candidate.context.archive.read() == before[1]
        assert frame.payload['installation_id'] == before[0].payload['installation_id']
        assert frame.payload['operations'] == before[0].payload['operations']
        assert frame.payload['setup_nonce'] == before[0].payload['setup_nonce']
        assert frame.payload['folder_endpoint'] == v.profile.read().payload['folder_endpoint']
        assert frame.payload['credential_image'] == v.profile.read().payload['credential_image']
        assert retained(v)[4:] == before[4:]
        admission = current_admission(a)
        assert admission.release(owner_authorized=True) == 2
        # Ordinary restart uses only current Main, with fresh current admission.
        def absent(*_args, **_kwargs):raise OSError('SYNTHETIC_OWN_STAGING_UNAVAILABLE')
        for store in (v.profile, v.s.candidate.context.archive, v.s.candidate.context.transaction,
                      a.commit.context.store, a.promotion.context.store):
            monkeypatch.setattr(store, 'read', absent);monkeypatch.setattr(store, 'save', absent)
        admission = current_admission(a)
        effects = Effects(admission.context.leadership, a.ctx.checkpoint, a.ctx.effects.store)
        runner = NativeWatchdogRuntime(NativeWatchdogContext(admission.context.leadership,
            a.ctx.checkpoint, a.ctx.capabilities, a.ctx.clock, lambda:None,
            configuration_revision=admission.revision, effects=effects))
        assert runner.tick()
        calls = []
        work = Work(Action.SSH, tid('mapped-native-current-work'), lambda *_:calls.append(True) or outcome)
        assert runner.perform(work) == outcome and runner.perform(work) == outcome and calls == [True]
        assert work_sha(admission.context.leadership.backend.read().document()) == work_sha(shared)
        assert main.read() == frame and admission.revision() == 2
        assert Setup(main).activate(admission.context.checker, DenyActivation())['reason'] == 'ACTIVATION_NOT_AUTHORIZED'
        assert not admission.status()['runtime_active'] and capsys.readouterr() == ('','')
    finally:
        if server is not None:server.stop()


@pytest.mark.parametrize('fault', ['pending-mapping','pending-endpoint','key-permission','forced','artifact'])
def test_actual_mapped_promotion_needs_fresh_physical_mapping_and_role_after_publication(staged, fault):
    v = staged;a = mapped(v);publish(a)
    if fault in {'pending-mapping','pending-endpoint'}:
        store = v.port.mapping.store if fault == 'pending-mapping' else v.metadata
        with store.native.locked() as port:port.stage(port.read('settings.json'))
    if fault == 'key-permission':v.key.chmod(0o644)
    if fault == 'forced':
        other = Leadership(a.ctx.leadership.backend, actor=ACTORS[1], enrollment=a.ctx.leadership.enrollment)
        plan = other.request_force(other.observe(clock(220)), request_id=tid('mapped-native-late-force'), user_requested=True)
        assert other.commit(plan, mode='START').outcome == 'CONFIRMED'
    if fault == 'artifact':
        key = v.port.spec.artifact_keys[0]
        path = v.current.root/v.port.base.prepare(key, v.port.spec.operation(key)).object_id
        path.rename(v.current.root/'held-synthetic-artifact')
    main = a.ctx.setup.store.read();shared = FolderStore(v.current).read()
    with pytest.raises((AuthorityError, ConfigurationError, SettingsError)):
        a.promotion.begin(a.checker, owner_authorized=True)
    assert a.ctx.setup.store.read() == main and FolderStore(v.current).read() == shared
    assert a.promotion.context.store.read() is None and not a.promotion.view()['runtime_active']


@pytest.mark.parametrize('after', [False,True])
def test_actual_mapped_main_cut_recovers_exact_child_without_resave_or_shared_cas(staged, monkeypatch, after):
    v = staged;a = mapped(v);publish(a)
    assert a.promotion.begin(a.checker, owner_authorized=True) == 'PREPARED'
    main = a.ctx.setup.store;before = main.read();locked = main.native.locked
    @contextmanager
    def interrupted():
        with locked() as port:
            promote = port.promote
            def stop():
                if after:promote()
                raise OSError('SYNTHETIC_MAPPED_MAIN_PROMOTION_CUT')
            port.promote = stop
            yield port
    monkeypatch.setattr(main.native, 'locked', interrupted)
    with pytest.raises(SettingsError, match='^SETTINGS_STORE_UNAVAILABLE$'):
        a.promotion.advance(a.checker, owner_authorized=True)
    monkeypatch.setattr(main.native, 'locked', locked)
    with main.native.locked() as port:
        pending, raw = port.read('settings.pending'), port.read('settings.json')
    shared = FolderStore(v.current).read()
    def forbidden(*_args, **_kwargs):pytest.fail('Recovery resaved Main or sent shared CAS')
    monkeypatch.setattr(main, 'save', forbidden)
    monkeypatch.setattr(FolderStore, 'compare_replace', forbidden)
    assert a.promotion.recover_original(a.checker, owner_authorized=True) == ('NO_PENDING' if after else 'INSPECT_REQUIRED')
    with main.native.locked() as port:
        assert port.read('settings.pending') is None and port.read('settings.json') == (raw if after else pending)
    assert a.promotion.inspect(a.checker) == 'PROFILE_PROMOTED'
    assert main.read().previous == before.payload and main.read().payload['state'] == 'INCOMPLETE'
    assert FolderStore(v.current).read() == shared and not a.promotion.view()['runtime_active']

