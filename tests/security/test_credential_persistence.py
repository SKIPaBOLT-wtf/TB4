"""Protected metadata round trips never reselect a changed key or expose bytes."""
import copy
from dataclasses import replace
import json

import pytest

from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.credential_persistence import export_private, restore_private, validate_image
from tb4.linux_credentials import LinuxKeyStore
from tb4.private_settings import SettingsError
from test_linux_credentials import Native, Runner, INSTALLATION, TARGET, TRUST, PURPOSES


def pair(native=None, now=100):
    native = native or Native()
    runner = Runner(native)
    store = LinuxKeyStore(INSTALLATION, native=native, runner=runner, clock=lambda:now)
    resolver = CredentialResolver(INSTALLATION,store,clock=lambda:now)
    return native, runner, store, resolver


def selected():
    native, runner, store, resolver = pair()
    ref = store.select(path="/synthetic/private/key", target_id=TARGET, target_trust=TRUST,
        purposes=PURPOSES, expires_at=200, access_mode="existing_key",launch_mode="headless",
        owner_authorized=True)
    handle = resolver.enroll(target_id=TARGET,target_trust=TRUST,store_locator=ref,
        purposes=PURPOSES,expires_at=200,owner_authorized=True)
    return native,runner,store,resolver,ref,handle


def capability(resolver, handle):
    return resolver.capability(handle,purpose=Purpose.FETCHER_STATUS,target_id=TARGET,target_trust=TRUST)


def test_restart_keeps_handles_versions_and_refreshes_actual_session():
    native, _, store, resolver, ref, handle = selected()
    image = export_private(store,resolver)
    restored_native, runner, restored_store, restored = pair()
    restored_native.user = replace(native.user,session=native.user.session+1)
    restore_private(image,restored_store,restored)
    assert capability(restored,handle).outcome is Outcome.READY
    assert restored._bindings[handle].store_locator == ref
    assert restored_store._selections[ref].user == restored_native.user
    assert restored_store._selections[ref].version == image["selections"][ref]["version"]
    assert runner.calls == 0


@pytest.mark.parametrize("change,expected", [
    ("rotated",Outcome.REVOKED),("expired",Outcome.EXPIRED),("revoked-binding",Outcome.REVOKED),
    ("revoked-selection",Outcome.REVOKED),("missing",Outcome.ABSENT),("denied",Outcome.DENIED),
    ("trust",Outcome.DENIED),
])
def test_restore_preserves_unavailability_instead_of_renewing_authority(change,expected):
    native,_,store,resolver,ref,handle = selected()
    if change == "revoked-binding":
        resolver.revoke(handle,owner_authorized=True)
    if change == "revoked-selection":
        store.revoke_selection(ref,owner_authorized=True)
    image = export_private(store,resolver)
    new_native,runner,new_store,new_resolver = pair(now=300 if change=="expired" else 100)
    if change=="rotated":new_native.version=2
    if change=="missing":new_native.state=Outcome.ABSENT
    if change=="denied":new_native.state=Outcome.DENIED
    if change=="trust":runner.trusted=False
    restore_private(image,new_store,new_resolver)
    assert capability(new_resolver,handle).outcome is expected and runner.calls==0
    assert new_store._selections[ref].version==1


def test_foreign_principal_or_installation_cannot_restore():
    _,_,store,resolver,_,_ = selected()
    image = export_private(store,resolver)
    native,_,new_store,new_resolver = pair()
    native.user=replace(native.user,uid=native.user.uid+1)
    with pytest.raises(SettingsError,match="USER_MISMATCH"):
        restore_private(image,new_store,new_resolver)
    assert not new_store._selections and not new_resolver._bindings
    image["installation_id"]=TARGET
    with pytest.raises(SettingsError):
        restore_private(image,new_store,new_resolver)


@pytest.mark.parametrize("change", ["extra-secret", "unbound-handle", "extra-purpose", "expiry",
                                   "invalid-version", "duplicate-purpose", "untrusted-shape"])
def test_bad_metadata_is_atomic_and_never_partially_restored(change):
    _,_,store,resolver,ref,handle = selected()
    image = export_private(store,resolver)
    if change=="extra-secret":image["selections"][ref]["password"]="SYNTHETIC_CANARY"
    if change=="unbound-handle":image["bindings"][handle]["store_locator"]="lk_"+"f"*32
    if change=="extra-purpose":image["bindings"][handle]["purposes"]=["ARBITRARY_COMMAND"]
    if change=="expiry":image["bindings"][handle]["expires_at"]=201
    if change=="invalid-version":image["selections"][ref]["version"]=True
    if change=="duplicate-purpose":image["selections"][ref]["purposes"]=["FETCHER_START"]*2
    if change=="untrusted-shape":image["selections"]=[]
    _,_,new_store,new_resolver=pair()
    with pytest.raises(SettingsError) as error:
        restore_private(image,new_store,new_resolver)
    assert not new_store._selections and not new_resolver._bindings
    assert "CANARY" not in str(error.value)


def test_restoration_does_not_overwrite_a_live_resolver():
    _,_,store,resolver,ref,handle=selected()
    image=export_private(store,resolver)
    with pytest.raises(SettingsError,match="NOT_EMPTY"):
        restore_private(image,store,resolver)
    assert capability(resolver,handle).available


def test_private_image_is_not_a_report_and_never_contains_material(capsys):
    _,_,store,resolver,_,handle=selected()
    image=export_private(store,resolver)
    raw=json.dumps(image)
    assert "/synthetic/private/key" in raw  # deliberately protected configuration
    assert "synthetic-linux-key-never-public" not in raw
    public=json.dumps(capability(resolver,handle).report())
    assert "/synthetic/" not in public and handle not in public
    assert capsys.readouterr()==("","")
