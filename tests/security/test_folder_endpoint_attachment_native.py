"""Actual Windows/Linux private pointer link; metadata never uses credentials."""
import copy
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tb4.commissioning_state import Setup
from tb4.drive.docs_authority import AuthorityError
import tb4.drive.folder_endpoint as endpoint_module
import tb4.drive.folder_endpoint_attachment as attachment_module
from tb4.drive.folder_endpoint import NativeFolderEndpoint
from tb4.drive.folder_endpoint_attachment import NativeFolderEndpointAttachment
from tb4.private_settings import SettingsError, native_settings, encoded
from tb4.reconfiguration_maintenance import sha
from tests.security.test_private_settings_native import fixture, SUPPORTED
from tests.security.test_folder_endpoint_native import system, prepare

pytestmark = pytest.mark.skipif(not SUPPORTED, reason="Actual Windows/Linux protected endpoint attachment")


def linked(fixture, monkeypatch):
    value = system(fixture, monkeypatch)
    reference = prepare(value)
    link = NativeFolderEndpointAttachment(value.selection, value.setup.store)
    return value, reference, link


def observe_guards(monkeypatch):
    failed = []
    for module in (attachment_module, endpoint_module):
        original = module.require
        def observe(condition, code, _original=original):
            if not condition:
                failed.append(code)
            return _original(condition, code)
        monkeypatch.setattr(module, "require", observe)
    return failed


def report(state, reference):
    return dict(status=state, reference=reference, metadata_only=True,
        credential_ready=False, runtime_active=False, automatic_replay=False)


def bytes_at(value):
    return (value.root / "settings.json").read_bytes(), (value.metadata_root / "settings.json").read_bytes()


def stopped_attachment(value, reference, link, monkeypatch, *, after=False):
    with value.setup.store.native.locked() as port:
        kind = type(port)
    original = kind.promote
    profile_binding = link._binding
    def stop(port):
        if sha(port.binding) == profile_binding:
            if after:
                original(port)
            raise SettingsError("SYNTHETIC_NATIVE_COMMIT_REPLY_LOST")
        return original(port)
    monkeypatch.setattr(kind, "promote", stop)
    with pytest.raises(SettingsError):
        link.attach(value.setup, reference, owner_authorized=True)
    monkeypatch.setattr(kind, "promote", original)


def stage_changed(value, mutation):
    # Alter only this owned existing synthetic pending frame, keeping the native
    # checksum intact so the tested semantic guard, not a checksum error, rejects it.
    import hashlib
    import json
    with value.setup.store.native.locked() as port:
        raw = port.read("settings.pending")
        frame = json.loads(raw)
        mutation(frame)
        frame.pop("digest")
        frame["digest"] = hashlib.sha256(encoded(frame)).hexdigest()
        (value.root / "settings.pending").write_bytes(encoded(frame))


def test_native_attach_preserves_full_parent_identity_image_history_and_grants_nothing(fixture, monkeypatch, capsys):
    v, reference, link = linked(fixture, monkeypatch)
    v.setup._save({**v.setup._payload, "operations": {"f"*64: "CONFIRMED"}})
    before = v.setup.store.read()
    metadata = v.metadata.read()
    key = v.key.read_bytes()
    def no_key_io(*_args, **_kwargs):
        pytest.fail("Metadata attachment opened a credential key")
    monkeypatch.setattr(type(v.store._native), "open_key", no_key_io)
    assert link.inspect(reference) == report("UNSELECTED", reference)
    assert link.attach(v.setup, reference, owner_authorized=True) == report("ATTACHED", reference)
    after = v.setup.store.read()
    pointer = after.payload["folder_endpoint"]
    assert set(pointer) == {"schema_version", "root", "reference", "binding_digest"}
    assert pointer == dict(schema_version=1, root=str(v.metadata_root),
        reference=reference, binding_digest=v.selection._binding)
    assert after.revision == before.revision + 1 and after.previous == before.payload
    assert {k:x for k,x in after.payload.items() if k != "folder_endpoint"} == before.payload
    assert v.metadata.read() == metadata and v.key.read_bytes() == key
    assert key not in (v.root / "settings.json").read_bytes()
    assert v.setup.status()["runtime_active"] is False and not v.setup.status()["settings_validated"]
    assert capsys.readouterr() == ("", "")


