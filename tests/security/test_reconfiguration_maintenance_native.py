"""Actual native state/profile/evidence cuts in freshly owned fixture roots."""
from contextlib import contextmanager
from dataclasses import replace
import sys

import pytest

from tb4.configuration_contract import ConfigurationError
from tb4.private_settings import native_settings, SettingsError
from tb4.reconfiguration_maintenance import Maintenance
from reconfiguration_controller_support import resolution_archive, system
from test_private_settings_native import fixture, protect_fixture  # noqa: F401

pytestmark = pytest.mark.skipif(sys.platform not in {"win32","linux"}, reason="native Windows/Linux64")


def native_system(root, store):
    baseline = native_settings(root.parent/"baseline", create=True, owner_authorized=True)
    profile = native_settings(root.parent/"profile", create=True, owner_authorized=True)
    return system(profile_store=profile, state_store=store, baseline_store=baseline)


def test_actual_native_wal_before_cas_restart_resolution_and_profile_preservation(fixture, capsys):
    root, store = fixture
    value = native_system(root, store)
    profile_before = value.setup.store.read()
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    resumed = Maintenance(replace(value.context, store=native_settings(root)))
    decision, status = resumed.proposal()
    archive = resolution_archive(value, native_settings(root.parent/"resolution", create=True, owner_authorized=True))
    assert resumed.resolve(decision, archive, owner_authorized=True) == "RESOLVED"
    assert Maintenance(replace(value.context, store=native_settings(root))).require_resolved(archive) == decision
    assert value.setup.store.read() == profile_before
    assert capsys.readouterr() == ("", "")


def test_actual_native_local_promotion_cut_recovers_exact_wal_without_provider_replay(fixture):
    root, store = fixture
    value = native_system(root, store)
    original = store.native.locked
    @contextmanager
    def stop():
        with original() as port:
            def fail():
                raise OSError("SYNTHETIC_STATE_CANARY")
            port.promote = fail
            yield port
    store.native.locked = stop
    commits = value.provider.store.commits
    with pytest.raises((ConfigurationError,SettingsError)):
        value.controller.begin(owner_authorized=True)
    pending = (root/"settings.pending").read_bytes()
    assert value.provider.store.commits == commits
    resumed = Maintenance(replace(value.context, store=native_settings(root)))
    assert resumed.recover_local(owner_authorized=True) == "INSPECT_REQUIRED"
    assert (root/"settings.json").read_bytes() == pending
    assert resumed.inspect() == "UNKNOWN" and value.provider.store.commits == commits


def test_actual_native_wrong_directory_or_broad_state_cannot_mint_resolution(fixture):
    root, store = fixture
    value = native_system(root, store)
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    other = root.parent/"foreign-state"
    foreign = native_settings(other, create=True, owner_authorized=True)
    path = other/"settings.json"
    path.write_bytes((root/"settings.json").read_bytes())
    protect_fixture(path)
    with pytest.raises(ConfigurationError, match="LOCAL_INSPECT_REQUIRED"):
        Maintenance(replace(value.context, store=foreign)).proposal()
    protect_fixture(root, broad=True)
    try:
        with pytest.raises(ConfigurationError, match="LOCAL_INSPECT_REQUIRED"):
            value.controller.proposal()
    finally:
        protect_fixture(root)
