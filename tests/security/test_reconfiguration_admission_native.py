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


@pytest.mark.parametrize("boundary",["release","revision","late-first-run","pending"])
def test_actual_native_stale_timing_preserves_profile_and_exact_checkpoint_frames(fixture,boundary):
    root,store=fixture;s,context,admission,checker=native_system(root,store)
    cp=context.checkpoint;original=context.leadership.profile
    stale=replace(original,control_s=7,lease_stale_s=180)
    if boundary=="revision":admission.release(owner_authorized=True)
    if boundary=="pending":
        locked=cp.store.native.locked
        @contextmanager
        def cut():
            with locked() as port:
                promote=port.promote
                def stop():
                    value=cp.store._decode(port.read("settings.pending"),port.binding).payload
                    if value["checkpoint"]["maintenance"] is None:raise OSError("SYNTHETIC_TIMING_RELEASE_CUT")
                    promote()
                port.promote=stop;yield port
        cp.store.native.locked=cut
        try:
            with pytest.raises((SettingsError,ConfigurationError)):admission.release(owner_authorized=True)
        finally:cp.store.native.locked=locked
    with cp.store.native.locked() as port:
        before=port.read("settings.json");pending=port.read("settings.pending")
    assert (pending is not None)==(boundary=="pending")
    profile=context.profile.read();writes=len(s.value.provider.store.calls)
    environment=checker.environment
    if boundary=="late-first-run":
        def late():
            context.leadership.profile=stale
            return environment()
        checker.environment=late
    else:context.leadership.profile=stale
    rejected=[];current=admission._current
    def observed(*args,**kwargs):
        try:return current(*args,**kwargs)
        except ConfigurationError as error:
            rejected.append(str(error));raise
    admission._current=observed
    # Native locks redact inner errors; still prove the actual timing refusal.
    with pytest.raises((ConfigurationError,SettingsError),match="^(ADMISSION_TIMING|SETTINGS_STORE_UNAVAILABLE)$"):
        if boundary=="pending":admission.recover_pending(owner_authorized=True)
        elif boundary=="revision":admission.revision()
        else:admission.release(owner_authorized=True)
    assert rejected==["ADMISSION_TIMING"]
    admission._current=current
    with cp.store.native.locked() as port:
        assert port.read("settings.json")==before and port.read("settings.pending")==pending
    assert context.profile.read()==profile and len(s.value.provider.store.calls)==writes
    checker.environment=environment;context.leadership.profile=original
    if boundary=="pending":assert admission.recover_pending(owner_authorized=True)=="INSPECT_REQUIRED"
    assert admission.release(owner_authorized=True)==2
