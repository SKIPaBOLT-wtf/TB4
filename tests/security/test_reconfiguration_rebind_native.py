"""Actual native private rebind frames/cuts; synthetic conditional SDK only."""
from contextlib import contextmanager
from dataclasses import replace
import copy

import pytest

from tb4.commissioning_checks import detect_environment
from tb4.configuration_contract import ConfigurationError
from tb4.drive.commissioning import frozen_plan
from tb4.private_settings import native_settings,SettingsError
from tb4.reconfiguration_rebind import RemoteRebind
from reconfiguration_rebind_support import system
from test_reconfiguration_rebind import large_plan
from test_private_settings_native import fixture,protect_fixture


def native_system(root,store):
    def private(name):return native_settings(root.parent/name,create=True,owner_authorized=True)
    return system(rebind_store=store,root_store=private("physical"),profile=private("candidate"),archive=private("archive"),
        transaction=private("candidate-meta"),profile_store=private("original"),checkpoint_store=private("checkpoint"),
        effect_store=private("effects"),state_store=private("maintenance"),baseline_store=private("baseline"),
        environment=lambda:detect_environment(launch_mode="EXTERNAL"))


@pytest.mark.parametrize("at",["begin","invoking","confirmed"])
def test_actual_native_pending_rebind_cut_recovers_exact_frame_without_conditional_repeat(fixture,at):
    root,store=fixture;s=native_system(root,store);locked=store.native.locked
    if at!="begin":s.rebind.begin(owner_authorized=True)
    original=s.value.setup.store.read();writes=len(s.value.provider.store.calls)
    @contextmanager
    def cut():
        with locked() as port:
            promote=port.promote
            def stop():
                value=store._decode(port.read("settings.pending"),port.binding).payload
                if value["dispatch"]=={"begin":"PREPARED","invoking":"INVOKING","confirmed":"CONFIRMED"}[at]:
                    raise OSError("SYNTHETIC_REBIND_PROMOTION_CUT")
                return promote()
            port.promote=stop;yield port
    store.native.locked=cut
    with pytest.raises((SettingsError,ConfigurationError)):
        s.rebind.begin(owner_authorized=True) if at=="begin" else s.rebind.advance(owner_authorized=True)
    store.native.locked=locked;pending=(root/"settings.pending").read_bytes()
    with pytest.raises(SettingsError):store.read()
    assert s.rebind.recover_local(owner_authorized=True)=="INSPECT_REQUIRED"
    assert (root/"settings.json").read_bytes()==pending
    fresh=RemoteRebind(s.context)
    assert fresh.inspect()=={"begin":"PREPARED","invoking":"UNKNOWN","confirmed":"REBOUND"}[at]
    assert len(s.value.provider.store.calls)==writes+(1 if at=="confirmed" else 0)
    assert s.value.setup.store.read()==original and len(s.moves)==3


def test_actual_native_copy_and_broad_permissions_are_refused(fixture):
    root,store=fixture;s=native_system(root,store);s.rebind.begin(owner_authorized=True)
    original=s.value.setup.store.read();writes=len(s.value.provider.store.calls)
    foreign=root.parent/"foreign-rebind";copy_store=native_settings(foreign,create=True,owner_authorized=True)
    target=foreign/"settings.json";target.write_bytes((root/"settings.json").read_bytes());protect_fixture(target)
    with pytest.raises((SettingsError,ConfigurationError)):
        RemoteRebind(replace(s.context,store=copy_store)).advance(owner_authorized=True)
    protect_fixture(root,broad=True)
    try:
        with pytest.raises((SettingsError,ConfigurationError)):s.rebind.advance(owner_authorized=True)
    finally:protect_fixture(root)
    assert len(s.value.provider.store.calls)==writes and s.value.setup.store.read()==original


def test_actual_native_max129_reference_pending_and_previous_frame_budget(fixture):
    root,store=fixture;s=native_system(root,store);s.rebind.begin(owner_authorized=True)
    plan,_=large_plan();current=store.read();frame=copy.deepcopy(current.payload)
    frame.update(transition_id=plan._validate()[2]["configuration"]["transition_id"],plan=frozen_plan(plan))
    # Frame/protection budget only: this saved synthetic plan is never an
    # admission or a dispatch. Its private profile is intentionally different.
    store.save(frame,expected_revision=current.revision)
    invoking={**frame,"dispatch":"INVOKING"}
    store.save(invoking,expected_revision=current.revision+1)
    assert store.read().payload==invoking and store.read().previous==frame
    assert (root/"settings.json").stat().st_size<=1024*1024 and not (root/"settings.pending").exists()
    writes=len(s.value.provider.store.calls)
    with pytest.raises((SettingsError,ConfigurationError,ValueError)):
        s.rebind.advance(owner_authorized=True)
    assert len(s.value.provider.store.calls)==writes
