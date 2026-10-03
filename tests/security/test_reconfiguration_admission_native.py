"""Actual OS admission-reservation cuts and protected identity/protection."""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import pytest

from tb4.configuration_contract import ConfigurationError
from tb4.private_settings import native_settings, SettingsError
from tb4.reconfiguration_admission import ConfigurationAdmission
from reconfiguration_admission_support import admission_for
from test_reconfiguration_promotion_native import native_system as promotion_native_system
from test_private_settings_native import fixture, protect_fixture


def native_system(root,store):
    s,pcontext,promotion,checker=promotion_native_system(root,store)
    promotion.begin(checker,owner_authorized=True)
    assert promotion.advance(checker,owner_authorized=True)=="PROFILE_PROMOTED"
    context,admission=admission_for(s.value,checker)
    return s,context,admission,checker


@pytest.mark.parametrize("source_changed",[False,True])
def test_actual_native_release_pending_recovers_only_current_exact_frame_without_remote_repeat(fixture,source_changed):
    root,store=fixture;s,context,admission,checker=native_system(root,store)
    cp=context.checkpoint;before=cp.read();frame=cp.store.read();profile=context.profile.read()
    writes=len(s.value.provider.store.calls);locked=cp.store.native.locked
    @contextmanager
    def cut():
        with locked() as port:
            promote=port.promote
            def stop():
                value=cp.store._decode(port.read("settings.pending"),port.binding).payload
                if value["checkpoint"]["maintenance"] is None:raise OSError("SYNTHETIC_ADMISSION_RELEASE_CUT")
                return promote()
            port.promote=stop;yield port
    cp.store.native.locked=cut
    with pytest.raises((SettingsError,ConfigurationError)):admission.release(owner_authorized=True)
    cp.store.native.locked=locked
    with locked() as port:pending=port.read("settings.pending")
    assert pending is not None
    with pytest.raises((SettingsError,ConfigurationError)):admission.revision()
    if source_changed:
        status=s.value.source.catalog["profiles"][0]["status"]
        s.value.source.catalog["profiles"][0]["status"]="REVOKED";s.value.source.save()
        with pytest.raises((SettingsError,ConfigurationError)):
            admission.recover_pending(owner_authorized=True)
        with locked() as port:assert port.read("settings.pending")==pending
        s.value.source.catalog["profiles"][0]["status"]=status;s.value.source.save()
    assert admission.recover_pending(owner_authorized=True)=="INSPECT_REQUIRED"
    with locked() as port:assert port.read("settings.json")==pending and port.read("settings.pending") is None
    fresh=ConfigurationAdmission(context)
    assert fresh.revision()==2 and fresh.release(owner_authorized=True)==2
    assert cp.read()==replace(before,maintenance=None)
    assert cp.store.read().revision==frame.revision+1 and cp.store.read().previous==frame.payload
    assert context.profile.read()==profile and len(s.value.provider.store.calls)==writes and len(s.moves)==3


def test_actual_native_admission_profile_copy_and_checkpoint_broad_permissions_refuse(fixture):
    root,store=fixture;s,context,admission,checker=native_system(root,store)
    frame=context.checkpoint.store.read();profile=context.profile.read();writes=len(s.value.provider.store.calls)
    foreign=root.parent/"foreign-admission-profile"
    copied=native_settings(foreign,create=True,owner_authorized=True)
    target=foreign/"settings.json"
    target.write_bytes((Path(context.profile.native.root)/"settings.json").read_bytes());protect_fixture(target)
    with pytest.raises((SettingsError,ConfigurationError)):
        ConfigurationAdmission(replace(context,profile=copied)).release(owner_authorized=True)
    cp_root=Path(context.checkpoint.store.native.root);protect_fixture(cp_root,broad=True)
    try:
        with pytest.raises((SettingsError,ConfigurationError)):admission.release(owner_authorized=True)
    finally:protect_fixture(cp_root)
    assert context.checkpoint.store.read()==frame and context.profile.read()==profile
    assert len(s.value.provider.store.calls)==writes
