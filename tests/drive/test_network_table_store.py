"""Real transaction model over faultable synthetic native ports."""
import copy
from pathlib import Path

import pytest

from tb4.commissioning_state import Setup
from tb4.network_table import NetworkTableError
from tb4.network_table_store import LocalNetworkTable
from tb4.private_settings import PrivateSettings
from tests.network_table_support import MemoryFactory, make_setup, system, good_proposal, seed


def restart(table, factory):
    setup = Setup(PrivateSettings(table.setup.store.native))
    return LocalNetworkTable(setup,installation_root=table.installation_root,factory=factory)


def test_default_custom_location_and_restart_keep_the_exact_table(tmp_path):
    table,factory=system(tmp_path)
    before=table.read()
    source=table.local_location()
    assert source==str(table.installation_root/"network-table")
    destination=tmp_path/"custom-table"
    assert table.move(destination,owner_authorized=True)=="CONFIRMED"
    assert table.local_location()==str(destination)
    assert table.read()==before
    assert PrivateSettings(factory.natives[source]).read().payload==before
    assert restart(table,factory).read()==before
    assert len(factory.natives)==2 and table.setup._payload["network_table"]["pending"] is None


def test_custom_initial_location_never_creates_default(tmp_path):
    setup,factory=make_setup(),MemoryFactory()
    table=LocalNetworkTable(setup,installation_root=tmp_path,factory=factory)
    custom=tmp_path/"owner-selected"
    table.configure(custom,owner_authorized=True)
    assert table.local_location()==str(custom) and not (tmp_path/"network-table").exists()


@pytest.mark.parametrize("action",["configure","move","approve"])
def test_owner_permission_is_not_inferred_from_access(tmp_path,action):
    table,factory=system(tmp_path)
    old=copy.deepcopy(table.setup._payload)
    with pytest.raises(NetworkTableError,match="OWNER_APPROVAL"):
        if action=="configure":
            LocalNetworkTable(make_setup(),installation_root=tmp_path,factory=factory).configure()
        elif action=="move": table.move(tmp_path/"unapproved")
        else: table.approve(good_proposal(table),now=100)
    assert table.setup._payload==old


def test_stale_owner_proposal_and_competing_settings_writer_cannot_overwrite(tmp_path):
    table,factory=system(tmp_path)
    proposed=good_proposal(table)
    other=restart(table,factory)
    table.approve(proposed,now=100,owner_authorized=True)
    before=table.read()
    with pytest.raises(NetworkTableError,match="REVISION_CHANGED"):
        table.approve(proposed,now=101,owner_authorized=True)
    with pytest.raises(Exception,match="CHANGED_RELOAD"):
        other.approve(proposed,now=101,owner_authorized=True)
    assert table.read()==before


@pytest.mark.parametrize("failure",["stage","promote"])
def test_failed_update_recovers_the_same_complete_candidate_without_second_write(tmp_path,failure):
    table,factory=system(tmp_path)
    proposed=good_proposal(table)
    native=factory.natives[table.local_location()]
    native.failure=failure
    with pytest.raises(NetworkTableError):
        table.approve(proposed,now=100,owner_authorized=True)
    assert table.setup._payload["network_table"]["pending"]["kind"]=="UPDATE"
    exact=native.files["settings.pending"]
    native.failure=None
    recovered=restart(table,factory)
    assert recovered.inspect()=="CONFIRMED"
    assert native.files["settings.json"]==exact and "settings.pending" not in native.files
    assert recovered.read()["descriptions"][proposed["device_id"]]["approved_at"]==100
    revision=PrivateSettings(native).read().revision
    with pytest.raises(NetworkTableError,match="NO_PENDING"):
        recovered.inspect()
    assert PrivateSettings(native).read().revision==revision


def test_failed_target_readback_preserves_prior_root_then_inspects_same_written_table(tmp_path,monkeypatch):
    table,factory=system(tmp_path)
    source=table.local_location();before=table.read()
    original=factory.__call__
    destination=tmp_path/"destination"
    def fault(root,**options):
        store=original(root,**options)
        if options.get("create"):
            promote=store.native.promote
            def lost():
                promote();store.native.failure="readback"
            store.native.promote=lost
        return store
    table.factory=fault
    with pytest.raises(NetworkTableError):
        table.move(destination,owner_authorized=True)
    assert table.setup._payload["network_table"]["root"]==source
    assert table.setup._payload["network_table"]["pending"]["target_root"]==str(destination)
    assert PrivateSettings(factory.natives[source]).read().payload==before
    native=factory.natives[str(destination)];native.failure=None
    bytes_before=copy.deepcopy(native.files)
    recovered=restart(table,factory)
    assert recovered.inspect()=="CONFIRMED" and recovered.read()==before
    assert native.files==bytes_before


