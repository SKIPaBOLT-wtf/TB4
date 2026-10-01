"""First-run/credential composition with actual OS handles and private files."""
import copy
import os

import pytest

from tb4.commissioning_state import Setup
from tb4.commissioning_checks import native_credential_pair, restore_setup_credentials
from tb4.credential_contract import Outcome, Purpose
from tb4.private_settings import native_settings, SettingsError
from test_private_settings_native import fixture, protect_fixture
from test_credential_persistence_native import Runner, TARGET, TRUST, CANARY


def prepare(fixture):
    root, settings = fixture
    setup = Setup(settings,create=True)
    path = root.parent / "synthetic-setup-key"
    path.write_bytes(CANARY)
    protect_fixture(path)
    factory = lambda installation:native_credential_pair(installation,runner=Runner(),clock=lambda:100)
    store,resolver = factory(setup.installation_id)
    extra = dict(interactive_required=False) if os.name=="nt" else dict(
        access_mode="existing_key",launch_mode="headless")
    ref=store.select(path=str(path),target_id=TARGET,target_trust=TRUST,purposes=frozenset(Purpose),
                     expires_at=200,owner_authorized=True,**extra)
    handle=resolver.enroll(target_id=TARGET,target_trust=TRUST,store_locator=ref,
                          purposes=frozenset(Purpose),expires_at=200,owner_authorized=True)
    selected=[dict(handle=handle,target_id=TARGET,target_trust=TRUST,
                   purposes=[Purpose.FETCHER_STATUS.value])]
    return root,setup,path,factory,store,resolver,handle,selected


def capability(resolver, handle):
    return resolver.capability(handle,purpose=Purpose.FETCHER_STATUS,target_id=TARGET,target_trust=TRUST)


def test_actual_setup_atomic_image_and_handle_survive_restart(fixture):
    root,setup,path,factory,store,resolver,handle,selected=prepare(fixture)
    setup.persist_credentials(store,resolver,selected)
    restarted=Setup(native_settings(root))
    restored=restore_setup_credentials(restarted,factory)
    assert restarted.installation_id==setup.installation_id
    assert restarted.private_choices()["credentials"]==selected
    assert capability(restored,handle).outcome is Outcome.READY
    assert path.read_bytes()==CANARY and CANARY not in (root/"settings.json").read_bytes()


def test_actual_setup_changed_key_is_not_reselected_on_restart(fixture):
    root,setup,path,factory,store,resolver,handle,selected=prepare(fixture)
    setup.persist_credentials(store,resolver,selected)
    path.write_bytes(b"synthetic-replacement")
    restarted=Setup(native_settings(root))
    restored=restore_setup_credentials(restarted,factory)
    assert capability(restored,handle).outcome is Outcome.REVOKED
    assert restarted.private_choices()["credentials"]==selected


def test_actual_setup_revocation_cannot_be_rolled_back(fixture):
    root,setup,_,factory,store,resolver,handle,selected=prepare(fixture)
    setup.persist_credentials(store,resolver,selected)
    resolver.revoke(handle,owner_authorized=True)
    setup.persist_credentials(store,resolver,selected)
    with pytest.raises(SettingsError,match="ROLLBACK_UNSAFE"):
        setup.rollback_choices(stopped=True)
    restarted=Setup(native_settings(root))
    assert capability(restore_setup_credentials(restarted,factory),handle).outcome is Outcome.REVOKED


def test_foreign_or_mismatched_reference_image_never_changes_setup(fixture):
    root,setup,_,_,store,resolver,_,selected=prepare(fixture)
    before=(root/"settings.json").read_bytes()
    bad=copy.deepcopy(selected)
    bad[0]["target_trust"]="e"*64
    with pytest.raises(SettingsError):
        setup.persist_credentials(store,resolver,bad)
    assert (root/"settings.json").read_bytes()==before


def test_failed_atomic_save_does_not_expose_new_handle_as_saved_configuration(fixture):
    root,setup,_,_,store,resolver,_,selected=prepare(fixture)
    # A conflicting actual lock prevents both metadata and selected refs changing.
    before=(root/"settings.json").read_bytes()
    with setup.store.native.locked():
        with pytest.raises(SettingsError):
            setup.persist_credentials(store,resolver,selected)
    assert (root/"settings.json").read_bytes()==before
    assert Setup(native_settings(root)).private_choices()["credentials"]==[]


def test_revocation_is_durable_even_while_an_external_operation_is_unknown(fixture):
    from test_first_run import storage_record
    root,setup,_,factory,store,resolver,handle,selected=prepare(fixture)
    setup.choose(dict(role="fetcher", storage=storage_record(), network_scope=[]))
    setup.persist_credentials(store,resolver,selected)
    setup.perform_once("e"*64,lambda:None,owner_authorized=True)
    resolver.revoke(handle,owner_authorized=True)
    setup.persist_credentials(store,resolver,selected)
    restarted=Setup(native_settings(root))
    assert restarted.status()["reason"]=="UNKNOWN_OPERATION"
    assert capability(restore_setup_credentials(restarted,factory),handle).outcome is Outcome.REVOKED


def test_existing_reference_cannot_be_unrevoked_or_forgotten_by_new_image(fixture):
    from dataclasses import replace
    root,setup,_,factory,store,resolver,handle,selected=prepare(fixture)
    resolver.revoke(handle,owner_authorized=True)
    setup.persist_credentials(store,resolver,selected)
    before=(root/"settings.json").read_bytes()
    resolver._bindings[handle]=replace(resolver._bindings[handle],revoked=False)
    with pytest.raises(SettingsError,match="IMAGE_TRANSITION"):
        setup.persist_credentials(store,resolver,selected)
    empty_store,empty_resolver=factory(setup.installation_id)
    with pytest.raises(SettingsError,match="IMAGE_TRANSITION"):
        setup.persist_credentials(empty_store,empty_resolver,[])
    assert (root/"settings.json").read_bytes()==before