def test_native_same_pointer_is_idempotent_in_ready_and_unknown_states_without_reset(fixture, monkeypatch):
    v, reference, link = linked(fixture, monkeypatch)
    link.attach(v.setup, reference, owner_authorized=True)
    for state, reason, operations in [
        ("SETTINGS_READY", "SETTINGS_VALIDATED", {}),
        ("BLOCKED", "UNKNOWN_OPERATION", {"e"*64: "UNKNOWN"})]:
        v.setup._save({**v.setup._payload, "state": state, "reason": reason, "operations": operations})
        before, raw = v.setup.store.read(), bytes_at(v)
        assert link.attach(v.setup, reference, owner_authorized=True) == report("ATTACHED", reference)
        assert link.recover(reference, owner_authorized=True) == report("ATTACHED", reference)
        assert v.setup.store.read() == before and bytes_at(v) == raw


@pytest.mark.parametrize("authorization", [False, None, 1, "true"])
def test_native_explicit_owner_required_before_save_or_recovery(fixture, monkeypatch, authorization):
    v, reference, link = linked(fixture, monkeypatch)
    before = bytes_at(v)
    failed = observe_guards(monkeypatch)
    with pytest.raises(AuthorityError, match="^FOLDER_ENDPOINT_OWNER_REQUIRED$"):
        link.attach(v.setup, reference, owner_authorized=authorization)
    with pytest.raises(AuthorityError, match="^FOLDER_ENDPOINT_OWNER_REQUIRED$"):
        link.recover(reference, owner_authorized=authorization)
    assert failed == ["FOLDER_ENDPOINT_OWNER_REQUIRED"] * 2 and bytes_at(v) == before


def test_native_stale_model_cannot_attach_new_profile_selection(fixture, monkeypatch):
    v, reference, link = linked(fixture, monkeypatch)
    original = v.setup
    Setup(v.setup.store).choose({})
    before = bytes_at(v)
    with pytest.raises(SettingsError, match="^SETTINGS_CHANGED_RELOAD_REQUIRED$"):
        link.attach(original, reference, owner_authorized=True)
    assert bytes_at(v) == before and not (v.root / "settings.pending").exists()


@pytest.mark.parametrize("state,reason", [("SETTINGS_READY", "SETTINGS_VALIDATED"),
    ("BLOCKED", "STORAGE_UNAVAILABLE"), ("CANCELLED", "CANCELLED")])
def test_native_new_link_requires_incomplete_profile_and_preserves_bytes(fixture, monkeypatch, state, reason):
    v, reference, link = linked(fixture, monkeypatch)
    v.setup._save({**v.setup._payload, "state": state, "reason": reason})
    before = bytes_at(v)
    failed = observe_guards(monkeypatch)
    with pytest.raises(SettingsError, match="^SETTINGS_STORE_UNAVAILABLE$"):
        link.attach(v.setup, reference, owner_authorized=True)
    assert failed == ["FOLDER_ENDPOINT_ATTACHMENT_STATE"]
    assert bytes_at(v) == before and not (v.root / "settings.pending").exists()


def test_native_first_selection_refuses_local_unknown_but_retains_it_for_takeover(fixture, monkeypatch):
    v, reference, link = linked(fixture, monkeypatch)
    v.setup._save({**v.setup._payload, "state": "INCOMPLETE",
        "reason": "UNKNOWN_OPERATION", "operations": {"e"*64: "UNKNOWN"}})
    before = bytes_at(v)
    failed = observe_guards(monkeypatch)
    with pytest.raises(SettingsError, match="^SETTINGS_STORE_UNAVAILABLE$"):
        link.attach(v.setup, reference, owner_authorized=True)
    assert failed == ["FOLDER_ENDPOINT_ATTACHMENT_UNKNOWN"]
    assert bytes_at(v) == before and v.setup._payload["operations"] == {"e"*64: "UNKNOWN"}
    assert not (v.root / "settings.pending").exists()


@pytest.mark.parametrize("field", ["reference", "root", "binding_digest"])
def test_native_existing_different_pointer_cannot_be_rebound_silently(fixture, monkeypatch, field):
    v, reference, link = linked(fixture, monkeypatch)
    link.attach(v.setup, reference, owner_authorized=True)
    payload = copy.deepcopy(v.setup._payload)
    pointer = payload["folder_endpoint"]
    pointer[field] = {"reference": "fe_"+"f"*32, "root": str(v.root),
                      "binding_digest": "f"*64}[field]
    v.setup._save(payload)
    before = bytes_at(v)
    failed = observe_guards(monkeypatch)
    with pytest.raises(SettingsError, match="^SETTINGS_STORE_UNAVAILABLE$"):
        link.attach(v.setup, reference, owner_authorized=True)
    assert failed == ["FOLDER_ENDPOINT_ATTACHMENT_CONFLICT"]
    assert bytes_at(v) == before