@pytest.mark.parametrize("foreign",["existing-folder","existing-table"])
def test_existing_destination_is_never_overwritten(tmp_path,foreign):
    table,factory=system(tmp_path)
    destination=tmp_path/"foreign"
    if foreign=="existing-folder":destination.mkdir()
    else:
        store=factory(destination,create=True,owner_authorized=True)
        store.save({"foreign":True},expected_revision=0)
    before=copy.deepcopy(table.setup._payload)
    with pytest.raises(NetworkTableError,match="DESTINATION_EXISTS"):
        table.move(destination,owner_authorized=True)
    assert table.setup._payload==before


def test_target_creation_race_leaves_pending_and_does_not_adopt_empty_foreign_folder(tmp_path,monkeypatch):
    table,factory=system(tmp_path)
    destination=tmp_path/"competing-folder"
    original=table._save_selection
    def race(selected):
        original(selected)
        if selected["pending"] is not None:
            destination.mkdir()
    monkeypatch.setattr(table,"_save_selection",race)
    with pytest.raises(NetworkTableError):
        table.move(destination,owner_authorized=True)
    assert str(destination) not in factory.natives
    assert table.setup._payload["network_table"]["pending"] is not None
    assert destination.exists()


def test_changed_source_after_move_intent_is_not_replaced_or_falsely_confirmed(tmp_path,monkeypatch):
    table,factory=system(tmp_path)
    destination=tmp_path/"changed-source-destination"
    original=table._save_selection
    source=factory.natives[table.local_location()]
    def race(selected):
        if selected["pending"] is not None and selected["pending"]["kind"]=="MOVE":
            current=PrivateSettings(source).read()
            changed={**current.payload,"revision":current.payload["revision"]+1}
            PrivateSettings(source).save(changed,expected_revision=current.revision)
        original(selected)
    monkeypatch.setattr(table,"_save_selection",race)
    with pytest.raises(NetworkTableError,match="SOURCE_CHANGED"):
        table.move(destination,owner_authorized=True)
    assert not destination.exists() and table.setup._payload["network_table"]["pending"] is not None


def test_observations_recheck_current_owner_at_the_actual_native_write(tmp_path):
    table,factory=system(tmp_path)
    value=table.read()
    from tb4.discovery_catalogue import Catalogue,Interface,Observation,Scope
    catalogue=Catalogue(value["catalogue"])
    scope=Scope((Interface("synthetic-interface",7,("192.0.2.0/24",),"LAN"),))
    catalogue.observe((Observation(7,"192.0.2.9","NEIGHBOR_CACHE",101,60,
                                   hardware_hint="synthetic-hint"),),scope,now=101)
    calls=[]
    def owner():
        calls.append(1)
        return len(calls)==1
    with pytest.raises(NetworkTableError,match="OWNER_SUPERSEDED"):
        table.sync_observations(catalogue.private_image(),current_owner=owner)
    native=factory.natives[table.local_location()]
    assert PrivateSettings(native).read().payload==value
    assert table.setup._payload["network_table"]["pending"]["requires_owner"]
    with pytest.raises(NetworkTableError,match="OWNER_SUPERSEDED"):
        table.resume(owner_authorized=True)
    assert table.resume(owner_authorized=True,current_owner=lambda:True)=="CONFIRMED"


def test_wrong_native_directory_binding_is_refused_without_altering_data(tmp_path):
    table,factory=system(tmp_path)
    native=factory.natives[table.local_location()]
    before=copy.deepcopy(native.files)
    native.binding={"principal":"synthetic-owner","directory":[99,99]}
    with pytest.raises(NetworkTableError,match="LOCATION_CHANGED"):
        table.read()
    assert native.files==before


def test_unknown_setup_operations_preserve_all_private_payloads(tmp_path):
    table,factory=system(tmp_path)
    table.setup._save({**table.setup._payload,"operations":{"c"*64:"UNKNOWN"}})
    before=copy.deepcopy(table.setup._payload)
    with pytest.raises(NetworkTableError,match="SETUP_INSPECT"):
        table.move(tmp_path/"not-created",owner_authorized=True)
    assert table.setup._payload==before and not (tmp_path/"not-created").exists()

