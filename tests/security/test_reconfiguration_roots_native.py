"""Actual protected root-move WAL cut/copy/protection, synthetic SDK only."""
from contextlib import contextmanager
from dataclasses import replace
import pytest

from tb4.commissioning_checks import detect_environment
from tb4.configuration_contract import ConfigurationError
from tb4.private_settings import native_settings, SettingsError
from tb4.reconfiguration_roots import DocsRootMoves
from reconfiguration_roots_support import system
from test_private_settings_native import fixture, protect_fixture


def native_system(root,store):
    def private(name):
        return native_settings(root.parent/name,create=True,owner_authorized=True)
    return system(root_store=store,profile=private("candidate"),archive=private("archive"),
        transaction=private("candidate-meta"),profile_store=private("original"),
        checkpoint_store=private("checkpoint"),effect_store=private("effects"),
        state_store=private("maintenance"),baseline_store=private("baseline"),
        environment=lambda:detect_environment(launch_mode="DESKTOP_SESSION"))


@pytest.mark.parametrize("at",["begin","prepared","completed"])
def test_actual_native_root_cut_promotes_same_frame_and_never_reissues_old_sdk(fixture,at):
    root,store = fixture; s = native_system(root,store)
    if at != "begin":
        s.roots.begin(owner_authorized=True)
    original = (root.parent/"original"/"settings.json").read_bytes()
    locked = store.native.locked
    @contextmanager
    def cut():
        with locked() as port:
            promote = port.promote
            def stop():
                payload = store._decode(port.read("settings.pending"),port.binding).payload
                if at != "completed" or payload["index"] == 1:
                    raise OSError("SYNTHETIC_ROOT_LOCAL_CUT")
                promote()
            port.promote = stop
            yield port
    store.native.locked = cut
    with pytest.raises(SettingsError,match="SETTINGS_STORE_UNAVAILABLE"):
        s.roots.begin(owner_authorized=True) if at == "begin" else s.roots.advance(owner_authorized=True)
    store.native.locked = locked
    pending = (root/"settings.pending").read_bytes()
    moves = len(s.moves)
    assert s.roots.recover_local(owner_authorized=True) == "INSPECT_REQUIRED"
    assert (root/"settings.json").read_bytes() == pending
    assert DocsRootMoves(s.context).inspect() == ("UNKNOWN" if at == "prepared" else "MOVING")
    assert len(s.moves) == moves and (root.parent/"original"/"settings.json").read_bytes() == original
    if at == "prepared":
        assert DocsRootMoves(s.context).advance(owner_authorized=True) == "UNKNOWN" and not s.moves


def test_actual_native_root_wal_restart_copy_and_broad_protection(fixture):
    root,store = fixture; s = native_system(root,store)
    s.roots.begin(owner_authorized=True)
    assert DocsRootMoves(s.context).inspect() == "MOVING"
    foreign = root.parent/"foreign-root-wal"
    copied = native_settings(foreign,create=True,owner_authorized=True)
    target = foreign/"settings.json"; target.write_bytes((root/"settings.json").read_bytes()); protect_fixture(target)
    with pytest.raises((SettingsError,ConfigurationError)):
        DocsRootMoves(replace(s.context,store=copied)).advance(owner_authorized=True)
    protect_fixture(root,broad=True)
    try:
        with pytest.raises((SettingsError,ConfigurationError)):
            DocsRootMoves(s.context).advance(owner_authorized=True)
    finally:
        protect_fixture(root)
    assert not s.moves