def test_native_foreign_reference_does_not_attach_or_mint_new_frame(fixture, monkeypatch):
    v, _, link = linked(fixture, monkeypatch)
    before = bytes_at(v)
    failed = observe_guards(monkeypatch)
    with pytest.raises(SettingsError, match="^SETTINGS_STORE_UNAVAILABLE$"):
        link.attach(v.setup, "fe_"+"f"*32, owner_authorized=True)
    assert failed == ["FOLDER_ENDPOINT_REFERENCE"] and bytes_at(v) == before


def test_native_alias_and_untyped_stores_are_denied(fixture, monkeypatch):
    v, _, _ = linked(fixture, monkeypatch)
    before = bytes_at(v)
    for profile in (v.metadata, native_settings(v.metadata_root)):
        with pytest.raises(AuthorityError, match="^FOLDER_ENDPOINT_ATTACHMENT_ALIAS$"):
            NativeFolderEndpointAttachment(v.selection, profile)
    with pytest.raises(AuthorityError, match="^FOLDER_ENDPOINT_ATTACHMENT_STORE$"):
        NativeFolderEndpointAttachment(SimpleNamespace(), v.setup.store)
    with pytest.raises(AuthorityError, match="^FOLDER_ENDPOINT_ATTACHMENT_STORE$"):
        NativeFolderEndpointAttachment(v.selection, object())
    assert bytes_at(v) == before


def test_native_selected_revocation_is_not_overridden_by_attachment(fixture, monkeypatch):
    v, reference, link = linked(fixture, monkeypatch)
    v.resolver.revoke(v.handle, owner_authorized=True)
    v.setup.persist_credentials(v.store, v.resolver, v.selected)
    before = bytes_at(v)
    failed = observe_guards(monkeypatch)
    with pytest.raises(SettingsError, match="^SETTINGS_STORE_UNAVAILABLE$"):
        link.attach(v.setup, reference, owner_authorized=True)
    assert failed == ["FOLDER_ENDPOINT_CREDENTIAL"] and bytes_at(v) == before


@pytest.mark.parametrize("after", [False, True])
def test_native_same_pending_or_completed_link_restarts_without_repeating_save(fixture, monkeypatch, after):
    v, reference, link = linked(fixture, monkeypatch)
    before = v.setup.store.read()
    metadata = v.metadata.read()
    stopped_attachment(v, reference, link, monkeypatch, after=after)
    if not after:
        assert (v.root / "settings.json").read_bytes()
        with pytest.raises(SettingsError, match="^SETTINGS_RECOVERY_REQUIRED$"):
            Setup(native_settings(v.root))
    restarted = NativeFolderEndpointAttachment(
        NativeFolderEndpoint(native_settings(v.metadata_root), v.setup.installation_id),
        native_settings(v.root))
    assert restarted.inspect(reference) == report("ATTACHED" if after else "PENDING", reference)
    def forbidden(*_args, **_kwargs):
        pytest.fail("Recovery reconstructed or resent native candidate")
    monkeypatch.setattr(v.setup.store.__class__, "_save_locked", forbidden)
    assert restarted.recover(reference, owner_authorized=True) == report("ATTACHED", reference)
    after_snapshot = v.setup.store.read()
    assert after_snapshot.revision == before.revision+1 and after_snapshot.previous == before.payload
    assert after_snapshot.payload["folder_endpoint"]["reference"] == reference
    assert {k:x for k,x in after_snapshot.payload.items() if k != "folder_endpoint"} == before.payload
    assert v.metadata.read() == metadata and not (v.root / "settings.pending").exists()
    assert Setup(native_settings(v.root))._payload == after_snapshot.payload


