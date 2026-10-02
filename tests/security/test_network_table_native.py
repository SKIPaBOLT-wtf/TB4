"""Native isolated table locations on each actual supported host, never home data."""
import copy
import os
from pathlib import Path
import sys
from threading import Thread

import pytest

from tb4.commissioning_state import Setup
from tb4.network_table import AddressingObservation, NetworkTableError, endpoint_digest
from tb4.network_table_store import LocalNetworkTable
from tb4.private_settings import SettingsError, native_settings
from tests.network_table_support import make_setup,seed,good_proposal
from test_private_settings_native import protect_fixture

pytestmark=pytest.mark.skipif(sys.platform not in {"win32","linux"},reason="qualified native Windows/Linux")


@pytest.fixture
def native_table(tmp_path):
    parent=tmp_path/"native-private-network"
    parent.mkdir(mode=0o700);protect_fixture(parent)
    installation=parent/"installation"
    installation.mkdir(mode=0o700);protect_fixture(installation)
    store=native_settings(parent/"setup",create=True,owner_authorized=True)
    setup=make_setup(store)
    table=LocalNetworkTable(setup,installation_root=installation)
    table.configure(owner_authorized=True)
    seed(table)
    return table,parent


def test_native_default_restart_approval_custom_move_and_prior_data(native_table,capsys):
    table,parent=native_table
    proposed=good_proposal(table)
    table.approve(proposed,now=100,owner_authorized=True)
    previous=Path(table.local_location())
    original=table.read()
    private_before=(previous/"settings.json").read_bytes()
    assert table.move(parent/"custom-location",owner_authorized=True)=="CONFIRMED"
    restarted=LocalNetworkTable(Setup(native_settings(Path(table.setup.store.native.root))))
    assert restarted.read()==original
    assert (previous/"settings.json").read_bytes()==private_before
    assert set(p.name for p in Path(table.local_location()).iterdir())=={"settings.json","settings.lock"}
    assert capsys.readouterr()==("","")


def test_native_insecure_destination_cannot_be_adopted_or_repaired(native_table):
    table,parent=native_table
    destination=parent/"existing-insecure"
    destination.mkdir();protect_fixture(destination,broad=True)
    before=table.read()
    with pytest.raises(NetworkTableError):
        table.move(destination,owner_authorized=True)
    assert table.read()==before
    assert not (destination/"settings.json").exists()


def test_native_table_permission_loss_is_closed_and_not_repaired(native_table,capsys):
    table,parent=native_table
    target=Path(table.local_location())/"settings.json"
    before=target.read_bytes()
    protect_fixture(target,broad=True)
    with pytest.raises(NetworkTableError):
        table.read()
    assert target.read_bytes()==before and capsys.readouterr()==("","")
    # Fixture restoration only, never production permission repair.
    protect_fixture(target)


def test_native_table_lock_blocks_competing_writer_without_losing_revision(native_table):
    table,parent=native_table
    native=native_settings(Path(table.local_location())).native
    before=table.read()
    proposed=good_proposal(table)
    with native.locked():
        with pytest.raises(NetworkTableError):
            table.approve(proposed,now=100,owner_authorized=True)
    assert table.read()==before


def test_native_existing_location_identity_swap_is_refused(native_table):
    table,parent=native_table
    old=Path(table.local_location())
    moved=old.with_name("original-preserved")
    old.rename(moved)
    native_settings(old,create=True,owner_authorized=True)
    with pytest.raises(NetworkTableError):
        table.read()
    assert (moved/"settings.json").exists()


def test_actual_discovery_owner_callback_updates_native_table_without_lock_reentry(tmp_path,capsys,monkeypatch):
    # Native-only job selections still load the existing synthetic service support.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/"drive"))
    from test_discovery_workflow import build,observation
    parent=tmp_path/"native-discovery-network"
    parent.mkdir(mode=0o700);protect_fixture(parent)
    installation=parent/"installation"
    installation.mkdir(mode=0o700);protect_fixture(installation)
    store=native_settings(parent/"setup",create=True,owner_authorized=True)
    flow,setup,provider,_,_=build(store=store)
    table=LocalNetworkTable(setup,installation_root=installation)
    assert table.configure(owner_authorized=True)=="CONFIRMED"
    remote_before=copy.deepcopy(provider.store.document)
    created_before=copy.deepcopy(provider.created)
    assert flow.observe((observation(),))==("OBSERVED",)
    assert table.read()["catalogue"]==setup._payload["discovery"]["image"]
    assert setup._payload["network_table"]["pending"] is None
    status=flow.status()["descriptions"]
    assert status["needs_description"]==1 and status["problem"] is None
    assert status["devices"][0]["stable_ip"]["value"]=="UNKNOWN"
    assert table.approve(good_proposal(table),now=220,owner_authorized=True)=="CONFIRMED"
    assert provider.store.document==remote_before and provider.created==created_before
    assert all(name=="files.get" for name,_ in provider.calls)
    assert capsys.readouterr()==("","")


