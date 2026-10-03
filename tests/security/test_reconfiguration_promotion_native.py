"""Actual Windows/Linux native original/promotion pending cuts and protection."""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import pytest

from tb4.configuration_contract import ConfigurationError
from tb4.private_settings import native_settings,SettingsError
from tb4.reconfiguration_promotion import PromotionContext,ProfilePromotion
from test_reconfiguration_commit_native import native_system as commit_native_system
from test_private_settings_native import fixture,protect_fixture


def native_system(root,store):
    commit_store=native_settings(root.parent/"promotion-commit",create=True,owner_authorized=True)
    s,context,commit,checker=commit_native_system(root,commit_store)
    commit.begin(checker,owner_authorized=True,decided_at=220)
    assert commit.advance(checker,owner_authorized=True)=="PUBLISHED"
    pcontext=PromotionContext(commit,store)
    return s,pcontext,ProfilePromotion(pcontext),checker


@pytest.mark.parametrize("at",["begin","original","confirmed"])
def test_actual_native_profile_promotion_cut_recovers_exact_frame_without_remote_repeat(fixture,at):
    root,store=fixture;s,context,promotion,checker=native_system(root,store)
    if at!="begin":promotion.begin(checker,owner_authorized=True)
    original=s.value.setup.store.read();writes=len(s.value.provider.store.calls)
    selected=s.value.setup.store if at=="original" else store;locked=selected.native.locked
    @contextmanager
    def cut():
        with locked() as port:
            promote=port.promote
            def stop():
                value=selected._decode(port.read("settings.pending"),port.binding).payload
                if at=="original" or value["phase"]==("PREPARED" if at=="begin" else "PROMOTED"):
                    raise OSError("SYNTHETIC_PROFILE_PROMOTION_CUT")
                return promote()
            port.promote=stop;yield port
    selected.native.locked=cut
    with pytest.raises((SettingsError,ConfigurationError)):
        promotion.begin(checker,owner_authorized=True) if at=="begin" else promotion.advance(checker,owner_authorized=True)
    selected.native.locked=locked
    with locked() as port:pending=port.read("settings.pending")
    assert pending is not None
    if at=="original":assert promotion.recover_original(checker,owner_authorized=True)=="INSPECT_REQUIRED"
    else:assert promotion.recover_local(checker,owner_authorized=True)=="INSPECT_REQUIRED"
    with locked() as port:assert port.read("settings.json")==pending
    fresh=ProfilePromotion(context)
    assert fresh.inspect(checker)==("PREPARED" if at=="begin" else "PROFILE_PROMOTED")
    if at=="begin":assert s.value.setup.store.read()==original
    else:assert s.value.setup.store.read().previous==original.payload
    assert len(s.value.provider.store.calls)==writes and len(s.moves)==3


def test_actual_native_promotion_copy_and_original_broad_permissions_are_refused(fixture):
    root,store=fixture;s,context,promotion,checker=native_system(root,store)
    promotion.begin(checker,owner_authorized=True);original=s.value.setup.store.read();writes=len(s.value.provider.store.calls)
    foreign=root.parent/"foreign-profile-promotion";copied=native_settings(foreign,create=True,owner_authorized=True)
    target=foreign/"settings.json";target.write_bytes((root/"settings.json").read_bytes());protect_fixture(target)
    with pytest.raises((SettingsError,ConfigurationError)):
        ProfilePromotion(replace(context,store=copied)).advance(checker,owner_authorized=True)
    original_root=Path(s.value.setup.store.native.root)
    protect_fixture(original_root,broad=True)
    try:
        with pytest.raises((SettingsError,ConfigurationError)):promotion.advance(checker,owner_authorized=True)
    finally:protect_fixture(original_root)
    assert s.value.setup.store.read()==original and len(s.value.provider.store.calls)==writes
