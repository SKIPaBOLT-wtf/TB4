"""Actual Windows/Linux native retained commit and complete Main promotion cuts."""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from tb4.configuration_contract import ConfigurationError
from tb4.private_settings import SettingsError,native_settings
from tb4.reconfiguration_retained import RetainedConfigurationCommit
from tb4.reconfiguration_retained_promotion import RetainedProfilePromotion
from tests.drive.reconfiguration_retained_support import native_system,publish
from tests.security.test_private_settings_native import fixture,protect_fixture


@pytest.mark.parametrize("at",["begin","invoking","confirmed"])
def test_native_commit_cut_recovers_only_same_complete_frame_and_never_resends(fixture,at):
    root,store=fixture;s=native_system(root,store);locked=store.native.locked
    if at!="begin":s.commit.begin(s.checker,owner_authorized=True,decided_at=220)
    original=s.value.setup.store.read();writes=len(s.value.provider.store.calls)
    @contextmanager
    def cut():
        with locked() as port:
            promote=port.promote
            def stop():
                value=store._decode(port.read("settings.pending"),port.binding).payload
                if value["dispatch"]=={"begin":"PREPARED","invoking":"INVOKING","confirmed":"CONFIRMED"}[at]:
                    raise OSError("SYNTHETIC_RETAINED_COMMIT_CUT")
                return promote()
            port.promote=stop;yield port
    store.native.locked=cut
    with pytest.raises((SettingsError,ConfigurationError)):
        s.commit.begin(s.checker,owner_authorized=True,decided_at=220) if at=="begin" else s.commit.advance(
            s.checker,owner_authorized=True)
    store.native.locked=locked;pending=(Path(root)/"settings.pending").read_bytes()
    with pytest.raises(SettingsError):store.read()
    status=s.value.source.catalog["profiles"][0]["status"]
    s.value.source.catalog["profiles"][0]["status"]="REVOKED";s.value.source.save()
    with pytest.raises(ConfigurationError):s.commit.recover_local(owner_authorized=True)
    assert (Path(root)/"settings.pending").read_bytes()==pending
    s.value.source.catalog["profiles"][0]["status"]=status;s.value.source.save()
    assert s.commit.recover_local(owner_authorized=True)=="INSPECT_REQUIRED"
    assert (Path(root)/"settings.json").read_bytes()==pending
    fresh=RetainedConfigurationCommit(s.context)
    assert fresh.inspect()=={"begin":"PREPARED","invoking":"UNKNOWN","confirmed":"PUBLISHED"}[at]
    assert len(s.value.provider.store.calls)==writes+(1 if at=="confirmed" else 0)
    assert s.value.setup.store.read()==original


@pytest.mark.parametrize("at",["begin","original","confirmed"])
def test_native_full_profile_cut_preserves_previous_and_recovers_same_bytes_without_shared_mutation(fixture,at):
    root,store=fixture;s=native_system(root,store,promotion=True);publish(s)
    if at!="begin":s.promotion.begin(s.checker,owner_authorized=True)
    original=s.value.setup.store.read();writes=len(s.value.provider.store.calls)
    selected=s.value.setup.store if at=="original" else store;locked=selected.native.locked
    @contextmanager
    def cut():
        with locked() as port:
            promote=port.promote
            def stop():
                value=selected._decode(port.read("settings.pending"),port.binding).payload
                if at=="original" or value["phase"]==("PREPARED" if at=="begin" else "PROMOTED"):
                    raise OSError("SYNTHETIC_RETAINED_PROMOTION_CUT")
                return promote()
            port.promote=stop;yield port
    selected.native.locked=cut
    with pytest.raises((SettingsError,ConfigurationError)):
        s.promotion.begin(s.checker,owner_authorized=True) if at=="begin" else s.promotion.advance(s.checker,owner_authorized=True)
    selected.native.locked=locked
    with locked() as port:pending=port.read("settings.pending")
    assert pending is not None
    if at=="original":assert s.promotion.recover_original(s.checker,owner_authorized=True)=="INSPECT_REQUIRED"
    else:assert s.promotion.recover_local(s.checker,owner_authorized=True)=="INSPECT_REQUIRED"
    with locked() as port:assert port.read("settings.json")==pending
    fresh=RetainedProfilePromotion(s.promotion_context)
    assert fresh.inspect(s.checker)==("PREPARED" if at=="begin" else "PROFILE_PROMOTED")
    if at=="begin":assert s.value.setup.store.read()==original
    else:assert s.value.setup.store.read().previous==original.payload
    assert len(s.value.provider.store.calls)==writes


def test_copied_native_commit_and_original_broad_permissions_refuse(fixture):
    root,store=fixture;root=Path(root);s=native_system(root,store);s.commit.begin(s.checker,owner_authorized=True,decided_at=220)
    original=s.value.setup.store.read();writes=len(s.value.provider.store.calls)
    foreign=root.parent/"foreign-retained-commit";copied=native_settings(foreign,create=True,owner_authorized=True)
    target=foreign/"settings.json";target.write_bytes((root/"settings.json").read_bytes());protect_fixture(target)
    with pytest.raises((SettingsError,ConfigurationError)):
        RetainedConfigurationCommit(replace(s.context,store=copied)).advance(s.checker,owner_authorized=True)
    protect_fixture(root,broad=True)
    try:
        with pytest.raises((SettingsError,ConfigurationError)):s.commit.advance(s.checker,owner_authorized=True)
    finally:protect_fixture(root)
    assert len(s.value.provider.store.calls)==writes and s.value.setup.store.read()==original
