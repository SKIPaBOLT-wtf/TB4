"""Actual OS current ACTIVE adoption cuts, pending bytes and native protection."""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import pytest

from tb4.configuration_contract import ConfigurationError
from tb4.private_settings import native_settings, SettingsError
from tb4.reconfiguration_active_adoption import ActiveAdoption, current_admission
from reconfiguration_active_adoption_support import system
from test_private_settings_native import fixture, protect_fixture


def native_system(root,store):
    stores={"transaction":store}
    for name in ("original","checkpoint","profile","archive","effects"):
        stores[name]=native_settings(root.parent/("active-adoption-"+name),create=True,owner_authorized=True)
    return system(stores=stores)


@pytest.mark.parametrize("at",["intent","archive","stage","staged","prepared","original","confirmed"])
def test_actual_native_adoption_cut_recovers_same_frame_and_never_writes_shared_authority(fixture,at):
    root,store=fixture;s=native_system(root,store)
    if at in {"prepared","original","confirmed"}:s.adoption.begin(owner_authorized=True)
    if at in {"original","confirmed"}:s.adoption.prepare(owner_authorized=True,decided_at=s.local.clock().utc)
    selected={"archive":s.context.archive,"stage":s.context.profile,"original":s.local.profile}.get(at,store)
    locked=selected.native.locked
    @contextmanager
    def cut():
        with locked() as port:
            promote=port.promote
            def stop():
                value=selected._decode(port.read("settings.pending"),port.binding).payload
                if at in {"archive","stage","original"} or value["phase"]=={
                    "intent":"STAGING","staged":"STAGED","prepared":"PREPARED","confirmed":"PROMOTED"}[at]:
                    raise OSError("SYNTHETIC_ACTIVE_ADOPTION_CUT")
                return promote()
            port.promote=stop;yield port
    selected.native.locked=cut
    writes=len(s.value.provider.store.calls)
    with pytest.raises((SettingsError,ConfigurationError)):
        if at in {"intent","archive","stage","staged"}:s.adoption.begin(owner_authorized=True)
        elif at=="prepared":s.adoption.prepare(owner_authorized=True,decided_at=s.local.clock().utc)
        else:s.adoption.advance(owner_authorized=True)
    selected.native.locked=locked
    with locked() as port:pending=port.read("settings.pending")
    assert pending is not None
    which={"archive":"archive","stage":"profile","original":"original"}.get(at,"transaction")
    # An obsolete source cannot qualify the same pending frame.
    status=s.value.source.catalog["profiles"][0]["status"]
    s.value.source.catalog["profiles"][0]["status"]="REVOKED";s.value.source.save()
    with pytest.raises((SettingsError,ConfigurationError)):s.adoption.recover_local(which,owner_authorized=True)
    with locked() as port:assert port.read("settings.pending")==pending
    s.value.source.catalog["profiles"][0]["status"]=status;s.value.source.save()
    assert s.adoption.recover_local(which,owner_authorized=True)=="INSPECT_REQUIRED"
    with locked() as port:assert port.read("settings.json")==pending and port.read("settings.pending") is None
    fresh=ActiveAdoption(s.context);phase=fresh.view()["phase"]
    if phase=="STAGING":fresh.resume_staging(owner_authorized=True);phase=fresh.view()["phase"]
    if phase=="STAGED":fresh.prepare(owner_authorized=True,decided_at=s.local.clock().utc)
    assert fresh.advance(owner_authorized=True)=="PROFILE_PROMOTED"
    assert current_admission(s.local).release(owner_authorized=True)==2
    assert s.local.profile.read().previous==s.before.payload
    assert len(s.value.provider.store.calls)==writes


def test_actual_native_adoption_copied_transaction_and_broad_main_permissions_refuse(fixture):
    root,store=fixture;s=native_system(root,store);s.adoption.begin(owner_authorized=True)
    s.adoption.prepare(owner_authorized=True,decided_at=s.local.clock().utc)
    before=s.local.profile.read();writes=len(s.value.provider.store.calls)
    foreign=root.parent/"foreign-active-adoption";copied=native_settings(foreign,create=True,owner_authorized=True)
    target=foreign/"settings.json";target.write_bytes((root/"settings.json").read_bytes());protect_fixture(target)
    with pytest.raises((SettingsError,ConfigurationError)):
        ActiveAdoption(replace(s.context,transaction=copied)).advance(owner_authorized=True)
    main_root=Path(s.local.profile.native.root);protect_fixture(main_root,broad=True)
    try:
        with pytest.raises((SettingsError,ConfigurationError)):s.adoption.advance(owner_authorized=True)
    finally:protect_fixture(main_root)
    assert s.local.profile.read()==before and len(s.value.provider.store.calls)==writes
