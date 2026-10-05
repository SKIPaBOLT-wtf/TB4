"""Actual native current-profile composition grants no role, key use or READY."""
from dataclasses import replace

import pytest

from tb4.commissioning_checks import detect_environment
from tb4.configuration_contract import ConfigurationError
from tb4.drive.folder_runtime import NativeFolderCommissioning
from tb4.private_settings import native_settings, SettingsError
from tb4.reconfiguration_folder_runtime import native_folder_admission
from tb4.timing_contract import TimingProfile
from tb4.watchdog.checkpoint_store import NativeCheckpoint
from tests.security.test_first_run import FACTS
from tests.security.test_folder_connection_native import commit, saved
from tests.security.test_folder_runtime_native import system
from tests.security.test_private_settings_native import fixture, SUPPORTED

pytestmark=pytest.mark.skipif(not SUPPORTED,reason='Actual Windows/Linux current native factory')


def admission(v,checkpoint):
    return native_folder_admission(v.settings,checkpoint,access=v.access,
        environment=lambda:detect_environment(launch_mode='EXTERNAL'),credential_clock=lambda:v.now[0],
        clock=lambda:None,capabilities=lambda:None,source=v.source,runtime=FACTS,
        enrollment={v.setup.installation_id:'synthetic-current-native-computer'})


def checkpoint(v):
    store=native_settings(v.root.parent/'factory-checkpoint',create=True,owner_authorized=True)
    return NativeCheckpoint(store,installation_id=v.setup.installation_id,
        binding=v.port.authority(v.authority).binding,create=True,owner_authorized=True)


def test_actual_current_profile_factory_has_no_key_proof_save_or_role_and_denies_missing_grant(fixture,monkeypatch,capsys):
    v=system(fixture,monkeypatch);cp=checkpoint(v);before,snapshot=saved(v),cp.read();calls=len(v.calls)
    def forbidden(*_args,**_kwargs):pytest.fail('Native factory opened a key, rewrote a profile or granted a role')
    monkeypatch.setattr(v.store._native.__class__,'open_key',forbidden)
    monkeypatch.setattr(v.settings.__class__,'_save_locked',forbidden)
    a=admission(v,cp)
    assert type(a.context.checker.storage.port) is NativeFolderCommissioning
    assert a.context.leadership.profile==TimingProfile.parse(v.settings.read().payload['choices']['timing'])
    with pytest.raises(ConfigurationError,match='^ADMISSION_LEADERSHIP_UNKNOWN$'):a.revision()
    assert not a.status()['runtime_active'] and saved(v)==before and cp.read()==snapshot and len(v.calls)==calls
    assert capsys.readouterr()==('', '')


def test_actual_factory_rebuilds_timing_from_current_protected_choices_without_grant(fixture,monkeypatch):
    v=system(fixture,monkeypatch);cp=checkpoint(v);first=admission(v,cp)
    changed=replace(first.context.leadership.profile,control_s=7,lease_stale_s=180)
    from dataclasses import asdict
    commit(v,lambda p:p['choices'].update(timing=asdict(changed)))
    before,calls=saved(v),len(v.calls)
    second=admission(v,cp)
    assert second.context.leadership.profile==changed and first.context.leadership.profile!=changed
    with pytest.raises(ConfigurationError,match='^ADMISSION_LEADERSHIP_UNKNOWN$'):second.revision()
    assert saved(v)==before and len(v.calls)==calls and cp.read().grant is None


@pytest.mark.parametrize('fault',['unselected','pending-endpoint'])
def test_actual_current_factory_refuses_lost_native_selection_before_transport_or_profile_write(fixture,monkeypatch,fault):
    v=system(fixture,monkeypatch);cp=checkpoint(v)
    if fault=='unselected':commit(v,lambda p:p['choices'].update(credentials=[]))
    else:
        with v.metadata.native.locked() as port:port.stage(port.read('settings.json'))
    profile,calls,snapshot=v.settings.read(),len(v.calls),cp.read()
    with pytest.raises(SettingsError):admission(v,cp)
    assert v.settings.read()==profile and len(v.calls)==calls and cp.read()==snapshot