def test_native_owner_read_scope_refuses_writes_and_expired_port(native_table,capsys):
    table,_=native_table
    setup=table.setup
    original=setup.store.native
    escaped=[]
    blocked=[]
    def current_owner():
        setup._fresh()
        if setup.store.native is not original:
            snapshot=setup.store.read()
            with setup.store.native.locked() as port:
                escaped.append(port)
                before=port.read("settings.json")
                with pytest.raises(SettingsError,match="^SETTINGS_READ_ONLY$"):
                    setup.store.save(snapshot.payload,expected_revision=snapshot.revision)
                with pytest.raises(SettingsError,match="^SETTINGS_READ_ONLY$"):
                    port.stage(b"synthetic-not-a-frame")
                with pytest.raises(SettingsError,match="^SETTINGS_READ_ONLY$"):
                    port.promote()
                assert port.read("settings.json")==before and port.read("settings.pending") is None
                blocked.append(True)
        return True
    entry=next(e for e in table.read()["catalogue"]["entries"] if e is not None)
    fact=AddressingObservation(entry["device_id"],endpoint_digest(entry),"ASSIGNED",100,60)
    assert table.record_addressing(fact,current_owner=current_owner)=="CONFIRMED"
    assert blocked and escaped and setup.store.native is original
    for port in escaped:
        with pytest.raises(SettingsError,match="^SETTINGS_READ_CONTEXT_EXPIRED$"):
            port.read("settings.json")
        with pytest.raises(SettingsError,match="^SETTINGS_READ_CONTEXT_EXPIRED$"):
            _=port.binding
    assert setup._payload["network_table"]["pending"] is None
    assert capsys.readouterr()==("","")


def test_other_thread_cannot_borrow_native_owner_read_scope(native_table):
    table,_=native_table
    setup=table.setup
    original=setup.store.native
    results=[]
    def competing_read():
        try:
            setup.store.read()
            results.append("UNEXPECTED_READ")
        except SettingsError as error:
            results.append(str(error))
    def current_owner():
        setup._fresh()
        if setup.store.native is not original:
            thread=Thread(target=competing_read)
            thread.start();thread.join(timeout=5)
            assert not thread.is_alive()
        return True
    entry=next(e for e in table.read()["catalogue"]["entries"] if e is not None)
    fact=AddressingObservation(entry["device_id"],endpoint_digest(entry),"ASSIGNED",100,60)
    assert table.record_addressing(fact,current_owner=current_owner)=="CONFIRMED"
    assert results==["SETTINGS_BUSY"] and setup.store.native is original


@pytest.mark.parametrize("raises",[False,True])
def test_native_owner_callback_refusal_restores_store_and_retains_pending(native_table,raises):
    table,_=native_table
    setup=table.setup
    original=setup.store.native
    before=table.read()
    def current_owner():
        setup._fresh()
        if setup.store.native is not original:
            if raises:
                raise SettingsError("SETTINGS_SYNTHETIC_OWNER_UNAVAILABLE")
            return False
        return True
    entry=next(e for e in before["catalogue"]["entries"] if e is not None)
    fact=AddressingObservation(entry["device_id"],endpoint_digest(entry),"ASSIGNED",100,60)
    with pytest.raises(NetworkTableError):
        table.record_addressing(fact,current_owner=current_owner)
    assert setup.store.native is original
    assert setup._payload["network_table"]["pending"]["kind"]=="UPDATE"
    assert table.read(allow_pending=True)==before
    with pytest.raises(NetworkTableError,match="^NETWORK_TABLE_INSPECT_REQUIRED$"):
        table.read()
