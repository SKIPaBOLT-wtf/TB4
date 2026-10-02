"""Native isolated table locations on each actual supported host, never home data."""
import os
from pathlib import Path
import sys

import pytest

from tb4.commissioning_state import Setup
from tb4.network_table import NetworkTableError
from tb4.network_table_store import LocalNetworkTable
from tb4.private_settings import native_settings
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
    with native.locked():
        with pytest.raises(NetworkTableError):
            table.approve(good_proposal(table),now=100,owner_authorized=True)
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

