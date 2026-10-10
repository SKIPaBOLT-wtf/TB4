"""Actual native rootless retained C4 and controller over fixed loopback SSH."""
from dataclasses import replace
import sys
from types import SimpleNamespace

import pytest

from tb4.configuration_contract import ConfigurationError, configuration
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority import FolderStore
from tb4.drive.folder_prerequisites import native_folder_prerequisites
from tb4.drive.leadership import Leadership
from tb4.private_settings import SettingsError
from tb4.reconfiguration_candidate import Candidate
from tb4.reconfiguration_effects import Effects
from tb4.reconfiguration_folder_runtime import native_folder_candidate_controller, native_folder_admission
from tb4.reconfiguration_maintenance import Maintenance
from tb4.reconfiguration_retained import RetainedCommitContext, RetainedConfigurationCommit, work_sha
from tb4.reconfiguration_retained_promotion import RetainedPromotionContext, RetainedProfilePromotion
from tb4.commissioning_checks import detect_environment
from tb4.commissioning_state import storage_spec
from tb4.timing_contract import TimingProfile
from test_folder_candidate_authenticated_ssh import staged, retained
from test_folder_commissioning import context
from test_native_leadership import ACTORS, clock, tid

pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='Actual native rootless C4/controller over SSH')


def native(v):
    s=v.s; environment=lambda:detect_environment(launch_mode='EXTERNAL')
    checker=native_folder_prerequisites(v.profile,access=v.access,environment=environment,
        source=s.ctx.source,runtime=s.ctx.runtime,clock=lambda:v.now[0],normal_authority=True)
    _,handle=storage_spec(s.ctx.setup.private_choices()['storage'])
    leader=Leadership(checker.storage.port.authority(handle),actor=s.ctx.setup.installation_id,
        enrollment=s.ctx.leadership.enrollment,profile=TimingProfile.parse(s.ctx.setup.private_choices()['timing']))
    ctx=replace(s.ctx,storage_port=checker.storage.port,leadership=leader,
        effects=Effects(leader,s.ctx.checkpoint,s.ctx.effects.store))
    candidate=Candidate(replace(s.candidate.context,maintenance=Maintenance(ctx)))
    commit=RetainedConfigurationCommit(RetainedCommitContext(candidate,s.context.store))
    promotion=RetainedProfilePromotion(RetainedPromotionContext(commit,s.promotion_context.store))
    controller=native_folder_candidate_controller(candidate,access=v.access,environment=environment,
        clock=lambda:v.now[0])
    return SimpleNamespace(v=v,ctx=ctx,candidate=candidate,checker=checker,commit=commit,
        promotion=promotion,controller=controller,environment=environment)


@pytest.mark.parametrize('staged',[False],indirect=True)
def test_actual_native_rootless_c4_promotion_and_current_profile_factory_preserve_work(staged,capsys):
    v=staged;a=native(v);before=retained(v);profile=a.ctx.setup.store.read()
    shared=a.ctx.leadership.backend.read().document()
    assert a.controller.refresh()['settings_validated']
    assert a.commit.begin(a.checker,owner_authorized=True,decided_at=220)=='PREPARED'
    assert a.ctx.setup.store.read()==profile
    assert a.commit.advance(a.checker,owner_authorized=True)=='PUBLISHED'
    assert a.ctx.setup.store.read()==profile
    assert a.promotion.begin(a.checker,owner_authorized=True)=='PREPARED'
    assert a.promotion.advance(a.checker,owner_authorized=True)=='PROFILE_PROMOTED'
    main=a.ctx.setup.store
    assert main.read().previous==profile.payload and v.s.candidate.context.archive.read()==before[1]
    admission=native_folder_admission(main,a.ctx.checkpoint,access=v.access,environment=a.environment,
        credential_clock=lambda:v.now[0],clock=a.ctx.clock,capabilities=a.ctx.capabilities,
        source=a.ctx.source,runtime=a.ctx.runtime,enrollment=a.ctx.leadership.enrollment)
    assert admission.release(owner_authorized=True)==2 and admission.revision()==2
    assert configuration(admission.context.leadership.backend.read().document())['phase']=='ACTIVE'
    assert work_sha(admission.context.leadership.backend.read().document())==work_sha(shared)
    assert not admission.status()['runtime_active'] and capsys.readouterr()==('', '')


@pytest.mark.parametrize('operation',['refresh','activate'])
def test_actual_controller_factory_late_native_metadata_loss_clears_ephemeral_readiness(staged,operation):
    v=staged;a=native(v)
    assert a.controller.refresh()['settings_validated']
    before,profile=retained(v),v.profile.read()
    with v.metadata.native.locked() as port:port.stage(port.read('settings.json'))
    with pytest.raises((AuthorityError,ConfigurationError,SettingsError)):
        getattr(a.controller,operation)()
    assert not a.candidate.view()['settings_validated'] and not a.candidate.view()['runtime_active']
    # Pending endpoint evidence remains; original Main/work and current staged profile do not change.
    after=(v.s.ctx.setup.store.read(),v.s.candidate.context.archive.read())
    assert after==before[:2] and v.profile.read()==profile
    assert FolderStore(v.current).read()==before[3]
    with v.metadata.native.locked() as port:assert port.read('settings.pending') is not None


def test_actual_remote_native_port_cannot_replace_server_local_mapped_after_qualification(staged):
    v=staged;a=native(v);before=retained(v);main=a.ctx.setup.store.read()
    with pytest.raises(ConfigurationError,match='^RETAINED_FOLDER_AFTER_REQUIRED$'):
        a.commit.begin(a.checker,owner_authorized=True,decided_at=220)
    assert a.ctx.setup.store.read()==main and a.commit.context.store.read() is None
    assert retained(v)==before and not a.candidate.view()['runtime_active']


@pytest.mark.parametrize('staged',[False],indirect=True)
@pytest.mark.parametrize('fault',['owner','forced','revoked'])
def test_actual_native_retained_commit_refuses_late_role_capability_or_owner_loss(staged,fault):
    v=staged;a=native(v);owner=fault!='owner'
    if fault=='forced':
        other=Leadership(a.ctx.leadership.backend,actor=ACTORS[1],enrollment=a.ctx.leadership.enrollment)
        plan=other.request_force(other.observe(clock(220)),request_id=tid('native-retained-force'),user_requested=True)
        assert other.commit(plan,mode='START').outcome=='CONFIRMED'
    if fault=='revoked':
        current=v.profile.read();payload=current.payload
        payload['credential_image']['bindings'][v.handle]['revoked']=True
        v.profile.save(payload,expected_revision=current.revision)
    before=retained(v)
    with pytest.raises((AuthorityError,ConfigurationError,SettingsError)):
        a.commit.begin(a.checker,owner_authorized=owner,decided_at=220)
    assert retained(v)==before and a.commit.context.store.read() is None
    assert not a.candidate.view()['runtime_active']