@pytest.mark.parametrize("change", ["profile", "previous", "revision", "reference", "root", "binding_digest"])
def test_native_pending_semantic_conflicts_hold_both_complete_frames(fixture, monkeypatch, change):
    v, reference, link = linked(fixture, monkeypatch)
    stopped_attachment(v, reference, link, monkeypatch)
    def mutate(frame):
        if change == "profile": frame["payload"]["reason"] = "MISSING_CHOICES"
        if change == "previous": frame["previous"]["reason"] = "MISSING_CHOICES"
        if change == "revision": frame["revision"] += 1
        if change == "reference": frame["payload"]["folder_endpoint"]["reference"] = "fe_"+"f"*32
        if change == "root": frame["payload"]["folder_endpoint"]["root"] = str(v.root)
        if change == "binding_digest": frame["payload"]["folder_endpoint"]["binding_digest"] = "f"*64
    stage_changed(v, mutate)
    raw = bytes_at(v)
    pending = (v.root / "settings.pending").read_bytes()
    failed = observe_guards(monkeypatch)
    with pytest.raises(SettingsError, match="^SETTINGS_STORE_UNAVAILABLE$"):
        link.recover(reference, owner_authorized=True)
    assert failed == ["FOLDER_ENDPOINT_ATTACHMENT_RECOVERY_CONFLICT"]
    assert bytes_at(v) == raw and (v.root / "settings.pending").read_bytes() == pending


def test_native_pending_cannot_promote_after_original_current_profile_changes(fixture, monkeypatch):
    import hashlib
    import json
    v, reference, link = linked(fixture, monkeypatch)
    stopped_attachment(v, reference, link, monkeypatch)
    pending = (v.root / "settings.pending").read_bytes()
    with v.setup.store.native.locked() as port:
        frame = json.loads(port.read("settings.json"))
        frame["payload"]["reason"] = "MISSING_CHOICES"
        frame.pop("digest")
        frame["digest"] = hashlib.sha256(encoded(frame)).hexdigest()
        # Only the owned synthetic current file changes; pending bytes stay exact.
        (v.root / "settings.json").write_bytes(encoded(frame))
    before = bytes_at(v)
    failed = observe_guards(monkeypatch)
    with pytest.raises(SettingsError, match="^SETTINGS_STORE_UNAVAILABLE$"):
        link.recover(reference, owner_authorized=True)
    assert failed == ["FOLDER_ENDPOINT_ATTACHMENT_RECOVERY_CONFLICT"]
    assert bytes_at(v) == before and (v.root / "settings.pending").read_bytes() == pending


def test_native_recovery_does_not_create_an_unstarted_link(fixture, monkeypatch):
    v, reference, link = linked(fixture, monkeypatch)
    before = bytes_at(v)
    failed = observe_guards(monkeypatch)
    with pytest.raises(SettingsError, match="^SETTINGS_STORE_UNAVAILABLE$"):
        link.recover(reference, owner_authorized=True)
    assert failed == ["FOLDER_ENDPOINT_ATTACHMENT_NOT_STARTED"] and bytes_at(v) == before


def test_native_changed_metadata_frame_refuses_attachment_and_preserves_profile(fixture, monkeypatch):
    v, reference, link = linked(fixture, monkeypatch)
    payload = copy.deepcopy(v.metadata.read().payload)
    v.metadata.save(payload, expected_revision=1)
    before = bytes_at(v)
    failed = observe_guards(monkeypatch)
    with pytest.raises(SettingsError, match="^SETTINGS_STORE_UNAVAILABLE$"):
        link.attach(v.setup, reference, owner_authorized=True)
    assert failed == ["FOLDER_ENDPOINT_IMMUTABLE"] and bytes_at(v) == before


def test_native_endpoint_lock_contention_does_not_touch_profile_or_pending(fixture, monkeypatch):
    v, reference, link = linked(fixture, monkeypatch)
    before = bytes_at(v)
    with v.metadata.native.locked():
        with pytest.raises(SettingsError):
            link.attach(v.setup, reference, owner_authorized=True)
    assert bytes_at(v) == before and not (v.root / "settings.pending").exists()


@pytest.mark.parametrize("store", ["endpoint", "profile"])
def test_native_unsafe_hardlinked_frame_is_not_a_private_attachment_grant(fixture, monkeypatch, store):
    v, reference, link = linked(fixture, monkeypatch)
    path = (v.metadata_root if store == "endpoint" else v.root) / "settings.json"
    alias = v.root.parent / "owned-synthetic-unsafe-frame-alias"
    before = bytes_at(v)
    os.link(path, alias)
    try:
        assert path.stat().st_nlink == 2
        with pytest.raises(SettingsError):
            link.attach(v.setup, reference, owner_authorized=True)
        assert bytes_at(v) == before and not (v.root / "settings.pending").exists()
    finally:
        alias.unlink()

