"""Actual protected root-move WAL cut/copy/protection, synthetic SDK only."""
from contextlib import contextmanager
from dataclasses import replace
import pytest

from tb4.commissioning_checks import detect_environment
from tb4.configuration_contract import ConfigurationError
from tb4.private_settings import native_settings, SettingsError
from tb4.reconfiguration_roots import DocsRootMoves
from tb4.watchdog.leadership_runtime import Action
from reconfiguration_roots_support import system
from test_private_settings_native import fixture, protect_fixture


@pytest.mark.parametrize("at",["invoking","revoked"])
def test_actual_native_disposition_cut_recovers_exact_frame_without_sdk_reissue(fixture,at):
    root,store = fixture; s = native_system(root,store)
    s.roots.begin(owner_authorized=True)
    if at == "revoked":
        start = s.value.effects.start
        def pause(*args,**kwargs):
            raise ConfigurationError("SYNTHETIC_BEFORE_EFFECT_START")
        s.value.effects.start = pause
        with pytest.raises(ConfigurationError,match="SYNTHETIC_BEFORE_EFFECT_START"):
            s.roots.advance(owner_authorized=True)
        s.value.effects.start = start
    original = (root.parent/"original"/"settings.json").read_bytes()
    locked = store.native.locked
    @contextmanager
    def cut():
        with locked() as port:
            promote = port.promote
            def stop():
                payload = store._decode(port.read("settings.pending"),port.binding).payload
                if payload["pending"] is not None and payload["pending"].get("dispatch") == at.upper():
                    raise OSError("SYNTHETIC_DISPOSITION_LOCAL_CUT")
                promote()
            port.promote = stop
            yield port
    store.native.locked = cut
    with pytest.raises(SettingsError,match="SETTINGS_STORE_UNAVAILABLE"):
        if at == "invoking":
            s.roots.advance(owner_authorized=True)
        else:
            s.roots.revoke_prepared(owner_authorized=True)
    store.native.locked = locked
    pending = (root/"settings.pending").read_bytes()
    assert not s.moves
    with pytest.raises(SettingsError,match="RECOVERY_REQUIRED"):
        store.read()
    assert s.roots.recover_local(owner_authorized=True) == "INSPECT_REQUIRED"
    assert (root/"settings.json").read_bytes() == pending and not s.moves
    fresh = DocsRootMoves(s.context)
    assert fresh.inspect() == "UNKNOWN" and fresh.advance(owner_authorized=True) == "UNKNOWN"
    if at == "revoked":
        assert fresh.require_revocation(fresh.revocation()) == fresh.revocation()
        assert s.value.effects.receipt(Action.IDENTITY) is None
    else:
        with pytest.raises(ConfigurationError,match="NOT_PREPARED"):
            fresh.revoke_prepared(owner_authorized=True)
        assert s.value.effects.receipt(Action.IDENTITY)["outcome"] == "UNKNOWN"
    assert not s.moves and (root.parent/"original"/"settings.json").read_bytes() == original


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
