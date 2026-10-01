"""Actual OS tests only use fresh synthetic private directories and bytes."""
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

from tb4.private_settings import native_settings, SettingsError

SUPPORTED = sys.platform == "win32" or sys.platform == "linux"
pytestmark = pytest.mark.skipif(not SUPPORTED, reason="requires native Windows or qualified Linux64")
PAYLOAD = {"installation": "synthetic-settings-id", "phase": "INCOMPLETE"}


def protect_fixture(path, *, broad=False):
    """TEST ONLY: initialize/alter fresh pytest-owned fixture protection."""
    if os.name == "nt":
        from test_windows_key_native import protect
        from tb4.windows_key_native import WindowsKeyNative
        protect(WindowsKeyNative(), path, "(A;;GR;;;WD)" if broad else "")
    else:
        path.chmod(0o755 if broad and path.is_dir() else
                   0o644 if broad else 0o700 if path.is_dir() else 0o600)


@pytest.fixture
def fixture(tmp_path):
    # This parent is new fixture data, never a preexisting user directory.
    parent = tmp_path / "private-fixture-parent"
    parent.mkdir(mode=0o700)
    protect_fixture(parent)
    root = parent / "r2-settings"
    store = native_settings(root, create=True, owner_authorized=True)
    return root, store


def test_actual_private_owner_lock_write_restart_and_previous(fixture, capsys):
    root, store = fixture
    assert store.read() is None
    first = store.save(PAYLOAD, expected_revision=0)
    assert native_settings(root).read() == first
    second = native_settings(root).save({**PAYLOAD, "phase": "CANCELLED"}, expected_revision=1)
    assert second.previous == PAYLOAD
    assert second.payload["installation"] == first.payload["installation"]
    assert store.recover_pending() == second
    assert capsys.readouterr() == ("", "")


def test_existing_root_cannot_be_recreated_or_repaired(fixture):
    root, store = fixture
    store.save(PAYLOAD, expected_revision=0)
    raw = (root / "settings.json").read_bytes()
    with pytest.raises(SettingsError):
        native_settings(root, create=True, owner_authorized=True)
    assert (root / "settings.json").read_bytes() == raw


def test_creation_needs_explicit_selected_root_authorization(tmp_path):
    root = tmp_path / "must-not-create"
    with pytest.raises(SettingsError, match="NOT_AUTHORIZED"):
        native_settings(root, create=True)
    assert not root.exists()


def test_actual_lock_contention_is_explicit_and_releases(fixture):
    root, store = fixture
    with store.native.locked():
        with pytest.raises(SettingsError, match="BUSY"):
            native_settings(root).read()
    assert store.read() is None


def test_actual_copied_state_is_rejected_by_directory_binding(fixture):
    root, store = fixture
    store.save(PAYLOAD, expected_revision=0)
    other = root.parent / "other-settings"
    other_store = native_settings(other, create=True, owner_authorized=True)
    target = other / "settings.json"
    target.write_bytes((root / "settings.json").read_bytes())
    protect_fixture(target)
    with pytest.raises(SettingsError, match="IDENTITY_MISMATCH"):
        other_store.read()


def test_actual_interrupted_stage_recovers_exact_identity(fixture):
    root, store = fixture
    original = store.native.locked
    from contextlib import contextmanager
    @contextmanager
    def interrupted():
        with original() as port:
            def stop():
                raise OSError("SYNTHETIC_SETTINGS_CANARY")
            port.promote = stop
            yield port
    store.native.locked = interrupted
    with pytest.raises(SettingsError):
        store.save(PAYLOAD, expected_revision=0)
    pending = (root / "settings.pending").read_bytes()
    restarted = native_settings(root)
    with pytest.raises(SettingsError, match="RECOVERY_REQUIRED"):
        restarted.read()
    assert restarted.recover_pending().payload == PAYLOAD
    assert (root / "settings.json").read_bytes() == pending
    assert not (root / "settings.pending").exists()


def test_actual_malformed_staging_is_not_overwritten(fixture):
    root, store = fixture
    with store.native.locked() as port:
        port.stage(b"{")
    with pytest.raises(SettingsError):
        store.recover_pending()
    with pytest.raises(SettingsError):
        store.save(PAYLOAD, expected_revision=0)
    assert (root / "settings.pending").read_bytes() == b"{"


@pytest.mark.parametrize("target", ["root", "settings.json", "settings.lock"])
def test_actual_broad_permissions_fail_without_repair(fixture, target):
    root, store = fixture
    store.save(PAYLOAD, expected_revision=0)
    path = root if target == "root" else root / target
    protect_fixture(path, broad=True)
    try:
        with pytest.raises(SettingsError):
            native_settings(root).read()
        if os.name != "nt":
            assert path.stat().st_mode & 0o077
    finally:
        protect_fixture(path)


@pytest.mark.parametrize("name", ["settings.json", "settings.pending", "settings.lock"])
def test_actual_hardlink_is_rejected(fixture, name):
    root, store = fixture
    # Seed only a new synthetic object; never replace a real settings file.
    source = root / "fixture-data"
    source.write_bytes(b"{}")
    protect_fixture(source)
    os.link(source, root / name)
    with pytest.raises(SettingsError):
        store.read()
    assert source.read_bytes() == b"{}"


@pytest.mark.skipif(os.name == "nt", reason="Linux FIFO/no-follow specific")
@pytest.mark.parametrize("kind", ["symlink", "fifo", "directory"])
def test_linux_special_objects_fail_without_opening_or_blocking(fixture, kind):
    root, store = fixture
    target = root / "settings.json"
    if kind == "symlink":
        source = root / "fixture-data"
        source.write_bytes(b"do-not-touch")
        target.symlink_to(source)
    elif kind == "fifo":
        os.mkfifo(target, mode=0o600)
    else:
        target.mkdir(mode=0o700)
    with pytest.raises(SettingsError):
        store.read()


def test_actual_payload_digest_corruption_is_preserved(fixture):
    root, store = fixture
    store.save(PAYLOAD, expected_revision=0)
    path = root / "settings.json"
    frame = json.loads(path.read_bytes())
    frame["payload"]["installation"] = "wrong-identity"
    path.write_text(json.dumps(frame), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(SettingsError, match="DIGEST_MISMATCH"):
        native_settings(root).read()
    assert path.read_bytes() == before


@pytest.mark.skipif(os.name == "nt", reason="Linux root rename and pinned-dir check")
def test_linux_directory_replacement_during_transaction_fails(fixture):
    root, store = fixture
    with store.native.locked() as port:
        root.rename(root.parent / "saved-fixture")
        root.mkdir(mode=0o700)
        with pytest.raises(SettingsError, match="DIRECTORY_CHANGED"):
            port.stage(b"{}")
    assert not (root / "settings.pending").exists()
